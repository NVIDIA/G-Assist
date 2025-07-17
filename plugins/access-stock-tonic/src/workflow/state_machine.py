"""
LangGraph State Machine for Structured Equity Product Creation
"""

import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
from enum import Enum
import json

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
try:
    from langchain_openai import ChatOpenAI
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

from ..agents.query_processor_agent import QueryProcessorAgent
from ..agents.stock_picker_agent import StockPickerAgent
from ..agents.analyzer_agent import AnalyzerAgent
from ..agents.product_bundler_agent import ProductBundlerAgent
from ..agents.summarizer_agent import SummarizerAgent
from ..tools.stock_selection_tool import StockSelectionTool
from .config import WorkflowConfig, DEFAULT_CONFIG
from ..agents.gassist_llm import GAssistLLM

class WorkflowState(TypedDict):
    """State definition for the workflow."""
    user_query: str
    processed_query: Optional[Dict[str, Any]]
    stock_picker_query: Optional[str]
    discovered_stocks: Optional[List[Dict[str, Any]]]
    analysis_results: Optional[List[Dict[str, Any]]]
    product_bundle: Optional[Dict[str, Any]]
    user_feedback: Optional[str]
    user_satisfied: Optional[bool]
    iteration_count: int
    max_iterations: int
    error_message: Optional[str]
    workflow_status: str
    config: Dict[str, Any]

class WorkflowStatus(Enum):
    """Workflow status enumeration."""
    INITIALIZED = "initialized"
    QUERY_PROCESSED = "query_processed"
    STOCKS_DISCOVERED = "stocks_discovered"
    ANALYSIS_COMPLETE = "analysis_complete"
    PRODUCT_CREATED = "product_created"
    USER_REVIEW = "user_review"
    COMPLETED = "completed"
    ERROR = "error"

