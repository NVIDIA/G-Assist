#!/usr/bin/env python3
"""
Gradio Interface for Stock Picker Application

This provides a web-based interface for the stock picking system with:
- Interactive query input
- Step-by-step workflow visualization
- Human-in-the-loop capabilities
- Real-time agent outputs
"""

import os
import json
import gradio as gr
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[DEBUG] Environment variables loaded from .env file")
except ImportError:
    print("[DEBUG] python-dotenv not available, using system environment variables")

# Import our application components
from src.workflow.state_machine import StructuredEquityWorkflow, WorkflowConfig
from src.agents.query_processor_agent import QueryProcessorAgent
from src.agents.stock_picker_agent import StockPickerAgent
from src.agents.analyzer_agent import AnalyzerAgent
from src.agents.product_bundler_agent import ProductBundlerAgent
from src.tools.stock_selection_tool import StockSelectionTool

class StockPickerGradioApp:
    """Gradio interface for the stock picking application."""
    
    def __init__(self):
        """Initialize the Gradio application."""
        self.workflow = None
        self.current_state = {}
        self.workflow_history = []
        
        # Get environment variables for configuration
        self.llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.hf_api_key = os.getenv("HF_API_KEY")
        
        # Model configuration
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        self.hf_model = os.getenv("HF_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        
        # MCP server configuration (separate from LLM provider)
        self.mcp_provider = os.getenv("MCP_PROVIDER", "huggingface").lower()
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "https://tonic-stock-predictions.hf.space/gradio_api/mcp/sse")
        
        # Debug logging
        print(f"[DEBUG] LLM_PROVIDER: {self.llm_provider}")
        print(f"[DEBUG] Anthropic Key: {self.anthropic_api_key[:10] if self.anthropic_api_key else 'None'}...")
        print(f"[DEBUG] OpenAI Key: {self.openai_api_key[:10] if self.openai_api_key else 'None'}...")
        print(f"[DEBUG] HF Key: {self.hf_api_key[:10] if self.hf_api_key else 'None'}...")
        print(f"[DEBUG] MCP Server URL: {self.mcp_server_url}")
        
        # Check if LLM is available
        self.use_llm = self._check_llm_availability()
        
        # Check if MCP is available
        self.use_mcp = self._check_mcp_availability()
        
        print(f"[DEBUG] Use LLM: {self.use_llm}")
        print(f"[DEBUG] Use MCP: {self.use_mcp}")
        print(f"[DEBUG] Selected LLM Provider: {self.llm_provider}")
        
        # Initialize workflow
        self._initialize_workflow()
    
    def _check_llm_availability(self) -> bool:
        """Check if LLM is available based on provider and API key."""
        # Helper function to check if API key is valid (not placeholder)
        def is_valid_api_key(key):
            return key and key != "your_openai_api_key_here" and key != "your_anthropic_api_key_here" and key != "your_huggingface_api_key_here"
        
        # Check if LLM_PROVIDER was explicitly set in environment (not default)
        explicit_provider = os.getenv("LLM_PROVIDER")
        provider_was_explicitly_set = explicit_provider and explicit_provider.lower() in ["anthropic", "openai", "huggingface"]
        
        # If provider was explicitly set and has valid API key, use it
        if provider_was_explicitly_set:
            if self.llm_provider == "anthropic" and is_valid_api_key(self.anthropic_api_key):
                return True
            elif self.llm_provider == "openai" and is_valid_api_key(self.openai_api_key):
                return True
            elif self.llm_provider == "huggingface" and is_valid_api_key(self.hf_api_key):
                return True
            else:
                print(f"[DEBUG] Explicitly configured provider '{self.llm_provider}' has no valid API key, falling back to auto-detection")
        
        # Auto-detect which provider has a valid API key as fallback
        if is_valid_api_key(self.anthropic_api_key):
            self.llm_provider = "anthropic"
            return True
        elif is_valid_api_key(self.openai_api_key):
            self.llm_provider = "openai"
            return True
        elif is_valid_api_key(self.hf_api_key):
            self.llm_provider = "huggingface"
            return True
        return False
    
    def _check_mcp_availability(self) -> bool:
        """Check if MCP server is available."""
        # MCP server requires HuggingFace API key regardless of LLM provider
        if self.hf_api_key and self.hf_api_key != "your_huggingface_api_key_here":
            self.mcp_provider = "huggingface"
            return True
        return False
    
    def _initialize_workflow(self):
        """Initialize the workflow with current configuration."""
        try:
            config = WorkflowConfig(
                base_stock_limit=20,
                max_stocks_per_iteration=50,
                max_stocks_for_product=15,
                iteration_stock_increase=10,
                max_iterations=3
            )
            
            # Use the appropriate API key based on the detected LLM provider
            if self.llm_provider == "anthropic":
                primary_api_key = self.anthropic_api_key
            elif self.llm_provider == "huggingface":
                primary_api_key = self.hf_api_key
            else:
                primary_api_key = self.openai_api_key
            
            print(f"[DEBUG] Using {self.llm_provider} as LLM provider with key: {primary_api_key[:10] if primary_api_key else 'None'}...")
            
            self.workflow = StructuredEquityWorkflow(
                openai_api_key=primary_api_key,  # Use the detected LLM provider's key
                config=config,
                use_llm=self.use_llm,
                llm_provider=self.llm_provider,
                anthropic_api_key=self.anthropic_api_key,
                hf_api_key=self.hf_api_key,  # Always pass HF key for MCP server
                openai_model=self.openai_model,
                anthropic_model=self.anthropic_model,
                hf_model=self.hf_model,
                mcp_server_url=self.mcp_server_url,  # Pass MCP server URL
                use_mcp=self.use_mcp  # Pass MCP availability flag
            )
        except Exception as e:
            print(f"Error initializing workflow: {e}")
            self.workflow = None
    
    def process_query_step(self, user_query: str) -> Dict[str, Any]:
        """Process the user query and return structured data."""
        if not self.workflow:
            return {"error": "Workflow not initialized"}
        
        try:
            # Process query using the query processor agent
            processed_query = self.workflow.query_processor.process_query(user_query)
            stock_picker_query = self.workflow.query_processor.to_stock_picker_query(processed_query)
            
            # Update current state
            self.current_state = {
                "user_query": user_query,
                "processed_query": processed_query.__dict__,
                "stock_picker_query": stock_picker_query,
                "step": "query_processed"
            }
            
            return {
                "success": True,
                "processed_query": processed_query.__dict__,
                "stock_picker_query": stock_picker_query,
                "message": "Query processed successfully"
            }
        except Exception as e:
            return {"error": f"Error processing query: {str(e)}"}
    
    def discover_stocks_step(self, user_feedback: str = "") -> Dict[str, Any]:
        """Discover stocks based on the processed query."""
        if not self.workflow or "processed_query" not in self.current_state:
            return {"error": "No processed query available"}
        
        try:
            # Get the stock picker query and processed query
            stock_picker_query = self.current_state.get("stock_picker_query")
            processed_query = self.current_state.get("processed_query")
            
            # Apply user feedback if provided
            if user_feedback:
                stock_picker_query = f"{stock_picker_query} {user_feedback}"
            
            # Calculate discovery limit
            discovery_limit = 30  # Default limit
            
            # Discover stocks
            discovered_stocks = self.workflow.stock_picker.pick_stocks(
                stock_picker_query,
                limit=discovery_limit,
                processed_query=processed_query
            )
            
            # Update current state
            self.current_state.update({
                "discovered_stocks": discovered_stocks,
                "step": "stocks_discovered"
            })
            
            return {
                "success": True,
                "discovered_stocks": discovered_stocks,
                "count": len(discovered_stocks),
                "message": f"Discovered {len(discovered_stocks)} stocks"
            }
        except Exception as e:
            return {"error": f"Error discovering stocks: {str(e)}"}
    
    def analyze_stocks_step(self, selected_stocks: List[str]) -> Dict[str, Any]:
        """Analyze the selected stocks."""
        if not self.workflow or "discovered_stocks" not in self.current_state:
            return {"error": "No discovered stocks available"}
        
        try:
            discovered_stocks = self.current_state.get("discovered_stocks", [])
            processed_query = self.current_state.get("processed_query", {})
            
            # Filter stocks based on user selection
            if selected_stocks:
                filtered_stocks = [
                    stock for stock in discovered_stocks 
                    if stock['symbol'] in selected_stocks
                ]
            else:
                # Use all discovered stocks if none selected
                filtered_stocks = discovered_stocks[:10]  # Limit to 10 for analysis
            
            # Extract symbols for analysis
            symbols = [stock['symbol'] for stock in filtered_stocks]
            
            # Analyze stocks
            analysis_results = self.workflow.analyzer.analyze_tickers(
                symbols,
                processed_query=processed_query
            )
            
            # Update current state
            self.current_state.update({
                "analysis_results": analysis_results,
                "step": "analysis_complete"
            })
            
            return {
                "success": True,
                "analysis_results": analysis_results,
                "count": len(analysis_results),
                "message": f"Analyzed {len(analysis_results)} stocks"
            }
        except Exception as e:
            return {"error": f"Error analyzing stocks: {str(e)}"}
    
    def create_product_step(self, user_preferences: str = "") -> Dict[str, Any]:
        """Create a structured product from the analysis results."""
        if not self.workflow or "analysis_results" not in self.current_state:
            return {"error": "No analysis results available"}
        
        try:
            analysis_results = self.current_state.get("analysis_results", [])
            processed_query = self.current_state.get("processed_query", {})
            
            # Create product bundle
            product_bundle = self.workflow.product_bundler.bundle_product(
                analysis_results,
                processed_query=processed_query
            )
            
            # Update current state
            self.current_state.update({
                "product_bundle": product_bundle,
                "step": "product_created"
            })
            
            return {
                "success": True,
                "product_bundle": product_bundle,
                "message": "Product created successfully"
            }
        except Exception as e:
            return {"error": f"Error creating product: {str(e)}"}
    
    def format_processed_query(self, processed_query: Dict[str, Any]) -> str:
        """Format processed query for display."""
        if not processed_query:
            return "No processed query data"
        
        lines = ["**Processed Query Data:**"]
        for key, value in processed_query.items():
            if value is not None:
                if isinstance(value, bool):
                    value = "Yes" if value else "No"
                elif isinstance(value, float):
                    value = f"${value:,.2f}" if key == "capital_amount" else f"{value:.2f}"
                lines.append(f"• **{key.replace('_', ' ').title()}**: {value}")
        
        return "\n".join(lines)
    
    def format_discovered_stocks(self, discovered_stocks: List[Dict[str, Any]]) -> str:
        """Format discovered stocks for display."""
        if not discovered_stocks:
            return "No stocks discovered"
        
        lines = [f"**Discovered Stocks ({len(discovered_stocks)}):**"]
        for i, stock in enumerate(discovered_stocks[:10], 1):  # Show first 10
            lines.append(f"{i}. **{stock['symbol']}**: {stock['company_name']}")
            if stock.get('sector'):
                lines.append(f"   Sector: {stock['sector']}")
            if stock.get('market_cap'):
                lines.append(f"   Market Cap: ${stock['market_cap']:,.0f}")
        
        if len(discovered_stocks) > 10:
            lines.append(f"\n... and {len(discovered_stocks) - 10} more stocks")
        
        return "\n".join(lines)
    
    def format_analysis_results(self, analysis_results: List[Dict[str, Any]]) -> str:
        """Format analysis results for display with individual stock summaries."""
        if not analysis_results:
            return "No analysis results available"
        
        lines = [f"**Analysis Results ({len(analysis_results)} stocks):**"]
        
        for i, result in enumerate(analysis_results[:5], 1):
            symbol = result.get('symbol', 'Unknown')
            summary = result.get('summary', '')
            assessment = result.get('assessment', {})
            
            lines.append(f"\n### {i}. {symbol}")
            
            # Display individual stock summary if available
            if summary and summary != f"No summarizer available for {symbol}" and not summary.startswith("Summary generation failed"):
                lines.append("#### 📝 Individual Stock Summary")
                lines.append(summary)
                lines.append("")
            
            # Display key assessment metrics
            if assessment:
                lines.append("#### 📊 Key Metrics")
                investment_rec = assessment.get('investment_recommendation', {})
                risk_assessment = assessment.get('risk_assessment', {})
                
                if investment_rec:
                    lines.append(f"• **Recommendation**: {investment_rec.get('recommendation', 'N/A')}")
                    lines.append(f"• **Score**: {investment_rec.get('score', 0):.1%}")
                
                if risk_assessment:
                    lines.append(f"• **Risk Level**: {risk_assessment.get('risk_level', 'N/A')}")
                    lines.append(f"• **Risk Score**: {risk_assessment.get('risk_score', 0):.1%}")
            
            lines.append("---")
        
        if len(analysis_results) > 5:
            lines.append(f"\n... and {len(analysis_results) - 5} more analyzed stocks with individual summaries")
        
        return "\n".join(lines)
    
    def format_enhanced_summaries(self, product_bundle: Dict[str, Any]) -> str:
        """Format enhanced summaries for display in a dedicated section."""
        if not product_bundle or not product_bundle.get("success"):
            return "No enhanced summaries available"
        
        lines = ["## 📝 Enhanced AI-Generated Summaries\n"]
        
        # Executive Summary
        executive_summary = product_bundle.get("executive_summary", "")
        if executive_summary:
            lines.append("### 🎯 Executive Summary")
            lines.append(executive_summary)
            lines.append("")
        
        # Portfolio Summary
        product_summary = product_bundle.get("product_summary", "")
        if product_summary:
            lines.append("### 📈 Portfolio Summary")
            lines.append(product_summary)
            lines.append("")
        
        # Risk Analysis Summary
        risk_summary = product_bundle.get("risk_summary", "")
        if risk_summary:
            lines.append("### ⚠️ Risk Analysis Summary")
            lines.append(risk_summary)
            lines.append("")
        
        # Investment Recommendation Summary
        recommendation_summary = product_bundle.get("recommendation_summary", "")
        if recommendation_summary:
            lines.append("### 💡 Investment Recommendation Summary")
            lines.append(recommendation_summary)
            lines.append("")
        
        # Individual Stock Assessments
        individual_assessments = product_bundle.get("individual_assessments", [])
        if individual_assessments:
            lines.append("### 🔍 Individual Stock Assessments")
            for i, assessment in enumerate(individual_assessments[:5], 1):  # Show first 5
                symbol = assessment.get('symbol', 'Unknown')
                enhanced_summary = assessment.get('enhanced_summary', '')
                original_assessment = assessment.get('original_assessment', '')
                
                lines.append(f"#### {i}. {symbol}")
                if enhanced_summary:
                    # Show the full enhanced summary
                    lines.append(enhanced_summary)
                elif original_assessment:
                    # Show the original assessment
                    lines.append(original_assessment)
                lines.append("")
            
            if len(individual_assessments) > 5:
                lines.append(f"... and {len(individual_assessments) - 5} more detailed assessments")
        
        # Assessment Metrics Summary
        assessment_summary = product_bundle.get("assessment_summary", {})
        if assessment_summary:
            lines.append("### 📊 Assessment Metrics Summary")
            lines.append(f"• **Total Assessments**: {assessment_summary.get('total_assessments', 0)}")
            lines.append(f"• **Average Confidence**: {assessment_summary.get('avg_confidence_score', 0):.1%}")
            lines.append(f"• **Average Suitability**: {assessment_summary.get('avg_suitability_score', 0):.1%}")
            lines.append(f"• **Average Recommendation Score**: {assessment_summary.get('avg_recommendation_score', 0):.1%}")
            
            # Risk Distribution
            risk_dist = assessment_summary.get('risk_distribution', {})
            if risk_dist:
                total = sum(risk_dist.values())
                if total > 0:
                    lines.append(f"\n**Risk Distribution**:")
                    lines.append(f"• Low Risk: {risk_dist.get('low', 0)} stocks ({risk_dist.get('low', 0)/total*100:.0f}%)")
                    lines.append(f"• Moderate Risk: {risk_dist.get('moderate', 0)} stocks ({risk_dist.get('moderate', 0)/total*100:.0f}%)")
                    lines.append(f"• High Risk: {risk_dist.get('high', 0)} stocks ({risk_dist.get('high', 0)/total*100:.0f}%)")
            
            # Recommendation Distribution
            rec_dist = assessment_summary.get('recommendation_distribution', {})
            if rec_dist:
                total = sum(rec_dist.values())
                if total > 0:
                    lines.append(f"\n**Recommendation Distribution**:")
                    lines.append(f"• Strong Buy: {rec_dist.get('strong_buy', 0)} stocks ({rec_dist.get('strong_buy', 0)/total*100:.0f}%)")
                    lines.append(f"• Buy: {rec_dist.get('buy', 0)} stocks ({rec_dist.get('buy', 0)/total*100:.0f}%)")
                    lines.append(f"• Hold: {rec_dist.get('hold', 0)} stocks ({rec_dist.get('hold', 0)/total*100:.0f}%)")
                    lines.append(f"• Sell: {rec_dist.get('sell', 0)} stocks ({rec_dist.get('sell', 0)/total*100:.0f}%)")
                    lines.append(f"• Strong Sell: {rec_dist.get('strong_sell', 0)} stocks ({rec_dist.get('strong_sell', 0)/total*100:.0f}%)")
        
        return "\n".join(lines)
    
    def format_product_bundle(self, product_bundle: Dict[str, Any]) -> str:
        """Format product bundle for display with all enhanced summaries."""
        if not product_bundle or not product_bundle.get("success"):
            return "No product bundle created"
        
        product = product_bundle.get("product", {})
        lines = []
        
        # Product Overview
        lines.append("## 🏗️ Structured Product Created")
        lines.append(f"• **Product ID**: {product.get('product_id', 'N/A')}")
        lines.append(f"• **Product Type**: {product.get('product_type', 'N/A')}")
        lines.append(f"• **Product Name**: {product.get('product_name', 'N/A')}")
        lines.append(f"• **Notional Amount**: ${product.get('notional_amount', 0):,.2f}")
        lines.append(f"• **Currency**: {product.get('currency', 'N/A')}")
        lines.append(f"• **Issue Date**: {product.get('issue_date', 'N/A')}")
        lines.append(f"• **Maturity Date**: {product.get('maturity_date', 'N/A')}")
        
        # Components
        components = product.get("components", [])
        if components:
            lines.append(f"\n### 📊 Components ({len(components)})")
            for i, component in enumerate(components[:5], 1):
                lines.append(f"{i}. {component.get('underlying_asset', 'N/A')}: {component.get('weight', 0):.1%}")
            if len(components) > 5:
                lines.append(f"... and {len(components) - 5} more components")
        
        # Risk profile
        risk_profile = product.get("risk_profile", {})
        if risk_profile:
            lines.append(f"\n### ⚠️ Risk Profile")
            for key, value in risk_profile.items():
                if isinstance(value, float):
                    lines.append(f"• {key.replace('_', ' ').title()}: {value:.4f}")
                else:
                    lines.append(f"• {key.replace('_', ' ').title()}: {value}")
        
        # Enhanced Summaries Section
        lines.append(f"\n## 📝 Enhanced AI-Generated Summaries")
        
        # Executive Summary
        executive_summary = product_bundle.get("executive_summary", "")
        if executive_summary:
            lines.append("### 🎯 Executive Summary")
            lines.append(executive_summary)
            lines.append("")
        
        # Portfolio Summary
        product_summary = product_bundle.get("product_summary", "")
        if product_summary:
            lines.append("### 📈 Portfolio Summary")
            lines.append(product_summary)
            lines.append("")
        
        # Risk Analysis Summary
        risk_summary = product_bundle.get("risk_summary", "")
        if risk_summary:
            lines.append("### ⚠️ Risk Analysis Summary")
            lines.append(risk_summary)
            lines.append("")
        
        # Investment Recommendation Summary
        recommendation_summary = product_bundle.get("recommendation_summary", "")
        if recommendation_summary:
            lines.append("### 💡 Investment Recommendation Summary")
            lines.append(recommendation_summary)
            lines.append("")
        
        # Individual Stock Assessments
        individual_assessments = product_bundle.get("individual_assessments", [])
        if individual_assessments:
            lines.append("### 🔍 Individual Stock Assessments")
            for i, assessment in enumerate(individual_assessments[:5], 1):  # Show first 5
                symbol = assessment.get('symbol', 'Unknown')
                enhanced_summary = assessment.get('enhanced_summary', '')
                original_assessment = assessment.get('original_assessment', '')
                
                lines.append(f"#### {i}. {symbol}")
                if enhanced_summary:
                    # Show the full enhanced summary
                    lines.append(enhanced_summary)
                elif original_assessment:
                    # Show the original assessment
                    lines.append(original_assessment)
                lines.append("")
            
            if len(individual_assessments) > 5:
                lines.append(f"... and {len(individual_assessments) - 5} more detailed assessments")
        
        # Assessment Metrics Summary
        assessment_summary = product_bundle.get("assessment_summary", {})
        if assessment_summary:
            lines.append("### 📊 Assessment Metrics Summary")
            lines.append(f"• **Total Assessments**: {assessment_summary.get('total_assessments', 0)}")
            lines.append(f"• **Average Confidence**: {assessment_summary.get('avg_confidence_score', 0):.1%}")
            lines.append(f"• **Average Suitability**: {assessment_summary.get('avg_suitability_score', 0):.1%}")
            lines.append(f"• **Average Recommendation Score**: {assessment_summary.get('avg_recommendation_score', 0):.1%}")
            
            # Risk Distribution
            risk_dist = assessment_summary.get('risk_distribution', {})
            if risk_dist:
                total = sum(risk_dist.values())
                if total > 0:
                    lines.append(f"\n**Risk Distribution**:")
                    lines.append(f"• Low Risk: {risk_dist.get('low', 0)} stocks ({risk_dist.get('low', 0)/total*100:.0f}%)")
                    lines.append(f"• Moderate Risk: {risk_dist.get('moderate', 0)} stocks ({risk_dist.get('moderate', 0)/total*100:.0f}%)")
                    lines.append(f"• High Risk: {risk_dist.get('high', 0)} stocks ({risk_dist.get('high', 0)/total*100:.0f}%)")
            
            # Recommendation Distribution
            rec_dist = assessment_summary.get('recommendation_distribution', {})
            if rec_dist:
                total = sum(rec_dist.values())
                if total > 0:
                    lines.append(f"\n**Recommendation Distribution**:")
                    lines.append(f"• Strong Buy: {rec_dist.get('strong_buy', 0)} stocks ({rec_dist.get('strong_buy', 0)/total*100:.0f}%)")
                    lines.append(f"• Buy: {rec_dist.get('buy', 0)} stocks ({rec_dist.get('buy', 0)/total*100:.0f}%)")
                    lines.append(f"• Hold: {rec_dist.get('hold', 0)} stocks ({rec_dist.get('hold', 0)/total*100:.0f}%)")
                    lines.append(f"• Sell: {rec_dist.get('sell', 0)} stocks ({rec_dist.get('sell', 0)/total*100:.0f}%)")
                    lines.append(f"• Strong Sell: {rec_dist.get('strong_sell', 0)} stocks ({rec_dist.get('strong_sell', 0)/total*100:.0f}%)")
        
        return "\n".join(lines)
    
    def create_interface(self):
        """Create the Gradio interface."""
        
        # Custom CSS for better styling
        css = """
        .gradio-container {
            max-width: 1200px !important;
        }
        .step-output {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        .success-message {
            color: #28a745;
            font-weight: bold;
        }
        .error-message {
            color: #dc3545;
            font-weight: bold;
        }
        """
        
        with gr.Blocks(css=css, title="Stock Picker AI", theme=gr.themes.Soft()) as interface:
            
            # Header
            gr.Markdown("""
            # 🤖 Stock Picker AI - Interactive Workflow
            
            This application provides an interactive interface for the AI-powered stock picking system.
            You can guide the process at each step and see detailed outputs from each agent.
            """)
            
            # Configuration section
            with gr.Accordion("🔧 Configuration", open=False):
                gr.Markdown(f"""
                **LLM Configuration:**
                - LLM Provider: {self.llm_provider.title()}
                - LLM Enabled: {'Yes' if self.use_llm else 'No'}
                - OpenAI API Key: {'✅ Set' if self.openai_api_key else '❌ Not Set'}
                - Anthropic API Key: {'✅ Set' if self.anthropic_api_key else '❌ Not Set'}
                - HuggingFace API Key: {'✅ Set' if self.hf_api_key else '❌ Not Set'}
                - OpenAI Model: {self.openai_model}
                - Anthropic Model: {self.anthropic_model}
                - HuggingFace Model: {self.hf_model}
                
                **MCP Server Configuration:**
                - MCP Provider: {self.mcp_provider.title()}
                - MCP Enabled: {'Yes' if self.use_mcp else 'No'}
                - MCP Server URL: {self.mcp_server_url}
                - MCP Authentication: {'✅ HuggingFace API Key' if self.hf_api_key else '❌ No API Key'}
                
                **Current Setup:**
                - Primary LLM: {self.llm_provider.title()} ({'✅ Active' if self.use_llm else '❌ Inactive'})
                - Stock Analysis: {'✅ MCP Server' if self.use_mcp else '❌ Rule-based'}
                """)
            
            # Step 1: Query Processing
            with gr.Tab("1️⃣ Query Processing"):
                gr.Markdown("### Step 1: Process Your Investment Query")
                gr.Markdown("""
                Enter your investment requirements in natural language. The system will extract structured criteria.
                
                **Example queries:**
                - "I want 10 conservative technology stocks with dividend focus for $50,000 investment over 6 months"
                - "Show me 15 aggressive growth stocks in healthcare for short-term trading with $25,000"
                - "Find 8 ESG-friendly mid-cap European stocks for long-term sustainable investing with $75,000"
                """)
                
                query_input = gr.Textbox(
                    label="Investment Query",
                    placeholder="Describe your investment requirements...",
                    lines=3
                )
                
                process_btn = gr.Button("Process Query", variant="primary")
                
                query_output = gr.Markdown(label="Processed Query Results")
                
                def process_query(query):
                    result = self.process_query_step(query)
                    if result.get("success"):
                        formatted = self.format_processed_query(result["processed_query"])
                        return formatted
                    else:
                        return f"❌ **Error**: {result.get('error', 'Unknown error')}"
                
                process_btn.click(
                    process_query,
                    inputs=[query_input],
                    outputs=[query_output]
                )
            
            # Step 2: Stock Discovery
            with gr.Tab("2️⃣ Stock Discovery"):
                gr.Markdown("### Step 2: Discover Stocks")
                gr.Markdown("""
                Based on your processed query, the system will discover relevant stocks.
                You can provide additional feedback to refine the discovery.
                """)
                
                discovery_feedback = gr.Textbox(
                    label="Additional Feedback (Optional)",
                    placeholder="Add any additional criteria or preferences...",
                    lines=2
                )
                
                discover_btn = gr.Button("Discover Stocks", variant="primary")
                
                discovery_output = gr.Markdown(label="Discovered Stocks")
                stock_selection = gr.Checkboxgroup(
                    label="Select Stocks for Analysis",
                    choices=[],
                    interactive=True
                )
                
                def discover_stocks(feedback):
                    result = self.discover_stocks_step(feedback)
                    if result.get("success"):
                        stocks = result["discovered_stocks"]
                        formatted = self.format_discovered_stocks(stocks)
                        
                        # Update stock selection choices
                        choices = [stock['symbol'] for stock in stocks]
                        
                        return formatted, gr.Checkboxgroup(choices=choices)
                    else:
                        return f"❌ **Error**: {result.get('error', 'Unknown error')}", gr.Checkboxgroup(choices=[])
                
                discover_btn.click(
                    discover_stocks,
                    inputs=[discovery_feedback],
                    outputs=[discovery_output, stock_selection]
                )
            
            # Step 3: Stock Analysis
            with gr.Tab("3️⃣ Stock Analysis"):
                gr.Markdown("### Step 3: Analyze Selected Stocks")
                gr.Markdown("""
                The system will analyze the selected stocks using advanced metrics and AI insights.
                """)
                
                analyze_btn = gr.Button("Analyze Stocks", variant="primary")
                
                analysis_output = gr.Markdown(label="Analysis Results")
                
                def analyze_stocks(selected):
                    result = self.analyze_stocks_step(selected)
                    if result.get("success"):
                        formatted = self.format_analysis_results(result["analysis_results"])
                        return formatted
                    else:
                        return f"❌ **Error**: {result.get('error', 'Unknown error')}"
                
                analyze_btn.click(
                    analyze_stocks,
                    inputs=[stock_selection],
                    outputs=[analysis_output]
                )
            
            # Step 4: Product Creation
            with gr.Tab("4️⃣ Product Creation"):
                gr.Markdown("### Step 4: Create Structured Product")
                gr.Markdown("""
                Based on the analysis results, the system will create a structured investment product
                compliant with FINOS CDM standards.
                """)
                
                product_preferences = gr.Textbox(
                    label="Product Preferences (Optional)",
                    placeholder="Add any specific product preferences...",
                    lines=2
                )
                
                create_product_btn = gr.Button("Create Product", variant="primary")
                
                product_output = gr.Markdown(label="Product Bundle")
                
                def create_product(preferences):
                    result = self.create_product_step(preferences)
                    if result.get("success"):
                        formatted = self.format_product_bundle(result["product_bundle"])
                        return formatted
                    else:
                        return f"❌ **Error**: {result.get('error', 'Unknown error')}"
                
                create_product_btn.click(
                    create_product,
                    inputs=[product_preferences],
                    outputs=[product_output]
                )
            
            # Step 5: Enhanced Summaries
            with gr.Tab("5️⃣ Enhanced Summaries"):
                gr.Markdown("### Step 5: AI-Generated Enhanced Summaries")
                gr.Markdown("""
                View comprehensive AI-generated summaries including executive summaries, risk analysis,
                investment recommendations, and detailed stock assessments.
                """)
                
                view_summaries_btn = gr.Button("View Enhanced Summaries", variant="primary")
                
                summaries_output = gr.Markdown(label="Enhanced Summaries")
                
                def view_enhanced_summaries():
                    # Check if we have a product bundle in the current state
                    if 'product_bundle' in self.current_state:
                        product_bundle = self.current_state['product_bundle']
                        if product_bundle and product_bundle.get("success"):
                            return self.format_enhanced_summaries(product_bundle)
                        else:
                            return "❌ **No product bundle available**. Please complete the product creation step first."
                    else:
                        return "❌ **No product bundle available**. Please complete the product creation step first."
                
                view_summaries_btn.click(
                    view_enhanced_summaries,
                    inputs=[],
                    outputs=[summaries_output]
                )
            
            # Complete Workflow
            with gr.Tab("🔄 Complete Workflow"):
                gr.Markdown("### Complete Workflow")
                gr.Markdown("""
                Run the entire workflow from start to finish with a single query.
                """)
                
                complete_query = gr.Textbox(
                    label="Complete Investment Query",
                    placeholder="Enter your complete investment requirements...",
                    lines=3
                )
                
                run_complete_btn = gr.Button("Run Complete Workflow", variant="primary", size="lg")
                
                complete_output = gr.Markdown(label="Complete Workflow Results")
                
                def run_complete_workflow(query):
                    if not self.workflow:
                        return "❌ **Error**: Workflow not initialized"
                    
                    try:
                        # Run the complete workflow
                        result = self.workflow.run(query)
                        
                        if result.get("success"):
                            lines = ["# 🎉 Complete Workflow Results\n"]
                            
                            # Processed query
                            processed_query = result.get("processed_query", {})
                            if processed_query:
                                lines.append("## 📋 Processed Query")
                                lines.append(self.format_processed_query(processed_query))
                                lines.append("")
                            
                            # Discovered stocks
                            discovered_stocks = result.get("discovered_stocks", [])
                            if discovered_stocks:
                                lines.append("## 📈 Discovered Stocks")
                                lines.append(self.format_discovered_stocks(discovered_stocks))
                                lines.append("")
                            
                            # Analysis results
                            analysis_results = result.get("analysis_results", [])
                            if analysis_results:
                                lines.append("## 🔬 Analysis Results")
                                lines.append(self.format_analysis_results(analysis_results))
                                lines.append("")
                            
                            # Product bundle with enhanced summaries
                            product_bundle = result.get("product_bundle", {})
                            if product_bundle:
                                lines.append("## 🏗️ Product Bundle & Enhanced Summaries")
                                lines.append(self.format_product_bundle(product_bundle))
                                lines.append("")
                            
                            # Dedicated Enhanced Summaries Section
                            if product_bundle:
                                lines.append("## 📝 Enhanced AI-Generated Summaries")
                                enhanced_summaries = self.format_enhanced_summaries(product_bundle)
                                lines.append(enhanced_summaries)
                                lines.append("")
                                
                                # Summary Highlights
                                lines.append("## 🎯 Summary Highlights")
                                
                                # Executive Summary
                                executive_summary = product_bundle.get("executive_summary", "")
                                if executive_summary:
                                    lines.append("### 🎯 Executive Summary")
                                    lines.append(executive_summary)
                                    lines.append("")
                                
                                # Risk Summary
                                risk_summary = product_bundle.get("risk_summary", "")
                                if risk_summary:
                                    lines.append("### ⚠️ Risk Analysis")
                                    lines.append(risk_summary)
                                    lines.append("")
                                
                                # Recommendation Summary
                                recommendation_summary = product_bundle.get("recommendation_summary", "")
                                if recommendation_summary:
                                    lines.append("### 💡 Investment Recommendations")
                                    lines.append(recommendation_summary)
                                    lines.append("")
                                
                                # Individual Stock Highlights
                                individual_assessments = product_bundle.get("individual_assessments", [])
                                if individual_assessments:
                                    lines.append("### 🔍 Key Stock Insights")
                                    for i, assessment in enumerate(individual_assessments[:5], 1):
                                        symbol = assessment.get('symbol', 'Unknown')
                                        enhanced_summary = assessment.get('enhanced_summary', '')
                                        if enhanced_summary:
                                            # Extract key points from enhanced summary
                                            summary_lines = enhanced_summary.split('\n')
                                            key_points = []
                                            for line in summary_lines:
                                                if any(keyword in line.lower() for keyword in ['recommendation', 'risk', 'confidence', 'suitability']):
                                                    key_points.append(line.strip())
                                                if len(key_points) >= 2:
                                                    break
                                            
                                            if key_points:
                                                lines.append(f"#### {symbol}")
                                                for point in key_points:
                                                    lines.append(f"• {point}")
                                                lines.append("")
                                    
                                    if len(individual_assessments) > 5:
                                        lines.append(f"... and {len(individual_assessments) - 5} more detailed assessments")
                                
                                # Assessment Metrics
                                assessment_summary = product_bundle.get("assessment_summary", {})
                                if assessment_summary:
                                    lines.append("### 📊 Portfolio Assessment Metrics")
                                    lines.append(f"• **Overall Confidence**: {assessment_summary.get('avg_confidence_score', 0):.1%}")
                                    lines.append(f"• **Investor Suitability**: {assessment_summary.get('avg_suitability_score', 0):.1%}")
                                    lines.append(f"• **Investment Recommendation**: {assessment_summary.get('avg_recommendation_score', 0):.1%}")
                                    
                                    # Risk Distribution
                                    risk_dist = assessment_summary.get('risk_distribution', {})
                                    if risk_dist:
                                        total = sum(risk_dist.values())
                                        if total > 0:
                                            lines.append(f"• **Risk Profile**: {risk_dist.get('low', 0)/total*100:.0f}% Low, {risk_dist.get('moderate', 0)/total*100:.0f}% Moderate, {risk_dist.get('high', 0)/total*100:.0f}% High")
                                    
                                    # Recommendation Distribution
                                    rec_dist = assessment_summary.get('recommendation_distribution', {})
                                    if rec_dist:
                                        total = sum(rec_dist.values())
                                        if total > 0:
                                            positive = rec_dist.get('strong_buy', 0) + rec_dist.get('buy', 0)
                                            lines.append(f"• **Recommendation Profile**: {positive/total*100:.0f}% Buy Recommendations")
                                
                                lines.append("")
                                lines.append("---")
                                lines.append("**🎉 Workflow completed successfully! All enhanced summaries have been generated.**")
                                lines.append("")
                                lines.append("**📋 Summary of Generated Content:**")
                                lines.append("✅ Structured Product Bundle")
                                lines.append("✅ Executive Summary")
                                lines.append("✅ Portfolio Summary") 
                                lines.append("✅ Risk Analysis Summary")
                                lines.append("✅ Investment Recommendation Summary")
                                lines.append("✅ Individual Stock Assessments")
                                lines.append("✅ Assessment Metrics")
                                lines.append("✅ CDM Compliance Information")
                            
                            return "\n".join(lines)
                        else:
                            return f"❌ **Error**: {result.get('error_message', 'Unknown error')}"
                    
                    except Exception as e:
                        return f"❌ **Error**: {str(e)}"
                
                run_complete_btn.click(
                    run_complete_workflow,
                    inputs=[complete_query],
                    outputs=[complete_output]
                )
            
            # Workflow Status
            with gr.Tab("📊 Workflow Status"):
                gr.Markdown("### Current Workflow Status")
                
                status_btn = gr.Button("Refresh Status", variant="secondary")
                
                status_output = gr.Markdown(label="Current Status")
                
                def get_status():
                    if not self.current_state:
                        return "**No workflow in progress**"
                    
                    lines = ["## Current Workflow Status\n"]
                    lines.append(f"**Current Step**: {self.current_state.get('step', 'unknown')}")
                    lines.append(f"**User Query**: {self.current_state.get('user_query', 'N/A')}")
                    
                    if 'processed_query' in self.current_state:
                        lines.append(f"**Query Processed**: ✅")
                    
                    if 'discovered_stocks' in self.current_state:
                        lines.append(f"**Stocks Discovered**: ✅ ({len(self.current_state['discovered_stocks'])} stocks)")
                    
                    if 'analysis_results' in self.current_state:
                        lines.append(f"**Analysis Complete**: ✅ ({len(self.current_state['analysis_results'])} stocks)")
                    
                    if 'product_bundle' in self.current_state:
                        product_bundle = self.current_state['product_bundle']
                        if product_bundle and product_bundle.get("success"):
                            lines.append(f"**Product Created**: ✅")
                            
                            # Check for enhanced summaries
                            has_executive = bool(product_bundle.get("executive_summary"))
                            has_risk = bool(product_bundle.get("risk_summary"))
                            has_recommendation = bool(product_bundle.get("recommendation_summary"))
                            has_individual = bool(product_bundle.get("individual_assessments"))
                            
                            if has_executive or has_risk or has_recommendation or has_individual:
                                lines.append(f"**Enhanced Summaries**: ✅")
                                summary_types = []
                                if has_executive:
                                    summary_types.append("Executive")
                                if has_risk:
                                    summary_types.append("Risk")
                                if has_recommendation:
                                    summary_types.append("Recommendation")
                                if has_individual:
                                    summary_types.append("Individual")
                                lines.append(f"  - Available: {', '.join(summary_types)} summaries")
                            else:
                                lines.append(f"**Enhanced Summaries**: ⚠️ (Template-based only)")
                        else:
                            lines.append(f"**Product Created**: ❌")
                    
                    return "\n".join(lines)
                
                status_btn.click(
                    get_status,
                    inputs=[],
                    outputs=[status_output]
                )
            
            # Footer
            gr.Markdown("""
            ---
            **Stock Picker AI** - Powered by LangChain, LangGraph, and advanced AI agents.
            
            This system uses multiple AI agents to process queries, discover stocks, analyze investments,
            and create structured products compliant with financial standards.
            """)
        
        return interface

def main():
    """Main function to run the Gradio app."""
    print("🚀 Starting Stock Picker AI Gradio Interface...")
    
    # Create the application
    app = StockPickerGradioApp()
    
    # Create and launch the interface
    interface = app.create_interface()
    
    # Launch the app
    interface.launch(
        server_name="0.0.0.0",
        server_port=9999,  # Changed to 9999 to avoid conflicts
        share=False,
        debug=True
    )

if __name__ == "__main__":
    main() 