class StructuredEquityWorkflow:
    """
    LangGraph-based state machine for structured equity product creation.
    """
    
    def __init__(self, config: Optional[WorkflowConfig] = None):
        """
        Initialize the structured equity workflow.
        
        Args:
            openai_api_key: OpenAI API key for LLM operations
            config: Workflow configuration
            use_llm: Whether to use LLM prompts for enhanced processing
            llm_provider: LLM provider ("openai", "anthropic", "huggingface")
            anthropic_api_key: Anthropic API key (if using Anthropic)
            hf_api_key: HuggingFace API key (if using HuggingFace or MCP server)
            openai_model: OpenAI model name
            anthropic_model: Anthropic model name
            hf_model: HuggingFace model name
            mcp_server_url: MCP server URL for stock analysis
            use_mcp: Whether to use MCP server for stock analysis
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or WorkflowConfig()
        self.llm = GAssistLLM()
        self.query_processor = QueryProcessorAgent(llm=self.llm)
        self.stock_picker = StockPickerAgent(llm=self.llm)
        self.analyzer = AnalyzerAgent(
            mcp_url="https://tonic-stock-predictions.hf.space/mcp/sse",
            openai_api_key="", use_llm=False, llm_provider="", 
            anthropic_api_key="", hf_api_key="",
            openai_model="", anthropic_model="", hf_model=""
        )
        self.product_bundler = ProductBundlerAgent(
            openai_api_key="", 
            use_llm=False, 
            llm_provider="", 
            anthropic_api_key="", 
            hf_api_key="",
            openai_model="", 
            anthropic_model="", 
            hf_model="",
            use_summarizer=True  # Enable summarizer by default
        )
        self.stock_selector = StockSelectionTool(
            openai_api_key="", use_llm=False, llm_provider="", anthropic_api_key="", hf_api_key="",
            openai_model="", anthropic_model="", hf_model=""
        )
        
        # Create the state machine
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow."""
        
        # Create the state graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("process_query", self._process_query_node)
        workflow.add_node("discover_stocks", self._discover_stocks_node)
        workflow.add_node("analyze_stocks", self._analyze_stocks_node)
        workflow.add_node("create_product", self._create_product_node)
        workflow.add_node("get_user_feedback", self._get_user_feedback_node)
        workflow.add_node("handle_user_feedback", self._handle_user_feedback_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Set entry point
        workflow.set_entry_point("process_query")
        
        # Define edges
        workflow.add_edge("process_query", "discover_stocks")
        workflow.add_edge("discover_stocks", "analyze_stocks")
        workflow.add_edge("analyze_stocks", "create_product")
        workflow.add_edge("create_product", "get_user_feedback")
        
        # Conditional edges based on user feedback
        workflow.add_conditional_edges(
            "get_user_feedback",
            self._should_continue_workflow,
            {
                "continue": "handle_user_feedback",
                "complete": END,
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("handle_user_feedback", "discover_stocks")
        workflow.add_edge("handle_error", END)
        
        # Compile the workflow
        return workflow.compile()
    
    def _process_query_node(self, state: WorkflowState) -> WorkflowState:
        """Process the user query into structured criteria."""
        try:
            self.logger.info("Processing user query...")
            
            # Process the query
            processed_query = self.query_processor.process_query(state["user_query"])
            
            # Convert to stock picker query
            stock_picker_query = self.query_processor.to_stock_picker_query(processed_query)
            
            # Update state
            state.update({
                "processed_query": processed_query.__dict__,
                "stock_picker_query": stock_picker_query,
                "workflow_status": WorkflowStatus.QUERY_PROCESSED.value,
                "error_message": None
            })
            
            self.logger.info(f"Query processed successfully. Stock picker query: {stock_picker_query}")
            return state
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            state.update({
                "error_message": f"Error processing query: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _discover_stocks_node(self, state: WorkflowState) -> WorkflowState:
        """Discover stocks based on the processed query."""
        try:
            self.logger.info("Discovering stocks...")
            
            # Get the stock picker query and processed query
            stock_picker_query = state.get("stock_picker_query")
            processed_query = state.get("processed_query")
            
            if not stock_picker_query:
                raise ValueError("No stock picker query available")
            
            # Calculate stock discovery limit based on iteration and config
            iteration = state.get("iteration_count", 0)
            base_limit = self.config.base_stock_limit
            iteration_increase = self.config.iteration_stock_increase
            
            # Ensure we discover significantly more stocks than we'll retain
            # This ensures the product bundler has a good selection to choose from
            discovery_limit = base_limit + (iteration * iteration_increase)
            
            # Cap at maximum allowed
            discovery_limit = min(discovery_limit, self.config.max_stocks_per_iteration)
            
            # Ensure minimum discovery for good selection
            discovery_limit = max(discovery_limit, self.config.max_stocks_for_product * 2)
            
            # Use limit from processed query if available
            if processed_query and processed_query.get('limit'):
                discovery_limit = max(discovery_limit, processed_query['limit'] * 2)
            
            self.logger.info(f"Discovering {discovery_limit} stocks (iteration {iteration})")
            
            # Discover stocks using the stock picker agent with processed query data
            discovered_stocks = self.stock_picker.pick_stocks(
                stock_picker_query, 
                limit=discovery_limit,
                processed_query=processed_query
            )
            
            if not discovered_stocks:
                raise ValueError("No stocks discovered")
            
            # Log discovery results
            self.logger.info(f"Discovered {len(discovered_stocks)} stocks")
            self.logger.info(f"Discovery limit was {discovery_limit}, will retain max {self.config.max_stocks_for_product}")
            
            # Update state
            state.update({
                "discovered_stocks": discovered_stocks,
                "workflow_status": WorkflowStatus.STOCKS_DISCOVERED.value,
                "error_message": None
            })
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error discovering stocks: {e}")
            state.update({
                "error_message": f"Error discovering stocks: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _analyze_stocks_node(self, state: WorkflowState) -> WorkflowState:
        """Analyze the discovered stocks using the analyzer agent with enhanced assessments."""
        try:
            self.logger.info("Analyzing stocks with comprehensive assessments...")
            
            # Get discovered stocks and processed query
            discovered_stocks = state.get("discovered_stocks")
            processed_query = state.get("processed_query")
            
            if not discovered_stocks:
                raise ValueError("No stocks to analyze")
            
            # Extract symbols for analysis
            symbols = [stock['symbol'] for stock in discovered_stocks]
            
            # Use the enhanced analyzer agent to perform analysis with assessments
            try:
                # Use the new analyze_tickers method that returns assessment data
                analysis_results = self.analyzer.analyze_tickers(
                    symbols, 
                    processed_query=processed_query
                )
                
                self.logger.info(f"Successfully analyzed {len(analysis_results)} stocks with assessments")
                
                # Log assessment statistics
                assessment_count = len([r for r in analysis_results if r.get('assessment')])
                summary_count = len([r for r in analysis_results if r.get('summary')])
                self.logger.info(f"Generated {assessment_count} comprehensive assessments")
                self.logger.info(f"Generated {summary_count} individual stock summaries")
                
                if assessment_count > 0:
                    # Log some assessment metrics
                    confidence_scores = []
                    suitability_scores = []
                    recommendation_scores = []
                    
                    for result in analysis_results:
                        assessment = result.get('assessment', {})
                        if assessment:
                            confidence_scores.append(assessment.get('confidence_score', {}).get('confidence_score', 0.5))
                            suitability_scores.append(assessment.get('suitability_score', {}).get('suitability_score', 0.5))
                            recommendation_scores.append(assessment.get('investment_recommendation', {}).get('score', 0.5))
                    
                    if confidence_scores:
                        avg_confidence = sum(confidence_scores) / len(confidence_scores)
                        self.logger.info(f"Average confidence score: {avg_confidence:.3f}")
                    
                    if suitability_scores:
                        avg_suitability = sum(suitability_scores) / len(suitability_scores)
                        self.logger.info(f"Average suitability score: {avg_suitability:.3f}")
                    
                    if recommendation_scores:
                        avg_recommendation = sum(recommendation_scores) / len(recommendation_scores)
                        self.logger.info(f"Average recommendation score: {avg_recommendation:.3f}")
                
                # Log summary statistics
                if summary_count > 0:
                    self.logger.info(f"Individual stock summaries generated for {summary_count}/{len(analysis_results)} stocks")
                    # Log a few example summaries
                    for i, result in enumerate(analysis_results[:3]):
                        symbol = result.get('symbol', 'Unknown')
                        summary = result.get('summary', '')
                        if summary and not summary.startswith("Summary generation failed") and summary != f"No summarizer available for {symbol}":
                            summary_preview = summary[:100] + "..." if len(summary) > 100 else summary
                            self.logger.info(f"Sample summary for {symbol}: {summary_preview}")
                
            except Exception as e:
                self.logger.warning(f"Enhanced analysis failed, falling back to individual analysis: {e}")
                
                # Fallback to individual analysis
                analysis_results = []
                for symbol in symbols:
                    try:
                        # Use the analyzer agent to analyze each stock with processed query data
                        analysis_result = self.analyzer.analyze_single_ticker(
                            symbol, 
                            processed_query=processed_query
                        )
                        
                        if analysis_result:
                            # Create basic assessment structure for fallback
                            from ..agents.analyzer_agent import StockAssessment
                            stock_assessment = StockAssessment(symbol, analysis_result, processed_query)
                            assessment_data = stock_assessment.to_dict()
                            analysis_results.append(assessment_data)
                        else:
                            # Fallback to simulated analysis if real analysis fails
                            simulated_analysis = self._simulate_stock_analysis(symbol, discovered_stocks, processed_query)
                            analysis_results.append(simulated_analysis)
                            
                    except Exception as e2:
                        self.logger.warning(f"Error analyzing {symbol}: {e2}")
                        # Fallback to simulated analysis
                        simulated_analysis = self._simulate_stock_analysis(symbol, discovered_stocks, processed_query)
                        analysis_results.append(simulated_analysis)
            
            # Log analysis results
            self.logger.info(f"Analyzed {len(analysis_results)} stocks")
            self.logger.info(f"Analysis complete with assessments, ready for product creation")
            
            # Update state
            state.update({
                "analysis_results": analysis_results,
                "workflow_status": WorkflowStatus.ANALYSIS_COMPLETE.value,
                "error_message": None
            })
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error analyzing stocks: {e}")
            state.update({
                "error_message": f"Error analyzing stocks: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _create_product_node(self, state: WorkflowState) -> WorkflowState:
        """Create structured product from analysis results using the product bundler agent."""
        try:
            self.logger.info("Creating structured product...")
            
            # Get analysis results and processed query
            analysis_results = state.get("analysis_results")
            processed_query = state.get("processed_query", {})
            
            if not analysis_results:
                raise ValueError("No analysis results available")
            
            # Get user preferences from processed query
            user_preferences = {
                'risk_tolerance': processed_query.get('risk_tolerance'),
                'investment_horizon': processed_query.get('investment_horizon'),
                'capital_amount': processed_query.get('capital_amount'),
                'esg_focus': processed_query.get('esg_focus'),
                'dividend_focus': processed_query.get('dividend_focus'),
                'growth_focus': processed_query.get('growth_focus'),
                'value_focus': processed_query.get('value_focus'),
                'sector': processed_query.get('sector'),
                'market_cap_range': processed_query.get('market_cap_range'),
                'market': processed_query.get('market'),
                'country': processed_query.get('country')
            }
            
            # Use the product bundler agent to create the product with processed query data
            product_bundle = self.product_bundler.bundle_product(
                analysis_results, 
                user_preferences,
                processed_query
            )
            
            if not product_bundle.get("success"):
                raise ValueError(f"Failed to create product: {product_bundle.get('error')}")
            
            # Log product creation results
            product = product_bundle.get("product", {})
            components = product.get("components", [])
            self.logger.info(f"Product created with {len(components)} components")
            self.logger.info(f"Product type: {product.get('product_type', 'N/A')}")
            self.logger.info(f"Notional amount: ${product.get('notional_amount', 0):,.2f}")
            self.logger.info(f"Maturity date: {product.get('maturity_date', 'N/A')}")
            
            # Verify we have a good selection (more discovered than retained)
            discovered_count = len(state.get("discovered_stocks", []))
            retained_count = len(components)
            
            self.logger.info(f"Stock selection: {discovered_count} discovered, {retained_count} retained")
            
            if retained_count >= discovered_count:
                self.logger.warning(f"Warning: Retained {retained_count} stocks from {discovered_count} discovered")
            
            # Update state
            state.update({
                "product_bundle": product_bundle,
                "workflow_status": WorkflowStatus.PRODUCT_CREATED.value,
                "error_message": None
            })
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error creating product: {e}")
            state.update({
                "error_message": f"Error creating product: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _get_user_feedback_node(self, state: WorkflowState) -> WorkflowState:
        """Get user feedback on the created product."""
        try:
            self.logger.info("Getting user feedback...")
            
            # Check if we should auto-accept based on iteration count
            iteration = state.get("iteration_count", 0)
            if iteration >= self.config.auto_accept_after_iterations:
                self.logger.info(f"Auto-accepting after {iteration} iterations")
                user_satisfied = True
                user_feedback = "Auto-accepted after maximum iterations"
            else:
                # In a real implementation, this would present the summary to the user
                # and wait for their feedback. For demo purposes, we'll simulate user satisfaction
                user_satisfied = True  # Simulate user being satisfied
                user_feedback = "Product looks good, proceed with creation."
            
            # Update state
            state.update({
                "user_feedback": user_feedback,
                "user_satisfied": user_satisfied,
                "workflow_status": WorkflowStatus.USER_REVIEW.value,
                "error_message": None
            })
            
            self.logger.info("User feedback received")
            return state
            
        except Exception as e:
            self.logger.error(f"Error getting user feedback: {e}")
            state.update({
                "error_message": f"Error getting user feedback: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _handle_user_feedback_node(self, state: WorkflowState) -> WorkflowState:
        """Handle user feedback and modify the workflow accordingly."""
        try:
            self.logger.info("Handling user feedback...")
            
            # Increment iteration count
            current_iteration = state.get("iteration_count", 0)
            new_iteration = current_iteration + 1
            
            # Check if we've exceeded max iterations
            if new_iteration >= self.config.max_iterations:
                self.logger.warning(f"Maximum iterations ({self.config.max_iterations}) reached")
                state.update({
                    "workflow_status": WorkflowStatus.COMPLETED.value,
                    "error_message": f"Maximum iterations reached. Final product created."
                })
                return state
            
            # Update state for next iteration
            state.update({
                "iteration_count": new_iteration,
                "discovered_stocks": None,  # Clear for new discovery
                "analysis_results": None,   # Clear for new analysis
                "product_bundle": None,     # Clear for new product
                "user_feedback": None,      # Clear feedback
                "user_satisfied": None,     # Clear satisfaction
                "workflow_status": WorkflowStatus.INITIALIZED.value
            })
            
            self.logger.info(f"Starting iteration {new_iteration}")
            return state
            
        except Exception as e:
            self.logger.error(f"Error handling user feedback: {e}")
            state.update({
                "error_message": f"Error handling user feedback: {str(e)}",
                "workflow_status": WorkflowStatus.ERROR.value
            })
            return state
    
    def _handle_error_node(self, state: WorkflowState) -> WorkflowState:
        """Handle errors in the workflow."""
        self.logger.error(f"Workflow error: {state.get('error_message')}")
        state.update({
            "workflow_status": WorkflowStatus.ERROR.value
        })
        return state
    
    def _should_continue_workflow(self, state: WorkflowState) -> str:
        """Determine the next step based on user feedback and iteration count."""
        
        # Check for errors
        if state.get("error_message"):
            return "error"
        
        # Check if user is satisfied
        user_satisfied = state.get("user_satisfied", False)
        if user_satisfied:
            return "complete"
        
        # Check iteration limits
        current_iteration = state.get("iteration_count", 0)
        if current_iteration >= self.config.max_iterations:
            return "complete"
        
        # Continue with modifications
        return "continue"
    
    def _simulate_stock_analysis(self, symbol: str, discovered_stocks: List[Dict[str, Any]], processed_query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Simulate stock analysis results with comprehensive assessments for demo purposes when real analysis fails."""
        
        # Create simulated analysis data with proper structure
        simulated_analysis = {
            "symbol": symbol,
            "analysis": {
                "signals": {
                    "rsi": "NEUTRAL",
                    "macd": "BUY",
                    "bollinger_bands": "ABOVE",
                    "sma": "ABOVE",
                    "overall": "BUY"
                },
                "metrics": {
                    "market_cap": 1000000000 + (hash(symbol) % 5000000000),
                    "pe_ratio": 15.0 + (hash(symbol) % 20),
                    "dividend_yield": 0.02 + (hash(symbol) % 5) / 100,
                    "beta": 1.0 + (hash(symbol) % 10) / 10
                },
                "risk": {
                    "sharpe_ratio": 1.2 + (hash(symbol) % 10) / 10,
                    "var_95": 0.02 + (hash(symbol) % 5) / 100,
                    "volatility": 0.15 + (hash(symbol) % 10) / 100,
                    "max_drawdown": 0.15 + (hash(symbol) % 10) / 100
                },
                "sector": {
                    "sector": "Technology",
                    "industry": "Software",
                    "sector_performance": 0.08
                },
                "regime": {
                    "current_regime": "BULL_MARKET",
                    "regime_probability": 0.7
                },
                "stress": {
                    "stress_score": 0.3 + (hash(symbol) % 5) / 10,
                    "scenario_analysis": "POSITIVE"
                },
                "ensemble": {
                    "ensemble_score": 0.75 + (hash(symbol) % 20) / 100,
                    "model_agreement": 0.8
                },
                "advanced": {
                    "momentum_score": 0.6 + (hash(symbol) % 30) / 100,
                    "quality_score": 0.7 + (hash(symbol) % 20) / 100
                }
            },
            "plot": None,
            "source": "simulated"
        }
        
        # Create comprehensive assessment using StockAssessment class
        try:
            from ..agents.analyzer_agent import StockAssessment
            stock_assessment = StockAssessment(symbol, simulated_analysis, processed_query)
            assessment_data = stock_assessment.to_dict()
            return assessment_data
        except Exception as e:
            self.logger.warning(f"Error creating assessment for {symbol}: {e}")
            # Fallback to basic structure
            return {
                "symbol": symbol,
                "analysis": simulated_analysis,
                "assessment": {
                    "investment_recommendation": {
                        "recommendation": "BUY",
                        "strength": "MEDIUM",
                        "score": 0.65,
                        "signal_breakdown": {
                            "overall_signal": "BUY",
                            "rsi_signal": "NEUTRAL",
                            "macd_signal": "BUY",
                            "signal_score": 0.7
                        },
                        "technical_factors": {
                            "sharpe_ratio": 1.2,
                            "ensemble_score": 0.75,
                            "momentum_score": 0.6,
                            "quality_score": 0.7,
                            "model_agreement": 0.8
                        }
                    },
                    "risk_assessment": {
                        "risk_level": "MODERATE",
                        "risk_score": 0.45,
                        "risk_factors": ["MODERATE_VOLATILITY", "LOW_VAR", "GOOD_SHARPE"],
                        "key_metrics": {
                            "sharpe_ratio": 1.2,
                            "var_95": 0.02,
                            "volatility": 0.15,
                            "max_drawdown": 0.15,
                            "stress_score": 0.3
                        },
                        "market_context": {
                            "current_regime": "BULL_MARKET",
                            "regime_probability": 0.7,
                            "scenario_analysis": "POSITIVE"
                        }
                    },
                    "confidence_score": {
                        "confidence_score": 0.72,
                        "confidence_level": "MEDIUM",
                        "factors": {
                            "ensemble_score": 0.75,
                            "model_agreement": 0.8,
                            "signal_consistency": 0.67,
                            "momentum_quality": 0.6,
                            "overall_quality": 0.7
                        }
                    },
                    "suitability_score": {
                        "suitability_score": 0.68,
                        "suitability_level": "GOOD",
                        "risk_suitability": 0.7,
                        "recommendation_suitability": 0.65,
                        "confidence_suitability": 0.72,
                        "user_preferences": processed_query or {}
                    },
                    "insights": {
                        "technical_insights": ["Technical indicators suggest positive momentum"],
                        "fundamental_insights": ["Reasonable valuation metrics"],
                        "risk_insights": ["Moderate risk profile suitable for most investors"],
                        "market_insights": ["Currently in bull market regime"],
                        "investment_insights": ["Good model agreement suggests reliable predictions"]
                    },
                    "assessment_timestamp": datetime.now().isoformat(),
                    "assessment_version": "2.0"
                },
                "processed_query": processed_query
            }
    
    def _create_product_summary(self, state: WorkflowState) -> str:
        """Create a summary of the product for user review."""
        
        product_bundle = state.get("product_bundle", {})
        if not product_bundle:
            return "No product available for review."
        
        product = product_bundle.get("product", {})
        stock_selection = product_bundle.get("stock_selection", {})
        
        summary = f"""
# Product Summary for Review

## Product Details
- **Product ID**: {product.get('product_id', 'N/A')}
- **Product Type**: {product.get('product_type', 'N/A')}
- **Product Name**: {product.get('product_name', 'N/A')}
- **Notional Amount**: ${product.get('notional_amount', 0):,.2f}

## Stock Selection Summary
- **Total Candidates**: {stock_selection.get('total_candidates', 0)}
- **Selected Stocks**: {stock_selection.get('selected_count', 0)}
- **Selection Efficiency**: {stock_selection.get('selection_efficiency', 0):.1%}

## Risk Profile
- **Risk Level**: {product.get('risk_profile', {}).get('risk_level', 'N/A')}
- **Expected Return**: {product.get('performance_metrics', {}).get('expected_return', 0):.2%}
- **Portfolio Score**: {product.get('performance_metrics', {}).get('portfolio_score', 0):.2f}

## Components ({len(product.get('components', []))} stocks)
"""
        
        components = product.get('components', [])
        for i, comp in enumerate(components[:5], 1):  # Show first 5
            summary += f"""
### Component {i}
- **Asset**: {comp.get('underlying_asset', 'N/A')}
- **Weight**: {comp.get('weight', 0):.2%}
- **Score**: {comp.get('score', 0):.2f}
- **Reason**: {comp.get('retention_reason', 'N/A')}
"""
        
        if len(components) > 5:
            summary += f"- ... and {len(components) - 5} more components\n"
        
        # Add CDM compliance
        cdm_info = product_bundle.get('cdm_compliance', {})
        summary += f"""
## CDM Compliance
- **Standard**: {cdm_info.get('standard', 'N/A')}
- **Compliance Level**: {cdm_info.get('compliance_level', 'N/A')}

## User Feedback Options
1. **Accept**: Proceed with product creation
2. **Modify**: Request changes to the product
3. **Restart**: Start over with different criteria
"""
        
        return summary
    
    def run(self, user_query: str) -> Dict[str, Any]:
        """
        Run the complete workflow.
        
        Args:
            user_query: The user's investment request
            
        Returns:
            Dictionary containing the final state and results
        """
        try:
            # Initialize state
            initial_state = WorkflowState(
                user_query=user_query,
                processed_query=None,
                stock_picker_query=None,
                discovered_stocks=None,
                analysis_results=None,
                product_bundle=None,
                user_feedback=None,
                user_satisfied=None,
                iteration_count=0,
                max_iterations=self.config.max_iterations,
                error_message=None,
                workflow_status=WorkflowStatus.INITIALIZED.value
            )
            
            # Run the workflow
            self.logger.info("Starting structured equity workflow...")
            final_state = self.workflow.invoke(initial_state)
            
            # Create result summary
            result = {
                "success": final_state.get("workflow_status") == WorkflowStatus.COMPLETED.value,
                "final_state": final_state,
                "product_bundle": final_state.get("product_bundle"),
                "iterations": final_state.get("iteration_count", 0),
                "error_message": final_state.get("error_message"),
                "workflow_status": final_state.get("workflow_status")
            }
            
            self.logger.info(f"Workflow completed with status: {final_state.get('workflow_status')}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error running workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_status": WorkflowStatus.ERROR.value
            } 

class StockPickerWorkflow:
    """
    Simple LangGraph-based state machine for stock picking.
    """
    class StockPickerState(TypedDict):
        user_query: str
        processed_query: Optional[Dict[str, Any]]
        stock_picker_query: Optional[str]
        discovered_stocks: Optional[List[Dict[str, Any]]]
        error_message: Optional[str]
        workflow_status: str

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm = GAssistLLM()
        self.query_processor = QueryProcessorAgent(llm=self.llm)
        self.stock_picker = StockPickerAgent(llm=self.llm)
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:
        workflow = StateGraph(self.StockPickerState)
        workflow.add_node("process_query", self._process_query_node)
        workflow.add_node("pick_stocks", self._pick_stocks_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.set_entry_point("process_query")
        workflow.add_edge("process_query", "pick_stocks")
        workflow.add_edge("pick_stocks", END)
        workflow.add_edge("handle_error", END)
        return workflow.compile()

    def _process_query_node(self, state: dict) -> dict:
        try:
            self.logger.info("Processing user query for stock picking...")
            processed_query = self.query_processor.process_query(state["user_query"])
            stock_picker_query = self.query_processor.to_stock_picker_query(processed_query)
            state.update({
                "processed_query": processed_query.__dict__,
                "stock_picker_query": stock_picker_query,
                "workflow_status": "query_processed",
                "error_message": None
            })
            return state
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            state.update({
                "error_message": f"Error processing query: {str(e)}",
                "workflow_status": "error"
            })
            return state

    def _pick_stocks_node(self, state: dict) -> dict:
        try:
            self.logger.info("Picking stocks based on processed query...")
            stock_picker_query = state.get("stock_picker_query")
            processed_query = state.get("processed_query")
            if not stock_picker_query:
                raise ValueError("No stock picker query available")
            limit = processed_query.get('limit', self.config.base_stock_limit) if processed_query else self.config.base_stock_limit
            discovered_stocks = self.stock_picker.pick_stocks(
                stock_picker_query,
                limit=limit,
                processed_query=processed_query
            )
            state.update({
                "discovered_stocks": discovered_stocks,
                "workflow_status": "stocks_picked",
                "error_message": None
            })
            return state
        except Exception as e:
            self.logger.error(f"Error picking stocks: {e}")
            state.update({
                "error_message": f"Error picking stocks: {str(e)}",
                "workflow_status": "error"
            })
            return state

    def _handle_error_node(self, state: dict) -> dict:
        self.logger.error(f"Workflow error: {state.get('error_message')}")
        state["workflow_status"] = "error"
        return state

    def run(self, user_query: str) -> Dict[str, Any]:
        try:
            initial_state = self.StockPickerState(
                user_query=user_query,
                processed_query=None,
                stock_picker_query=None,
                discovered_stocks=None,
                error_message=None,
                workflow_status="initialized"
            )
            self.logger.info("Starting stock picker workflow...")
            final_state = self.workflow.invoke(initial_state)
            result = {
                "success": final_state.get("workflow_status") == "stocks_picked",
                "final_state": final_state,
                "discovered_stocks": final_state.get("discovered_stocks"),
                "error_message": final_state.get("error_message"),
                "workflow_status": final_state.get("workflow_status")
            }
            self.logger.info(f"Workflow completed with status: {final_state.get('workflow_status')}")
            return result
        except Exception as e:
            self.logger.error(f"Error running workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_status": "error"
            } 

class StockAnalyzerWorkflow:
    """
    Simple workflow: user query -> query processor -> analyzer -> summarizer -> return plot and summary.
    """
    class State(TypedDict):
        user_query: str
        processed_query: Optional[Dict[str, Any]]
        stock_symbol: Optional[str]
        analysis_result: Optional[Dict[str, Any]]
        summary: Optional[str]
        plot: Optional[Any]
        error_message: Optional[str]
        workflow_status: str

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm = GAssistLLM()
        self.query_processor = QueryProcessorAgent(llm=self.llm)
        self.analyzer = AnalyzerAgent(llm=self.llm)
        self.summarizer = SummarizerAgent(llm=self.llm)
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> StateGraph:
        workflow = StateGraph(self.State)
        workflow.add_node("process_query", self._process_query_node)
        workflow.add_node("analyze_stock", self._analyze_stock_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.set_entry_point("process_query")
        workflow.add_edge("process_query", "analyze_stock")
        workflow.add_edge("analyze_stock", "summarize")
        workflow.add_edge("summarize", END)
        workflow.add_edge("handle_error", END)
        return workflow.compile()

    def _process_query_node(self, state: dict) -> dict:
        try:
            processed_query = self.query_processor.process_query(state["user_query"])
            # For single stock, expect a symbol in processed_query or user_query
            symbol = processed_query.sector or processed_query.original_query  # fallback to original query if no symbol
            state.update({
                "processed_query": processed_query.__dict__,
                "stock_symbol": symbol,
                "workflow_status": "query_processed",
                "error_message": None
            })
            return state
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            state.update({
                "error_message": f"Error processing query: {str(e)}",
                "workflow_status": "error"
            })
            return state

    def _analyze_stock_node(self, state: dict) -> dict:
        try:
            symbol = state.get("stock_symbol")
            if not symbol:
                raise ValueError("No stock symbol found in state.")
            analysis_result = self.analyzer.analyze_single_ticker(symbol, processed_query=state.get("processed_query"))
            plot = None
            if analysis_result and "analysis" in analysis_result and "plot" in analysis_result["analysis"]:
                plot = analysis_result["analysis"]["plot"]
            state.update({
                "analysis_result": analysis_result,
                "plot": plot,
                "workflow_status": "analyzed",
                "error_message": None
            })
            return state
        except Exception as e:
            self.logger.error(f"Error analyzing stock: {e}")
            state.update({
                "error_message": f"Error analyzing stock: {str(e)}",
                "workflow_status": "error"
            })
            return state

    def _summarize_node(self, state: dict) -> dict:
        try:
            summary = self.summarizer.generate_stock_summary(state["analysis_result"])
            state.update({
                "summary": summary,
                "workflow_status": "summarized",
                "error_message": None
            })
            return state
        except Exception as e:
            self.logger.error(f"Error summarizing: {e}")
            state.update({
                "error_message": f"Error summarizing: {str(e)}",
                "workflow_status": "error"
            })
            return state

    def _handle_error_node(self, state: dict) -> dict:
        self.logger.error(f"Workflow error: {state.get('error_message')}")
        state["workflow_status"] = "error"
        return state

    def run(self, user_query: str) -> Dict[str, Any]:
        try:
            initial_state = self.State(
                user_query=user_query,
                processed_query=None,
                stock_symbol=None,
                analysis_result=None,
                summary=None,
                plot=None,
                error_message=None,
                workflow_status="initialized"
            )
            self.logger.info("Starting stock analyzer workflow...")
            final_state = self.workflow.invoke(initial_state)
            result = {
                "success": final_state.get("workflow_status") == "summarized",
                "final_state": final_state,
                "summary": final_state.get("summary"),
                "plot": final_state.get("plot"),
                "error_message": final_state.get("error_message"),
                "workflow_status": final_state.get("workflow_status")
            }
            self.logger.info(f"Workflow completed with status: {final_state.get('workflow_status')}")
            return result
        except Exception as e:
            self.logger.error(f"Error running workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_status": "error"
            } 