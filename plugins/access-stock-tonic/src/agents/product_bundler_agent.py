"""
Product Bundler Agent - Creates structured equity products based on analyzer outputs using FINOS CDM standards.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from langchain_core.tools import BaseTool
import json

from ..tools.stock_selection_tool import StockSelectionTool
from ..prompts.product_bundler_prompts import (
    PRODUCT_BUNDLER_SYSTEM_PROMPT,
    PRODUCT_BUNDLER_CDM_PROMPT,
    PRODUCT_BUNDLER_EXAMPLES,
    PRODUCT_BUNDLER_INPUT_TEMPLATE
)

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_community.chat_models import ChatHuggingFace
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Import the summarizer agent
try:
    from .summarizer_agent import SummarizerAgent
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False
    print("Warning: SummarizerAgent not available. Will use template-based summaries.")

@dataclass
class CDMProductStructure:
    """CDM-compliant product structure based on FINOS CDM standards."""
    product_id: str
    product_type: str  # "EQUITY_BASKET", "STRUCTURED_NOTE", "ETF", etc.
    product_name: str
    issuer: str
    issue_date: str
    maturity_date: Optional[str]
    currency: str = "USD"
    notional_amount: float = 0.0
    components: List[Dict[str, Any]] = None
    risk_profile: Dict[str, Any] = None
    performance_metrics: Dict[str, Any] = None
    regulatory_classification: str = "RETAIL"
    tax_status: str = "TAXABLE"
    
    def __post_init__(self):
        if self.components is None:
            self.components = []
        if self.risk_profile is None:
            self.risk_profile = {}
        if self.performance_metrics is None:
            self.performance_metrics = {}

@dataclass
class CDMComponent:
    """CDM-compliant component structure."""
    component_id: str
    asset_type: str  # "EQUITY", "BOND", "DERIVATIVE", etc.
    underlying_asset: str
    weight: float
    quantity: Optional[float] = None
    price: Optional[float] = None
    market_value: Optional[float] = None

class CDMProductBundlerTool(BaseTool):
    """LangChain tool for creating CDM-compliant product structures."""
    
    name: str = "cdm_product_bundler"
    description: str = """
    Creates structured equity products based on FINOS CDM standards.
    Takes stock analysis results and produces CDM-compliant product structures.
    """
    logger: Optional[Any] = None
    use_llm: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm: Optional[Any] = None
    prompt_template: Optional[Any] = None
    stock_selector: Optional[Any] = None
    
    def __init__(self, openai_api_key: str, use_llm: bool = True, llm_provider: str = "openai", 
                 anthropic_api_key: Optional[str] = None, hf_api_key: Optional[str] = None,
                 openai_model: str = "gpt-4", anthropic_model: str = "claude-3-opus-20240229", 
                 hf_model: str = "HuggingFaceH4/zephyr-7b-beta"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.use_llm = use_llm
        self.llm_provider = llm_provider
        if self.use_llm:
            if llm_provider == "openai":
                self.llm = ChatOpenAI(
                    model=openai_model,
                    temperature=0.1,
                    openai_api_key=openai_api_key
                )
            elif llm_provider == "anthropic":
                self.llm = ChatAnthropic(
                    model=anthropic_model,
                    temperature=0.1,
                    anthropic_api_key=anthropic_api_key
                )
            elif llm_provider == "huggingface":
                self.llm = ChatHuggingFace(
                    model=hf_model,
                    temperature=0.1,
                    huggingfacehub_api_token=hf_api_key
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            self.prompt_template = ChatPromptTemplate.from_messages([
                ("system", PRODUCT_BUNDLER_SYSTEM_PROMPT),
                ("human", PRODUCT_BUNDLER_CDM_PROMPT)
            ])
        self.stock_selector = StockSelectionTool(openai_api_key)
        
    def _run(self, analysis_results: str, processed_query: str = None) -> str:
        """Create CDM-compliant product structure from analysis results."""
        try:
            # Parse the analysis results
            results = json.loads(analysis_results)
            
            # Parse processed query if provided
            query_data = None
            if processed_query:
                query_data = json.loads(processed_query)
            
            # Create CDM product structure
            product = self._create_cdm_product(results, query_data)
            
            # Return structured output
            return json.dumps(asdict(product), indent=2)
            
        except Exception as e:
            self.logger.error(f"Error in CDM product bundler: {e}")
            return f"Error: {str(e)}"
    
    def _create_cdm_product(self, analysis_results: List[Dict[str, Any]], 
                           processed_query: Optional[Dict[str, Any]] = None) -> CDMProductStructure:
        """Create a CDM-compliant product structure."""
        
        # Generate product ID
        product_id = f"EQ_BASKET_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine product type based on analysis
        product_type = self._determine_product_type(analysis_results)
        
        # Use stock selection tool to select and weight components
        user_preferences = self._extract_user_preferences(analysis_results, processed_query)
        
        # Determine target and min counts from processed query
        target_count = 15  # Default
        min_count = 5      # Default
        if processed_query:
            # Use limit from processed query as target count
            target_count = processed_query.get('limit', 15)
            min_count = max(3, target_count // 3)  # At least 3, or 1/3 of target
        
        selected_stocks_json = self.stock_selector._run(
            json.dumps(analysis_results), 
            json.dumps(user_preferences),
            target_count=target_count,
            min_count=min_count
        )
        selected_stocks = json.loads(selected_stocks_json)
        
        # Use LLM to enhance product structure if available
        if self.use_llm and processed_query:
            enhanced_product = self._enhance_product_with_llm(selected_stocks, processed_query, product_type)
        else:
            enhanced_product = None
        
        # Create components from selected stocks
        components = self._create_components_from_selection(selected_stocks)
        
        # Calculate risk profile
        risk_profile = self._calculate_risk_profile(selected_stocks)
        
        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(selected_stocks)
        
        # Determine notional amount from processed query
        notional_amount = 100000.0  # Default $100k
        if processed_query and processed_query.get('capital_amount'):
            notional_amount = processed_query['capital_amount']
        
        # Determine maturity date from investment horizon
        maturity_days = 365  # Default 1 year
        if processed_query:
            investment_horizon = processed_query.get('investment_horizon', 'long')
            horizon_mapping = {
                'short': 90,    # 3 months
                'medium': 180,  # 6 months
                'long': 365     # 1 year
            }
            maturity_days = horizon_mapping.get(investment_horizon, 365)
        
        # Create product structure
        product = CDMProductStructure(
            product_id=product_id,
            product_type=product_type,
            product_name=f"Structured Equity Basket - {product_type}",
            issuer="STRUCTURED_EQUITIES_PLATFORM",
            issue_date=datetime.now().isoformat(),
            maturity_date=(datetime.now() + timedelta(days=maturity_days)).isoformat(),
            currency="USD",
            notional_amount=notional_amount,
            components=components,
            risk_profile=risk_profile,
            performance_metrics=performance_metrics,
            regulatory_classification="RETAIL",
            tax_status="TAXABLE"
        )
        
        # Apply LLM enhancements if available
        if enhanced_product:
            product.product_name = enhanced_product.get('product_name', product.product_name)
            product.risk_profile.update(enhanced_product.get('risk_insights', {}))
            product.performance_metrics.update(enhanced_product.get('performance_insights', {}))
        
        return product
    
    def _enhance_product_with_llm(self, selected_stocks: List[Dict[str, Any]], 
                                 processed_query: Dict[str, Any], 
                                 product_type: str) -> Dict[str, Any]:
        """Enhance product structure using LLM insights."""
        try:
            # Create component list for prompt
            component_list = "\n".join([
                f"- {stock['symbol']}: {stock.get('retention_reason', 'Selected based on analysis')}"
                for stock in selected_stocks
            ])
            
            # Create prompt for product enhancement
            prompt = PRODUCT_BUNDLER_CDM_PROMPT.format(
                notional_amount=processed_query.get('capital_amount', 100000.0),
                currency="USD",
                maturity_date=(datetime.now() + timedelta(days=365)).isoformat(),
                regulatory_class="RETAIL",
                risk_tolerance=processed_query.get('risk_tolerance', 'moderate'),
                investment_horizon=processed_query.get('investment_horizon', 'long'),
                capital_amount=processed_query.get('capital_amount', 100000.0),
                strategy_focus=self._get_strategy_focus(processed_query),
                component_list=component_list
            )
            
            response = self.llm.invoke(prompt)
            
            # Parse LLM response for enhancements
            content = response.content
            
            enhanced_product = {
                'product_name': self._extract_product_name(content),
                'risk_insights': self._extract_risk_insights(content),
                'performance_insights': self._extract_performance_insights(content)
            }
            
            return enhanced_product
            
        except Exception as e:
            self.logger.error(f"Error enhancing product with LLM: {e}")
            return {}
    
    def _get_strategy_focus(self, processed_query: Dict[str, Any]) -> str:
        """Get strategy focus from processed query."""
        if processed_query.get('dividend_focus'):
            return "Dividend Income"
        elif processed_query.get('growth_focus'):
            return "Growth"
        elif processed_query.get('value_focus'):
            return "Value"
        elif processed_query.get('esg_focus'):
            return "ESG/Sustainable"
        else:
            return "Balanced"
    
    def _extract_product_name(self, content: str) -> str:
        """Extract product name from LLM response."""
        # Look for product name patterns
        import re
        name_match = re.search(r'product name[:\s]+([^\n]+)', content, re.IGNORECASE)
        if name_match:
            return name_match.group(1).strip()
        return "Structured Equity Basket"
    
    def _extract_risk_insights(self, content: str) -> Dict[str, Any]:
        """Extract risk insights from LLM response."""
        insights = {}
        content_lower = content.lower()
        
        if 'low risk' in content_lower:
            insights['risk_level'] = 'LOW'
        elif 'high risk' in content_lower:
            insights['risk_level'] = 'HIGH'
        else:
            insights['risk_level'] = 'MODERATE'
        
        return insights
    
    def _extract_performance_insights(self, content: str) -> Dict[str, Any]:
        """Extract performance insights from LLM response."""
        insights = {}
        content_lower = content.lower()
        
        if 'high return' in content_lower or 'aggressive' in content_lower:
            insights['expected_return_range'] = '15-25%'
        elif 'moderate return' in content_lower or 'balanced' in content_lower:
            insights['expected_return_range'] = '8-15%'
        else:
            insights['expected_return_range'] = '5-10%'
        
        return insights
    
    def _extract_user_preferences(self, analyzer_results: List[Dict[str, Any]], 
                                 processed_query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract user preferences from analyzer results with enhanced assessment data."""
        
        # Analyze the characteristics of the stocks to infer preferences
        risk_levels = []
        sectors = []
        market_caps = []
        dividend_yields = []
        ensemble_scores = []
        momentum_scores = []
        quality_scores = []
        suitability_scores = []
        confidence_scores = []
        recommendation_scores = []
        
        for result in analyzer_results:
            # Check if we have the new assessment structure
            assessment = result.get('assessment', {})
            analysis = result.get('analysis', {})
            
            if assessment:
                # Use assessment data for better preference extraction
                risk_assessment = assessment.get('risk_assessment', {})
                confidence_score = assessment.get('confidence_score', {})
                suitability_score = assessment.get('suitability_score', {})
                investment_recommendation = assessment.get('investment_recommendation', {})
                
                # Extract risk level from assessment
                risk_level = risk_assessment.get('risk_level', 'MODERATE').lower()
                risk_levels.append(risk_level)
                
                # Extract confidence and suitability scores
                confidence_val = confidence_score.get('confidence_score', 0.5)
                confidence_scores.append(confidence_val)
                
                suitability_val = suitability_score.get('suitability_score', 0.5)
                suitability_scores.append(suitability_val)
                
                # Extract recommendation score
                rec_score = investment_recommendation.get('score', 0.5)
                recommendation_scores.append(rec_score)
                
                # Extract technical factors
                technical_factors = investment_recommendation.get('technical_factors', {})
                ensemble_score = technical_factors.get('ensemble_score', 0.5)
                momentum_score = technical_factors.get('momentum_score', 0.5)
                quality_score = technical_factors.get('quality_score', 0.5)
                
                ensemble_scores.append(ensemble_score)
                momentum_scores.append(momentum_score)
                quality_scores.append(quality_score)
                
            elif analysis:
                # Fallback to original analysis data extraction
                # Extract risk information from MCP outputs - handle MCP key names
                risk_metrics = analysis.get('risk', {})
                if risk_metrics:
                    sharpe_ratios = []
                    var_95_values = []
                    volatilities = []
                    
                    for stock in selected_stocks:
                        analysis = stock.get('analysis', {})
                        risk_data = analysis.get('risk', {})
                        
                        # Handle MCP key names
                        sharpe_ratios.append(risk_data.get('Sharpe_Ratio', risk_data.get('sharpe_ratio', 0)))
                        var_95_values.append(risk_data.get('VaR_95', risk_data.get('var_95', 0)))
                        volatilities.append(risk_data.get('Annual_Volatility', risk_data.get('volatility', 0)))
                
                # Extract sector information from MCP outputs - handle MCP key names
                sector_analysis = analysis.get('sector', {})
                if sector_analysis:
                    sectors.append(sector_analysis.get('Sector', sector_analysis.get('sector', 'UNKNOWN')))
                
                # Extract market cap information from MCP outputs - handle MCP key names
                metrics = analysis.get('metrics', {})
                if metrics:
                    market_cap = metrics.get('Market_Cap', metrics.get('market_cap', 0))
                    if market_cap > 10e9:  # $10B+
                        market_caps.append("large")
                    elif market_cap > 2e9:  # $2B+
                        market_caps.append("mid")
                    else:
                        market_caps.append("small")
                    
                    # Extract dividend yield from MCP outputs - handle MCP key names
                    dividend_yield = metrics.get('Dividend_Yield', metrics.get('dividend_yield', 0))
                    dividend_yields.append(dividend_yield)
                
                # Extract ensemble scores from MCP outputs - handle MCP key names
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_score = ensemble_data.get('ensemble_score', 0)
                    ensemble_scores.append(ensemble_score)
                
                # Extract advanced metrics from MCP outputs - handle MCP key names
                advanced_data = analysis.get('advanced', {})
                if advanced_data:
                    momentum_score = advanced_data.get('momentum_score', 0.5)
                    quality_score = advanced_data.get('quality_score', 0.5)
                    momentum_scores.append(momentum_score)
                    quality_scores.append(quality_score)
            
            # Always extract sector and market cap from analysis if available
            if analysis:
                sector_analysis = analysis.get('sector', {})
                if sector_analysis:
                    sectors.append(sector_analysis.get('sector', 'UNKNOWN'))
                
                metrics = analysis.get('metrics', {})
                if metrics:
                    market_cap = metrics.get('market_cap', 0)
                    if market_cap > 10e9:  # $10B+
                        market_caps.append("large")
                    elif market_cap > 2e9:  # $2B+
                        market_caps.append("mid")
                    else:
                        market_caps.append("small")
                    
                    dividend_yield = metrics.get('dividend_yield', 0)
                    dividend_yields.append(dividend_yield)
        
        # Determine inferred preferences with enhanced logic
        risk_tolerance = "moderate"
        if risk_levels:
            low_count = risk_levels.count("low")
            high_count = risk_levels.count("high")
            if low_count > len(risk_levels) / 2:
                risk_tolerance = "conservative"
            elif high_count > len(risk_levels) / 2:
                risk_tolerance = "aggressive"
        
        # Determine dividend focus
        dividend_focus = False
        if dividend_yields:
            avg_dividend = sum(dividend_yields) / len(dividend_yields)
            dividend_focus = avg_dividend > 0.03  # 3% average dividend yield
        
        # Determine growth focus
        growth_focus = False
        if market_caps:
            small_mid_count = market_caps.count("small") + market_caps.count("mid")
            growth_focus = small_mid_count > len(market_caps) / 2
        
        # Determine momentum focus
        momentum_focus = False
        if momentum_scores:
            avg_momentum = sum(momentum_scores) / len(momentum_scores)
            momentum_focus = avg_momentum > 0.6
        
        # Determine quality focus
        quality_focus = False
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            quality_focus = avg_quality > 0.7
        
        # Determine ensemble confidence
        ensemble_confidence = "moderate"
        if ensemble_scores:
            avg_ensemble = sum(ensemble_scores) / len(ensemble_scores)
            if avg_ensemble > 0.8:
                ensemble_confidence = "high"
            elif avg_ensemble < 0.5:
                ensemble_confidence = "low"
        
        # Enhanced confidence assessment
        overall_confidence = "moderate"
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            if avg_confidence > 0.8:
                overall_confidence = "high"
            elif avg_confidence < 0.5:
                overall_confidence = "low"
        
        # Overall suitability assessment
        overall_suitability = "moderate"
        if suitability_scores:
            avg_suitability = sum(suitability_scores) / len(suitability_scores)
            if avg_suitability > 0.8:
                overall_suitability = "excellent"
            elif avg_suitability > 0.6:
                overall_suitability = "good"
            elif avg_suitability < 0.4:
                overall_suitability = "poor"
        
        return {
            'risk_tolerance': risk_tolerance,
            'investment_horizon': 'long',  # Default for structured products
            'sectors': list(set(sectors)),
            'dividend_focus': dividend_focus,
            'growth_focus': growth_focus,
            'momentum_focus': momentum_focus,
            'quality_focus': quality_focus,
            'ensemble_confidence': ensemble_confidence,
            'overall_confidence': overall_confidence,
            'overall_suitability': overall_suitability,
            'esg_focus': False,  # Default, would be set by user preferences
            'assessment_metrics': {
                'avg_confidence_score': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5,
                'avg_suitability_score': sum(suitability_scores) / len(suitability_scores) if suitability_scores else 0.5,
                'avg_recommendation_score': sum(recommendation_scores) / len(recommendation_scores) if recommendation_scores else 0.5,
                'assessment_count': len([r for r in analyzer_results if r.get('assessment')])
            }
        }
    
    def _determine_product_type(self, analysis_results: List[Dict[str, Any]]) -> str:
        """Determine the appropriate CDM product type based on analysis."""
        
        # Analyze the characteristics of the stocks
        risk_levels = []
        sectors = []
        market_caps = []
        
        for result in analysis_results:
            analysis = result.get('analysis', {})
            if analysis:
                # Extract risk information
                risk_metrics = analysis.get('risk', {})
                if risk_metrics:
                    sharpe_ratios = []
                    var_95_values = []
                    volatilities = []
                    
                    for stock in selected_stocks:
                        analysis = stock.get('analysis', {})
                        risk_data = analysis.get('risk', {})
                        
                        # Handle MCP key names
                        sharpe_ratios.append(risk_data.get('Sharpe_Ratio', risk_data.get('sharpe_ratio', 0)))
                        var_95_values.append(risk_data.get('VaR_95', risk_data.get('var_95', 0)))
                        volatilities.append(risk_data.get('Annual_Volatility', risk_data.get('volatility', 0)))
                
                # Extract sector information
                sector_analysis = analysis.get('sector', {})
                if sector_analysis:
                    sectors.append(sector_analysis.get('sector', 'UNKNOWN'))
                
                # Extract market cap information
                metrics = analysis.get('metrics', {})
                if metrics:
                    market_cap = metrics.get('market_cap', 0)
                    if market_cap > 10e9:  # $10B+
                        market_caps.append("LARGE")
                    elif market_cap > 2e9:  # $2B+
                        market_caps.append("MID")
                    else:
                        market_caps.append("SMALL")
        
        # Determine product type based on characteristics
        avg_risk = "MEDIUM"
        if risk_levels:
            low_count = risk_levels.count("low")
            high_count = risk_levels.count("high")
            if low_count > len(risk_levels) / 2:
                avg_risk = "LOW"
            elif high_count > len(risk_levels) / 2:
                avg_risk = "HIGH"
        
        # Map to CDM product types
        if avg_risk == "LOW":
            return "CONSERVATIVE_EQUITY_BASKET"
        elif avg_risk == "HIGH":
            return "AGGRESSIVE_EQUITY_BASKET"
        else:
            return "BALANCED_EQUITY_BASKET"
    
    def _create_components_from_selection(self, selected_stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create CDM components from stock selection results."""
        
        components = []
        
        for i, stock in enumerate(selected_stocks):
            component = CDMComponent(
                component_id=f"COMP_{stock['symbol']}_{i}",
                asset_type="EQUITY",
                underlying_asset=stock['symbol'],
                weight=stock['weight'],
                quantity=None,  # Will be calculated based on weight and price
                price=None,     # Current market price
                market_value=None  # Will be calculated
            )
            
            components.append(asdict(component))
        
        return components
    
    def _calculate_risk_profile(self, selected_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk profile for selected stocks using MCP outputs."""
        
        if not selected_stocks:
            return {"risk_level": "MEDIUM", "volatility": 0.0, "var_95": 0.0}
        
        # Calculate weighted average risk metrics from MCP outputs
        total_weight = sum(stock['weight'] for stock in selected_stocks)
        
        weighted_risk_score = sum(stock['risk_score'] * stock['weight'] for stock in selected_stocks) / total_weight
        
        # Extract MCP risk metrics
        sharpe_ratios = []
        var_95_values = []
        volatilities = []
        max_drawdowns = []
        stress_scores = []
        regime_probabilities = []
        ensemble_scores = []
        
        for stock in selected_stocks:
            analysis = stock.get('analysis', {})
            if analysis:
                risk_data = analysis.get('risk', {})
                if risk_data:
                    # Handle MCP key names
                    sharpe_ratios.append(risk_data.get('Sharpe_Ratio', risk_data.get('sharpe_ratio', 0)))
                    var_95_values.append(risk_data.get('VaR_95', risk_data.get('var_95', 0)))
                    volatilities.append(risk_data.get('Annual_Volatility', risk_data.get('volatility', 0)))
                    max_drawdowns.append(risk_data.get('Max_Drawdown', risk_data.get('max_drawdown', 0)))
                
                stress_data = analysis.get('stress', {})
                if stress_data:
                    stress_scores.append(stress_data.get('stress_score', 0))
                
                regime_data = analysis.get('regime', {})
                if regime_data:
                    # Handle MCP regime data structure
                    probabilities = regime_data.get('probabilities', [0.5])
                    regime_probabilities.append(probabilities[0] if probabilities else 0.5)
                
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_scores.append(ensemble_data.get('ensemble_score', 0))
        
        # Calculate aggregate metrics
        avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0
        avg_var_95 = sum(var_95_values) / len(var_95_values) if var_95_values else 0
        avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0
        avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
        avg_stress_score = sum(stress_scores) / len(stress_scores) if stress_scores else 0
        avg_regime_probability = sum(regime_probabilities) / len(regime_probabilities) if regime_probabilities else 0.5
        avg_ensemble_score = sum(ensemble_scores) / len(ensemble_scores) if ensemble_scores else 0
        
        # Determine risk level based on MCP metrics
        if avg_sharpe > 1.5 and avg_var_95 < 0.02 and avg_volatility < 0.15:
            risk_level = "LOW"
        elif avg_sharpe > 0.8 and avg_var_95 < 0.05 and avg_volatility < 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        # Calculate diversification score
        unique_symbols = set(stock['symbol'] for stock in selected_stocks)
        diversification_score = len(unique_symbols) / len(selected_stocks)
        
        # Determine market regime
        if avg_regime_probability > 0.7:
            market_regime = "BULL_MARKET"
        elif avg_regime_probability < 0.3:
            market_regime = "BEAR_MARKET"
        else:
            market_regime = "NEUTRAL_MARKET"
        
        return {
            "risk_level": risk_level,
            "weighted_risk_score": weighted_risk_score,
            "diversification_score": diversification_score,
            "market_regime": market_regime,
            "ensemble_confidence": avg_ensemble_score,
            "stress_resilience": 1.0 - avg_stress_score,  # Higher is better
            "risk_metrics": {
                "sharpe_ratio": avg_sharpe,
                "var_95": avg_var_95,
                "volatility": avg_volatility,
                "max_drawdown": avg_max_drawdown
            },
            "regime_probability": avg_regime_probability
        }
    
    def _calculate_performance_metrics(self, selected_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall performance metrics for the product using MCP outputs."""
        
        if not selected_stocks:
            return {"expected_return": 0.0, "volatility": 0.0, "sharpe_ratio": 0.0}
        
        # Extract performance metrics from MCP outputs
        signals = []
        pe_ratios = []
        dividend_yields = []
        market_caps = []
        momentum_scores = []
        quality_scores = []
        ensemble_scores = []
        
        for stock in selected_stocks:
            analysis = stock.get('analysis', {})
            if analysis:
                # Extract trading signals - handle MCP key names
                signal_data = analysis.get('signals', {})
                if signal_data:
                    overall_signal = signal_data.get('overall', signal_data.get('Overall', 'NEUTRAL'))
                    signals.append(overall_signal)
                
                # Extract financial metrics - handle MCP key names
                metrics_data = analysis.get('metrics', {})
                if metrics_data:
                    pe_ratios.append(metrics_data.get('P/E_Ratio', metrics_data.get('pe_ratio', 0)))
                    dividend_yields.append(metrics_data.get('Dividend_Yield', metrics_data.get('dividend_yield', 0)))
                    market_caps.append(metrics_data.get('Market_Cap', metrics_data.get('market_cap', 0)))
                
                # Extract advanced metrics - handle MCP key names
                advanced_data = analysis.get('advanced', {})
                if advanced_data:
                    momentum_scores.append(advanced_data.get('momentum_score', 0))
                    quality_scores.append(advanced_data.get('quality_score', 0))
                
                # Extract ensemble metrics - handle MCP key names
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_scores.append(ensemble_data.get('ensemble_score', 0))
        
        # Calculate aggregate metrics
        avg_pe_ratio = sum(pe_ratios) / len(pe_ratios) if pe_ratios else 0
        avg_dividend_yield = sum(dividend_yields) / len(dividend_yields) if dividend_yields else 0
        avg_market_cap = sum(market_caps) / len(market_caps) if market_caps else 0
        avg_momentum = sum(momentum_scores) / len(momentum_scores) if momentum_scores else 0
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        avg_ensemble = sum(ensemble_scores) / len(ensemble_scores) if ensemble_scores else 0
        
        # Calculate signal distribution
        buy_signals = signals.count('BUY') if signals else 0
        sell_signals = signals.count('SELL') if signals else 0
        neutral_signals = signals.count('NEUTRAL') if signals else 0
        total_signals = len(signals)
        
        signal_strength = (buy_signals - sell_signals) / total_signals if total_signals > 0 else 0
        
        # Estimate expected return based on MCP metrics
        # Base return from dividend yield
        base_return = avg_dividend_yield
        
        # Momentum premium
        momentum_premium = avg_momentum * 0.05  # 5% max momentum premium
        
        # Quality premium
        quality_premium = avg_quality * 0.03  # 3% max quality premium
        
        # Ensemble confidence premium
        ensemble_premium = avg_ensemble * 0.02  # 2% max ensemble premium
        
        # Signal strength premium
        signal_premium = signal_strength * 0.04  # 4% max signal premium
        
        expected_return = base_return + momentum_premium + quality_premium + ensemble_premium + signal_premium
            
        # Calculate risk-adjusted metrics
        risk_profile = self._calculate_risk_profile(selected_stocks)
        volatility = risk_profile.get('risk_metrics', {}).get('volatility', 0.15)
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0
        
        return {
            "expected_return": expected_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "signal_analysis": {
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "neutral_signals": neutral_signals,
                "signal_strength": signal_strength
            },
            "financial_metrics": {
                "avg_pe_ratio": avg_pe_ratio,
                "avg_dividend_yield": avg_dividend_yield,
                "avg_market_cap": avg_market_cap
            },
            "advanced_metrics": {
                "avg_momentum_score": avg_momentum,
                "avg_quality_score": avg_quality,
                "avg_ensemble_score": avg_ensemble
            },
            "return_components": {
                "base_return": base_return,
                "momentum_premium": momentum_premium,
                "quality_premium": quality_premium,
                "ensemble_premium": ensemble_premium,
                "signal_premium": signal_premium
            }
        }

class ProductBundlerAgent:
    """
    Product Bundler Agent that creates structured equity products based on analyzer outputs
    using FINOS CDM standards.
    """
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 anthropic_api_key: Optional[str] = None,
                 hf_api_key: Optional[str] = None,
                 use_llm: bool = False,
                 llm_provider: str = "openai",
                 openai_model: str = "gpt-4",
                 anthropic_model: str = "claude-3-opus-20240229",
                 hf_model: str = "HuggingFaceH4/zephyr-7b-beta",
                 use_summarizer: bool = True):
        """
        Initialize the Product Bundler Agent.
        
        Args:
            openai_api_key: OpenAI API key
            anthropic_api_key: Anthropic API key
            hf_api_key: HuggingFace API key
            use_llm: Whether to use LLM for product bundling
            llm_provider: LLM provider ("openai", "anthropic", or "huggingface")
            openai_model: OpenAI model name
            anthropic_model: Anthropic model name
            hf_model: HuggingFace model name
            use_summarizer: Whether to use the summarizer agent for enhanced summaries
        """
        self.logger = logging.getLogger(__name__)
        self.use_llm = use_llm and LLM_AVAILABLE and (openai_api_key or anthropic_api_key or hf_api_key)
        self.llm_provider = llm_provider
        self.use_summarizer = use_summarizer and SUMMARIZER_AVAILABLE
        
        # Initialize LLM client
        self.llm_client = None
        if self.use_llm:
            self._initialize_llm_client(
                openai_api_key, anthropic_api_key, hf_api_key,
                openai_model, anthropic_model, hf_model
            )
        
        # Initialize summarizer agent
        self.summarizer = None
        if self.use_summarizer:
            self._initialize_summarizer(
                openai_api_key, anthropic_api_key, llm_provider,
                openai_model, anthropic_model
            )
        
        # Initialize product templates
        self.product_templates = self._initialize_product_templates()
        
        # Initialize stock selector tool
        self.stock_selector = StockSelectionTool(
            openai_api_key=openai_api_key,
            use_llm=use_llm,
            llm_provider=llm_provider,
            anthropic_api_key=anthropic_api_key,
            hf_api_key=hf_api_key,
            openai_model=openai_model,
            anthropic_model=anthropic_model,
            hf_model=hf_model
        )
        
        self.logger.info(f"ProductBundlerAgent initialized with LLM: {self.use_llm}, Summarizer: {self.use_summarizer}")
    
    def _initialize_summarizer(self, openai_api_key: str, anthropic_api_key: str,
                              llm_provider: str, openai_model: str, anthropic_model: str):
        """Initialize the summarizer agent."""
        try:
            self.summarizer = SummarizerAgent(
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
                use_llm=self.use_llm,
                llm_provider=llm_provider,
                openai_model=openai_model,
                anthropic_model=anthropic_model
            )
            self.logger.info("Summarizer agent initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize summarizer agent: {e}")
            self.use_summarizer = False
    
    def bundle_product(self, analyzer_results: List[Dict[str, Any]], 
                      user_preferences: Dict[str, Any] = None,
                      processed_query: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a structured equity product from analyzer results.
        
        Args:
            analyzer_results: List of analysis results from analyzer agent
            user_preferences: Optional user preferences for product customization
            processed_query: Structured query data from query processor
            
        Returns:
            Dictionary containing the structured product
        """
        try:
            print(f"[BUNDLER DEBUG] Starting bundle_product with {len(analyzer_results)} analyzer results")
            print(f"[BUNDLER DEBUG] User preferences: {user_preferences}")
            print(f"[BUNDLER DEBUG] Processed query: {processed_query}")
            
            # Debug analyzer results structure
            for i, result in enumerate(analyzer_results):
                symbol = result.get('symbol', 'UNKNOWN')
                has_assessment = 'assessment' in result
                has_analysis = 'analysis' in result
                has_price_data = 'price_data' in result
                print(f"[BUNDLER DEBUG] Analyzer result {i+1}: {symbol}")
                print(f"[BUNDLER DEBUG]   has_assessment: {has_assessment}")
                print(f"[BUNDLER DEBUG]   has_analysis: {has_analysis}")
                print(f"[BUNDLER DEBUG]   has_price_data: {has_price_data}")
                if has_assessment:
                    assessment_keys = list(result['assessment'].keys())
                    print(f"[BUNDLER DEBUG]   assessment keys: {assessment_keys}")
                if has_analysis:
                    analysis_keys = list(result['analysis'].keys())
                    print(f"[BUNDLER DEBUG]   analysis keys: {analysis_keys}")
            
            # Store original analyzer results for assessment data mapping
            self.last_analyzer_results = analyzer_results
            print(f"[BUNDLER DEBUG] Stored {len(analyzer_results)} analyzer results in last_analyzer_results")
            
            # Use stock selection tool to select and weight stocks
            if not user_preferences:
                print(f"[BUNDLER DEBUG] No user preferences provided, extracting from analyzer results")
                user_preferences = self._extract_user_preferences(analyzer_results, processed_query)
                print(f"[BUNDLER DEBUG] Extracted user preferences: {user_preferences}")
            
            # Determine target and min counts from processed query
            target_count = 15  # Default
            min_count = 5      # Default
            if processed_query:
                # Use limit from processed query as target count
                target_count = processed_query.get('limit', 15)
                min_count = max(3, target_count // 3)  # At least 3, or 1/3 of target
            
            print(f"[BUNDLER DEBUG] Using target_count: {target_count}, min_count: {min_count}")
            
            selected_stocks_json = self.stock_selector._run(
                json.dumps(analyzer_results), 
                json.dumps(user_preferences),
                target_count=target_count,
                min_count=min_count
            )
            selected_stocks = json.loads(selected_stocks_json)
            
            print(f"[BUNDLER DEBUG] Stock selection completed, selected {len(selected_stocks)} stocks")
            for i, stock in enumerate(selected_stocks):
                symbol = stock.get('symbol', 'UNKNOWN')
                weight = stock.get('weight', 0)
                total_score = stock.get('total_score', 0)
                print(f"[BUNDLER DEBUG] Selected stock {i+1}: {symbol} - weight: {weight:.3f}, score: {total_score:.3f}")
            
            # Create product bundle with selected stocks
            product_bundle = self._create_product_bundle(selected_stocks, user_preferences, processed_query)
            
            # Add selection metadata
            product_bundle["stock_selection"] = {
                "total_candidates": len(analyzer_results),
                "selected_count": len(selected_stocks),
                "selection_efficiency": len(selected_stocks) / len(analyzer_results) if analyzer_results else 0,
                "selection_criteria": user_preferences
            }
            
            print(f"[BUNDLER DEBUG] Product bundle created successfully")
            print(f"[BUNDLER DEBUG] Product bundle keys: {list(product_bundle.keys())}")
            print(f"[BUNDLER DEBUG] Product bundle success: {product_bundle.get('success', False)}")
            
            return product_bundle
            
        except Exception as e:
            print(f"[BUNDLER DEBUG] Error in bundle_product: {e}")
            import traceback
            print(f"[BUNDLER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error bundling product: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_user_preferences(self, analyzer_results: List[Dict[str, Any]], 
                                 processed_query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract user preferences from analyzer results with enhanced assessment data."""
        
        # Analyze the characteristics of the stocks to infer preferences
        risk_levels = []
        sectors = []
        market_caps = []
        dividend_yields = []
        ensemble_scores = []
        momentum_scores = []
        quality_scores = []
        suitability_scores = []
        confidence_scores = []
        recommendation_scores = []
        
        for result in analyzer_results:
            # Check if we have the new assessment structure
            assessment = result.get('assessment', {})
            analysis = result.get('analysis', {})
            
            if assessment:
                # Use assessment data for better preference extraction
                risk_assessment = assessment.get('risk_assessment', {})
                confidence_score = assessment.get('confidence_score', {})
                suitability_score = assessment.get('suitability_score', {})
                investment_recommendation = assessment.get('investment_recommendation', {})
                
                # Extract risk level from assessment
                risk_level = risk_assessment.get('risk_level', 'MODERATE').lower()
                risk_levels.append(risk_level)
                
                # Extract confidence and suitability scores
                confidence_val = confidence_score.get('confidence_score', 0.5)
                confidence_scores.append(confidence_val)
                
                suitability_val = suitability_score.get('suitability_score', 0.5)
                suitability_scores.append(suitability_val)
                
                # Extract recommendation score
                rec_score = investment_recommendation.get('score', 0.5)
                recommendation_scores.append(rec_score)
                
                # Extract technical factors
                technical_factors = investment_recommendation.get('technical_factors', {})
                ensemble_score = technical_factors.get('ensemble_score', 0.5)
                momentum_score = technical_factors.get('momentum_score', 0.5)
                quality_score = technical_factors.get('quality_score', 0.5)
                
                ensemble_scores.append(ensemble_score)
                momentum_scores.append(momentum_score)
                quality_scores.append(quality_score)
                
            elif analysis:
                # Fallback to original analysis data extraction
                # Extract risk information from MCP outputs - handle MCP key names
                risk_metrics = analysis.get('risk', {})
                if risk_metrics:
                    sharpe_ratios = []
                    var_95_values = []
                    volatilities = []
                    
                    for stock in selected_stocks:
                        analysis = stock.get('analysis', {})
                        risk_data = analysis.get('risk', {})
                        
                        # Handle MCP key names
                        sharpe_ratios.append(risk_data.get('Sharpe_Ratio', risk_data.get('sharpe_ratio', 0)))
                        var_95_values.append(risk_data.get('VaR_95', risk_data.get('var_95', 0)))
                        volatilities.append(risk_data.get('Annual_Volatility', risk_data.get('volatility', 0)))
                
                # Extract sector information from MCP outputs - handle MCP key names
                sector_analysis = analysis.get('sector', {})
                if sector_analysis:
                    sectors.append(sector_analysis.get('Sector', sector_analysis.get('sector', 'UNKNOWN')))
                
                # Extract market cap information from MCP outputs - handle MCP key names
                metrics = analysis.get('metrics', {})
                if metrics:
                    market_cap = metrics.get('Market_Cap', metrics.get('market_cap', 0))
                    if market_cap > 10e9:  # $10B+
                        market_caps.append("large")
                    elif market_cap > 2e9:  # $2B+
                        market_caps.append("mid")
                    else:
                        market_caps.append("small")
                    
                    # Extract dividend yield from MCP outputs - handle MCP key names
                    dividend_yield = metrics.get('Dividend_Yield', metrics.get('dividend_yield', 0))
                    dividend_yields.append(dividend_yield)
                
                # Extract ensemble scores from MCP outputs - handle MCP key names
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_score = ensemble_data.get('ensemble_score', 0)
                    ensemble_scores.append(ensemble_score)
                
                # Extract advanced metrics from MCP outputs - handle MCP key names
                advanced_data = analysis.get('advanced', {})
                if advanced_data:
                    momentum_score = advanced_data.get('momentum_score', 0.5)
                    quality_score = advanced_data.get('quality_score', 0.5)
                    momentum_scores.append(momentum_score)
                    quality_scores.append(quality_score)
            
            # Always extract sector and market cap from analysis if available
            if analysis:
                sector_analysis = analysis.get('sector', {})
                if sector_analysis:
                    sectors.append(sector_analysis.get('sector', 'UNKNOWN'))
                
                metrics = analysis.get('metrics', {})
                if metrics:
                    market_cap = metrics.get('market_cap', 0)
                    if market_cap > 10e9:  # $10B+
                        market_caps.append("large")
                    elif market_cap > 2e9:  # $2B+
                        market_caps.append("mid")
                    else:
                        market_caps.append("small")
                    
                    dividend_yield = metrics.get('dividend_yield', 0)
                    dividend_yields.append(dividend_yield)
        
        # Determine inferred preferences with enhanced logic
        risk_tolerance = "moderate"
        if risk_levels:
            low_count = risk_levels.count("low")
            high_count = risk_levels.count("high")
            if low_count > len(risk_levels) / 2:
                risk_tolerance = "conservative"
            elif high_count > len(risk_levels) / 2:
                risk_tolerance = "aggressive"
        
        # Determine dividend focus
        dividend_focus = False
        if dividend_yields:
            avg_dividend = sum(dividend_yields) / len(dividend_yields)
            dividend_focus = avg_dividend > 0.03  # 3% average dividend yield
        
        # Determine growth focus
        growth_focus = False
        if market_caps:
            small_mid_count = market_caps.count("small") + market_caps.count("mid")
            growth_focus = small_mid_count > len(market_caps) / 2
        
        # Determine momentum focus
        momentum_focus = False
        if momentum_scores:
            avg_momentum = sum(momentum_scores) / len(momentum_scores)
            momentum_focus = avg_momentum > 0.6
        
        # Determine quality focus
        quality_focus = False
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            quality_focus = avg_quality > 0.7
        
        # Determine ensemble confidence
        ensemble_confidence = "moderate"
        if ensemble_scores:
            avg_ensemble = sum(ensemble_scores) / len(ensemble_scores)
            if avg_ensemble > 0.8:
                ensemble_confidence = "high"
            elif avg_ensemble < 0.5:
                ensemble_confidence = "low"
        
        # Enhanced confidence assessment
        overall_confidence = "moderate"
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            if avg_confidence > 0.8:
                overall_confidence = "high"
            elif avg_confidence < 0.5:
                overall_confidence = "low"
        
        # Overall suitability assessment
        overall_suitability = "moderate"
        if suitability_scores:
            avg_suitability = sum(suitability_scores) / len(suitability_scores)
            if avg_suitability > 0.8:
                overall_suitability = "excellent"
            elif avg_suitability > 0.6:
                overall_suitability = "good"
            elif avg_suitability < 0.4:
                overall_suitability = "poor"
        
        return {
            'risk_tolerance': risk_tolerance,
            'investment_horizon': 'long',  # Default for structured products
            'sectors': list(set(sectors)),
            'dividend_focus': dividend_focus,
            'growth_focus': growth_focus,
            'momentum_focus': momentum_focus,
            'quality_focus': quality_focus,
            'ensemble_confidence': ensemble_confidence,
            'overall_confidence': overall_confidence,
            'overall_suitability': overall_suitability,
            'esg_focus': False,  # Default, would be set by user preferences
            'assessment_metrics': {
                'avg_confidence_score': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5,
                'avg_suitability_score': sum(suitability_scores) / len(suitability_scores) if suitability_scores else 0.5,
                'avg_recommendation_score': sum(recommendation_scores) / len(recommendation_scores) if recommendation_scores else 0.5,
                'assessment_count': len([r for r in analyzer_results if r.get('assessment')])
            }
        }
    
    def _create_product_bundle(self, selected_stocks: List[Dict[str, Any]], 
                             user_preferences: Dict[str, Any],
                             processed_query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create the final product bundle with enhanced assessment data and comprehensive summaries."""
        
        # Determine notional amount from processed query first
        notional_amount = 100000.0  # Default $100k
        if processed_query and processed_query.get('capital_amount'):
            notional_amount = processed_query['capital_amount']
        
        # Determine maturity date from investment horizon
        maturity_days = 365  # Default 1 year
        if processed_query:
            investment_horizon = processed_query.get('investment_horizon', 'long')
            horizon_mapping = {
                'short': 90,    # 3 months
                'medium': 180,  # 6 months
                'long': 365     # 1 year
            }
            maturity_days = horizon_mapping.get(investment_horizon, 365)
        
        # Generate product ID
        product_id = f"EQ_BASKET_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine product type
        product_type = self._determine_product_type(selected_stocks)
        
        # Create components with assessment data
        components = []
        assessment_summary = {
            'total_assessments': 0,
            'avg_confidence_score': 0.0,
            'avg_suitability_score': 0.0,
            'avg_recommendation_score': 0.0,
            'risk_distribution': {'low': 0, 'moderate': 0, 'high': 0},
            'recommendation_distribution': {'strong_buy': 0, 'buy': 0, 'hold': 0, 'sell': 0, 'strong_sell': 0}
        }
        
        confidence_scores = []
        suitability_scores = []
        recommendation_scores = []
        text_assessments = []
        
        # Debug logging
        self.logger.info(f"Processing {len(selected_stocks)} selected stocks for assessment summary")
        
        # Create a mapping of symbols to their original analysis data
        # This is needed because selected_stocks only contains scoring info, not assessment data
        original_analysis_data = {}
        if hasattr(self, 'last_analyzer_results'):
            for result in self.last_analyzer_results:
                symbol = result.get('symbol', '')
                if symbol:
                    original_analysis_data[symbol] = result
        
        for i, stock in enumerate(selected_stocks):
            symbol = stock.get('symbol', 'UNKNOWN')
            
            # Get original analysis data for this stock
            original_data = original_analysis_data.get(symbol, {})
            assessment = original_data.get('assessment', {})
            
            # Debug logging for each stock
            self.logger.info(f"Stock {i+1}: {symbol} - Has assessment: {bool(assessment)}")
            
            if assessment:
                assessment_summary['total_assessments'] += 1
                
                # Get assessment metrics with better error handling
                confidence_score = 0.5
                suitability_score = 0.5
                recommendation_score = 0.5
                
                try:
                    confidence_score = assessment.get('confidence_score', {}).get('confidence_score', 0.5)
                    suitability_score = assessment.get('suitability_score', {}).get('suitability_score', 0.5)
                    recommendation_score = assessment.get('investment_recommendation', {}).get('score', 0.5)
                except (TypeError, AttributeError) as e:
                    self.logger.warning(f"Error extracting assessment metrics for {symbol}: {e}")
                
                confidence_scores.append(confidence_score)
                suitability_scores.append(suitability_score)
                recommendation_scores.append(recommendation_score)
                
                # Collect text assessments
                text_assessment = assessment.get('text_assessment', '') if assessment else ''
                if text_assessment:
                    text_assessments.append({
                        'symbol': symbol,
                        'assessment': text_assessment
                    })
                
                # Track risk and recommendation distributions with better error handling
                try:
                    risk_level = assessment.get('risk_assessment', {}).get('risk_level', 'MODERATE').lower()
                    if risk_level in assessment_summary['risk_distribution']:
                        assessment_summary['risk_distribution'][risk_level] += 1
                    
                    recommendation = assessment.get('investment_recommendation', {}).get('recommendation', 'HOLD').lower()
                    recommendation_key = recommendation.replace('_', '').lower()
                    if recommendation_key in assessment_summary['recommendation_distribution']:
                        assessment_summary['recommendation_distribution'][recommendation_key] += 1
                except (TypeError, AttributeError) as e:
                    self.logger.warning(f"Error tracking distributions for {symbol}: {e}")
            else:
                # Use default scores for stocks without assessments
                confidence_scores.append(0.5)
                suitability_scores.append(0.5)
                recommendation_scores.append(0.5)
            
            # Create enhanced component with assessment data
            component = {
                "component_id": f"COMP_{symbol}_{i}",
                "asset_type": "EQUITY",
                "underlying_asset": symbol,
                "weight": stock['weight'],
                "score": stock['total_score'],
                "retention_reason": stock['retention_reason']
            }
            
            # Add price data to component if available
            price_data = original_data.get('price_data', {})
            if price_data:
                component.update({
                    "price_data": {
                        "current_price": price_data.get('current_price'),
                        "current_date": price_data.get('current_date'),
                        "predicted_price": price_data.get('predicted_price'),
                        "predicted_date": price_data.get('predicted_date'),
                        "price_change": price_data.get('price_change'),
                        "price_change_pct": price_data.get('price_change_pct')
                    }
                })
            
            # Add assessment data to component if available
            if assessment:
                component.update({
                    "assessment": {
                        "investment_recommendation": assessment.get('investment_recommendation', {}),
                        "risk_assessment": assessment.get('risk_assessment', {}),
                        "confidence_score": assessment.get('confidence_score', {}),
                        "suitability_score": assessment.get('suitability_score', {}),
                        "insights": assessment.get('insights', {}),
                        "text_assessment": assessment.get('text_assessment', '')
                    },
                    "assessment_metrics": {
                        "confidence_score": confidence_score,
                        "suitability_score": suitability_score,
                        "recommendation_score": recommendation_score
                    }
                })
            
            components.append(component)
        
        # Calculate assessment summary metrics with better error handling
        if confidence_scores:
            assessment_summary['avg_confidence_score'] = sum(confidence_scores) / len(confidence_scores)
        if suitability_scores:
            assessment_summary['avg_suitability_score'] = sum(suitability_scores) / len(suitability_scores)
        if recommendation_scores:
            assessment_summary['avg_recommendation_score'] = sum(recommendation_scores) / len(recommendation_scores)
        
        # Debug logging for final assessment summary
        self.logger.info(f"Final assessment summary: {assessment_summary}")
        self.logger.info(f"Total components: {len(components)}")
        self.logger.info(f"Text assessments: {len(text_assessments)}")
        
        # Debug logging for original analysis data
        self.logger.info(f"Original analysis data keys: {list(original_analysis_data.keys())}")
        for symbol, data in original_analysis_data.items():
            has_assessment = bool(data.get('assessment'))
            self.logger.info(f"  {symbol}: has_assessment={has_assessment}")
        
        # Calculate risk profile and performance metrics
        risk_profile = self._calculate_risk_profile(selected_stocks)
        performance_metrics = self._calculate_performance_metrics(selected_stocks)
        
        # Generate comprehensive product summary
        product_summary = self._generate_product_summary(
            selected_stocks, assessment_summary, user_preferences, processed_query, text_assessments
        )
        
        # Generate enhanced summaries using summarizer agent if available
        enhanced_product_summary = product_summary
        enhanced_individual_assessments = text_assessments
        executive_summary = ""
        risk_summary = ""
        recommendation_summary = ""
        
        if self.use_summarizer and self.summarizer:
            try:
                # Create portfolio data for summarizer
                portfolio_data = {
                    'assessment_summary': assessment_summary,
                    'product_summary': product_summary,
                    'individual_assessments': text_assessments,
                    'user_preferences': user_preferences,
                    'product': {
                        'product_type': product_type,
                        'notional_amount': notional_amount,
                        'components': components
                    },
                    'processed_query': processed_query
                }
                
                # Generate enhanced summaries using summarizer
                enhanced_product_summary = self.summarizer.generate_portfolio_summary(portfolio_data)
                executive_summary = self.summarizer.generate_executive_summary(portfolio_data)
                risk_summary = self.summarizer.generate_risk_summary(portfolio_data)
                recommendation_summary = self.summarizer.generate_recommendation_summary(portfolio_data)
                
                # Generate enhanced individual stock summaries
                enhanced_individual_assessments = []
                for stock in selected_stocks:
                    symbol = stock.get('symbol', '')
                    original_data = original_analysis_data.get(symbol, {})
                    if original_data.get('assessment'):
                        enhanced_stock_summary = self.summarizer.generate_stock_summary(original_data)
                        enhanced_individual_assessments.append({
                            'symbol': symbol,
                            'original_assessment': original_data.get('assessment', {}).get('text_assessment', ''),
                            'enhanced_summary': enhanced_stock_summary
                        })
                
                self.logger.info("Enhanced summaries generated successfully using summarizer agent")
                
            except Exception as e:
                self.logger.error(f"Failed to generate enhanced summaries: {e}")
                # Fallback to template-based summaries
                enhanced_product_summary = product_summary
                enhanced_individual_assessments = text_assessments
                executive_summary = self._generate_template_executive_summary(assessment_summary, user_preferences, {'product_type': product_type, 'notional_amount': notional_amount, 'components': components})
                risk_summary = self._generate_template_risk_summary(assessment_summary, text_assessments, user_preferences)
                recommendation_summary = self._generate_template_recommendation_summary(assessment_summary, text_assessments, user_preferences)
        else:
            # Use template-based summaries
            enhanced_product_summary = product_summary
            enhanced_individual_assessments = text_assessments
            executive_summary = self._generate_template_executive_summary(assessment_summary, user_preferences, {'product_type': product_type, 'notional_amount': notional_amount, 'components': components})
            risk_summary = self._generate_template_risk_summary(assessment_summary, text_assessments, user_preferences)
            recommendation_summary = self._generate_template_recommendation_summary(assessment_summary, text_assessments, user_preferences)
        
        # Create product structure
        product = {
            "product_id": product_id,
            "product_type": product_type,
            "product_name": f"Structured Equity Basket - {product_type}",
            "issuer": "STRUCTURED_EQUITIES_PLATFORM",
            "issue_date": datetime.now().isoformat(),
            "maturity_date": (datetime.now() + timedelta(days=maturity_days)).isoformat(),
            "currency": "USD",
            "notional_amount": notional_amount,
            "components": components,
            "risk_profile": risk_profile,
            "performance_metrics": performance_metrics,
            "regulatory_classification": "RETAIL",
            "tax_status": "TAXABLE"
        }
        
        # Get template info
        template_info = self.product_templates.get(product_type, {})
        
        # Create final bundle with assessment data and enhanced summaries
        product_bundle = {
            "success": True,
            "product": product,
            "template_info": template_info,
            "user_preferences": user_preferences,
            "assessment_summary": assessment_summary,
            "product_summary": enhanced_product_summary,
            "individual_assessments": enhanced_individual_assessments,
            "executive_summary": executive_summary,
            "risk_summary": risk_summary,
            "recommendation_summary": recommendation_summary,
            "creation_timestamp": datetime.now().isoformat(),
            "cdm_compliance": {
                "standard": "FINOS CDM 6.0.0",
                "compliance_level": "FULL",
                "product_model": "EQUITY_BASKET",
                "event_model": "TRADE_EVENTS",
                "legal_agreements": "STANDARD_ISDA"
            }
        }
        
        return product_bundle
    
    def _determine_product_type(self, selected_stocks: List[Dict[str, Any]]) -> str:
        """Determine product type based on selected stocks."""
        
        if not selected_stocks:
            return "BALANCED_EQUITY_BASKET"
        
        # Calculate average risk score
        avg_risk_score = sum(stock['risk_score'] for stock in selected_stocks) / len(selected_stocks)
        
        if avg_risk_score > 0.7:
            return "CONSERVATIVE_EQUITY_BASKET"
        elif avg_risk_score < 0.4:
            return "AGGRESSIVE_EQUITY_BASKET"
        else:
            return "BALANCED_EQUITY_BASKET"
    
    def _calculate_risk_profile(self, selected_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk profile for selected stocks using MCP outputs."""
        
        if not selected_stocks:
            return {"risk_level": "MEDIUM", "volatility": 0.0, "var_95": 0.0}
        
        # Calculate weighted average risk metrics from MCP outputs
        total_weight = sum(stock['weight'] for stock in selected_stocks)
        
        weighted_risk_score = sum(stock['risk_score'] * stock['weight'] for stock in selected_stocks) / total_weight
        
        # Extract MCP risk metrics
        sharpe_ratios = []
        var_95_values = []
        volatilities = []
        max_drawdowns = []
        stress_scores = []
        regime_probabilities = []
        ensemble_scores = []
        
        for stock in selected_stocks:
            analysis = stock.get('analysis', {})
            if analysis:
                risk_data = analysis.get('risk', {})
                if risk_data:
                    sharpe_ratios.append(risk_data.get('sharpe_ratio', 0))
                    var_95_values.append(risk_data.get('var_95', 0))
                    volatilities.append(risk_data.get('volatility', 0))
                    max_drawdowns.append(risk_data.get('max_drawdown', 0))
                
                stress_data = analysis.get('stress', {})
                if stress_data:
                    stress_scores.append(stress_data.get('stress_score', 0))
                
                regime_data = analysis.get('regime', {})
                if regime_data:
                    regime_probabilities.append(regime_data.get('regime_probability', 0.5))
                
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_scores.append(ensemble_data.get('ensemble_score', 0))
        
        # Calculate aggregate metrics
        avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0
        avg_var_95 = sum(var_95_values) / len(var_95_values) if var_95_values else 0
        avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0
        avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
        avg_stress_score = sum(stress_scores) / len(stress_scores) if stress_scores else 0
        avg_regime_probability = sum(regime_probabilities) / len(regime_probabilities) if regime_probabilities else 0.5
        avg_ensemble_score = sum(ensemble_scores) / len(ensemble_scores) if ensemble_scores else 0
        
        # Determine risk level based on MCP metrics
        if avg_sharpe > 1.5 and avg_var_95 < 0.02 and avg_volatility < 0.15:
            risk_level = "LOW"
        elif avg_sharpe > 0.8 and avg_var_95 < 0.05 and avg_volatility < 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        # Calculate diversification score
        unique_symbols = set(stock['symbol'] for stock in selected_stocks)
        diversification_score = len(unique_symbols) / len(selected_stocks)
        
        # Determine market regime
        if avg_regime_probability > 0.7:
            market_regime = "BULL_MARKET"
        elif avg_regime_probability < 0.3:
            market_regime = "BEAR_MARKET"
        else:
            market_regime = "NEUTRAL_MARKET"
        
        return {
            "risk_level": risk_level,
            "weighted_risk_score": weighted_risk_score,
            "diversification_score": diversification_score,
            "market_regime": market_regime,
            "ensemble_confidence": avg_ensemble_score,
            "stress_resilience": 1.0 - avg_stress_score,  # Higher is better
            "risk_metrics": {
                "sharpe_ratio": avg_sharpe,
                "var_95": avg_var_95,
                "volatility": avg_volatility,
                "max_drawdown": avg_max_drawdown
            },
            "regime_probability": avg_regime_probability
        }
    
    def _calculate_performance_metrics(self, selected_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall performance metrics for the product using MCP outputs."""
        
        if not selected_stocks:
            return {"expected_return": 0.0, "volatility": 0.0, "sharpe_ratio": 0.0}
        
        # Extract performance metrics from MCP outputs
        signals = []
        pe_ratios = []
        dividend_yields = []
        market_caps = []
        momentum_scores = []
        quality_scores = []
        ensemble_scores = []
        
        for stock in selected_stocks:
            analysis = stock.get('analysis', {})
            if analysis:
                # Extract trading signals - handle MCP key names
                signal_data = analysis.get('signals', {})
                if signal_data:
                    overall_signal = signal_data.get('overall', signal_data.get('Overall', 'NEUTRAL'))
                    signals.append(overall_signal)
                
                # Extract financial metrics - handle MCP key names
                metrics_data = analysis.get('metrics', {})
                if metrics_data:
                    pe_ratios.append(metrics_data.get('P/E_Ratio', metrics_data.get('pe_ratio', 0)))
                    dividend_yields.append(metrics_data.get('Dividend_Yield', metrics_data.get('dividend_yield', 0)))
                    market_caps.append(metrics_data.get('Market_Cap', metrics_data.get('market_cap', 0)))
                
                # Extract advanced metrics - handle MCP key names
                advanced_data = analysis.get('advanced', {})
                if advanced_data:
                    momentum_scores.append(advanced_data.get('momentum_score', 0))
                    quality_scores.append(advanced_data.get('quality_score', 0))
                
                # Extract ensemble metrics - handle MCP key names
                ensemble_data = analysis.get('ensemble', {})
                if ensemble_data:
                    ensemble_scores.append(ensemble_data.get('ensemble_score', 0))
        
        # Calculate aggregate metrics
        avg_pe_ratio = sum(pe_ratios) / len(pe_ratios) if pe_ratios else 0
        avg_dividend_yield = sum(dividend_yields) / len(dividend_yields) if dividend_yields else 0
        avg_market_cap = sum(market_caps) / len(market_caps) if market_caps else 0
        avg_momentum = sum(momentum_scores) / len(momentum_scores) if momentum_scores else 0
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        avg_ensemble = sum(ensemble_scores) / len(ensemble_scores) if ensemble_scores else 0
        
        # Calculate signal distribution
        buy_signals = signals.count('BUY') if signals else 0
        sell_signals = signals.count('SELL') if signals else 0
        neutral_signals = signals.count('NEUTRAL') if signals else 0
        total_signals = len(signals)
        
        signal_strength = (buy_signals - sell_signals) / total_signals if total_signals > 0 else 0
        
        # Estimate expected return based on MCP metrics
        # Base return from dividend yield
        base_return = avg_dividend_yield
        
        # Momentum premium
        momentum_premium = avg_momentum * 0.05  # 5% max momentum premium
        
        # Quality premium
        quality_premium = avg_quality * 0.03  # 3% max quality premium
        
        # Ensemble confidence premium
        ensemble_premium = avg_ensemble * 0.02  # 2% max ensemble premium
        
        # Signal strength premium
        signal_premium = signal_strength * 0.04  # 4% max signal premium
        
        expected_return = base_return + momentum_premium + quality_premium + ensemble_premium + signal_premium
        
        # Calculate risk-adjusted metrics
        risk_profile = self._calculate_risk_profile(selected_stocks)
        volatility = risk_profile.get('risk_metrics', {}).get('volatility', 0.15)
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0
        
        return {
            "expected_return": expected_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "signal_analysis": {
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "neutral_signals": neutral_signals,
                "signal_strength": signal_strength
            },
            "financial_metrics": {
                "avg_pe_ratio": avg_pe_ratio,
                "avg_dividend_yield": avg_dividend_yield,
                "avg_market_cap": avg_market_cap
            },
            "advanced_metrics": {
                "avg_momentum_score": avg_momentum,
                "avg_quality_score": avg_quality,
                "avg_ensemble_score": avg_ensemble
            },
            "return_components": {
                "base_return": base_return,
                "momentum_premium": momentum_premium,
                "quality_premium": quality_premium,
                "ensemble_premium": ensemble_premium,
                "signal_premium": signal_premium
            }
        }
    
    def _generate_product_summary(self, selected_stocks: List[Dict[str, Any]], 
                                 assessment_summary: Dict[str, Any],
                                 user_preferences: Dict[str, Any],
                                 processed_query: Dict[str, Any],
                                 text_assessments: List[Dict[str, Any]]) -> str:
        """Generate comprehensive product summary based on assessment data and individual stock assessments."""
        
        # Extract key information
        total_stocks = len(selected_stocks)
        product_type = self._determine_product_type(selected_stocks)
        
        # Assessment metrics
        avg_confidence = assessment_summary.get('avg_confidence_score', 0.5)
        avg_suitability = assessment_summary.get('avg_suitability_score', 0.5)
        avg_recommendation = assessment_summary.get('avg_recommendation_score', 0.5)
        
        # Risk distribution
        risk_dist = assessment_summary.get('risk_distribution', {})
        low_risk_count = risk_dist.get('low', 0)
        moderate_risk_count = risk_dist.get('moderate', 0)
        high_risk_count = risk_dist.get('high', 0)
        
        # Recommendation distribution
        rec_dist = assessment_summary.get('recommendation_distribution', {})
        strong_buy_count = rec_dist.get('strong_buy', 0)
        buy_count = rec_dist.get('buy', 0)
        hold_count = rec_dist.get('hold', 0)
        sell_count = rec_dist.get('sell', 0)
        strong_sell_count = rec_dist.get('strong_sell', 0)
        
        # User preferences
        risk_tolerance = user_preferences.get('risk_tolerance', 'moderate')
        investment_horizon = user_preferences.get('investment_horizon', 'long')
        capital_amount = processed_query.get('capital_amount', 100000.0) if processed_query else 100000.0
        
        # Calculate portfolio characteristics
        total_weight = sum(stock.get('weight', 0) for stock in selected_stocks)
        avg_weight = total_weight / total_stocks if total_stocks > 0 else 0
        
        # Generate comprehensive summary
        summary = f"""
# Structured Equity Product Summary

## Product Overview
**Product Type**: {product_type}
**Total Components**: {total_stocks} stocks
**Investment Amount**: ${capital_amount:,.2f}
**Target Investor**: {risk_tolerance.title()} risk tolerance, {investment_horizon}-term horizon
**Creation Date**: {datetime.now().strftime('%B %d, %Y')}

## Portfolio Assessment Summary
**Overall Confidence**: {avg_confidence:.1%} ({self._get_confidence_level(avg_confidence)})
**Overall Suitability**: {avg_suitability:.1%} ({self._get_suitability_level(avg_suitability)})
**Average Recommendation Score**: {avg_recommendation:.1%}

## Risk Profile Distribution
- **Low Risk**: {low_risk_count} stocks ({low_risk_count/total_stocks*100:.1f}%)
- **Moderate Risk**: {moderate_risk_count} stocks ({moderate_risk_count/total_stocks*100:.1f}%)
- **High Risk**: {high_risk_count} stocks ({high_risk_count/total_stocks*100:.1f}%)

## Investment Recommendation Distribution
- **Strong Buy**: {strong_buy_count} stocks ({strong_buy_count/total_stocks*100:.1f}%)
- **Buy**: {buy_count} stocks ({buy_count/total_stocks*100:.1f}%)
- **Hold**: {hold_count} stocks ({hold_count/total_stocks*100:.1f}%)
- **Sell**: {sell_count} stocks ({sell_count/total_stocks*100:.1f}%)
- **Strong Sell**: {strong_sell_count} stocks ({strong_sell_count/total_stocks*100:.1f}%)

## Portfolio Characteristics
**Average Component Weight**: {avg_weight:.1%}
**Diversification Level**: {self._assess_diversification(selected_stocks)}
**Sector Exposure**: {self._get_sector_exposure(selected_stocks)}
**Market Cap Distribution**: {self._get_market_cap_distribution(selected_stocks)}

## Key Strengths
{self._identify_portfolio_strengths(selected_stocks, assessment_summary)}

## Risk Considerations
{self._identify_portfolio_risks(selected_stocks, assessment_summary)}

## Investment Thesis
This {product_type.lower().replace('_', ' ')} is designed for {risk_tolerance} investors seeking {investment_horizon}-term growth. 
The portfolio demonstrates {self._get_portfolio_characteristics(avg_confidence, avg_suitability, avg_recommendation)} 
with a balanced risk-reward profile appropriate for the target investor profile.

## Expected Performance
Based on the assessment data, this portfolio is expected to deliver:
- **Risk-Adjusted Returns**: {self._estimate_risk_adjusted_returns(assessment_summary)}
- **Volatility Profile**: {self._estimate_volatility_profile(assessment_summary)}
- **Downside Protection**: {self._estimate_downsides_protection(assessment_summary)}

## Individual Stock Highlights
{self._generate_stock_highlights(selected_stocks, text_assessments)}

## Regulatory Compliance
This product complies with FINOS CDM 6.0.0 standards and is classified as a RETAIL investment product. 
All components are subject to standard market risks and regulatory oversight.

## Conclusion
This structured equity product offers a {self._get_overall_assessment(avg_confidence, avg_suitability, avg_recommendation)} 
investment opportunity for {risk_tolerance} investors. The portfolio's {avg_confidence:.1%} confidence level 
and {avg_suitability:.1%} suitability score indicate strong alignment with the target investor profile.
"""
        
        return summary.strip()
    
    def _get_confidence_level(self, score: float) -> str:
        """Get confidence level description."""
        if score >= 0.8:
            return "High Confidence"
        elif score >= 0.6:
            return "Moderate Confidence"
        else:
            return "Low Confidence"
    
    def _get_suitability_level(self, score: float) -> str:
        """Get suitability level description."""
        if score >= 0.8:
            return "Excellent Suitability"
        elif score >= 0.6:
            return "Good Suitability"
        elif score >= 0.4:
            return "Fair Suitability"
        else:
            return "Poor Suitability"
    
    def _assess_diversification(self, selected_stocks: List[Dict[str, Any]]) -> str:
        """Assess portfolio diversification level."""
        if len(selected_stocks) >= 20:
            return "High (Well-diversified across multiple stocks)"
        elif len(selected_stocks) >= 10:
            return "Moderate (Good diversification)"
        else:
            return "Low (Concentrated portfolio)"
    
    def _get_sector_exposure(self, selected_stocks: List[Dict[str, Any]]) -> str:
        """Get sector exposure summary."""
        sectors = {}
        for stock in selected_stocks:
            assessment = stock.get('assessment', {})
            if assessment:
                sector_info = assessment.get('analysis', {}).get('sector', {})
                sector_name = sector_info.get('sector', 'Unknown')
                sectors[sector_name] = sectors.get(sector_name, 0) + 1
        
        if sectors:
            top_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3]
            sector_list = [f"{sector} ({count})" for sector, count in top_sectors]
            return ", ".join(sector_list)
        else:
            return "Diversified across sectors"
    
    def _get_market_cap_distribution(self, selected_stocks: List[Dict[str, Any]]) -> str:
        """Get market cap distribution summary."""
        large_cap = 0
        mid_cap = 0
        small_cap = 0
        
        for stock in selected_stocks:
            assessment = stock.get('assessment', {})
            if assessment:
                metrics = assessment.get('analysis', {}).get('metrics', {})
                market_cap = metrics.get('market_cap', 0)
                if market_cap > 10e9:
                    large_cap += 1
                elif market_cap > 2e9:
                    mid_cap += 1
                else:
                    small_cap += 1
        
        return f"Large Cap: {large_cap}, Mid Cap: {mid_cap}, Small Cap: {small_cap}"
    
    def _identify_portfolio_strengths(self, selected_stocks: List[Dict[str, Any]], assessment_summary: Dict[str, Any]) -> str:
        """Identify portfolio strengths."""
        strengths = []
        
        avg_confidence = assessment_summary.get('avg_confidence_score', 0.5)
        avg_suitability = assessment_summary.get('avg_suitability_score', 0.5)
        
        if avg_confidence > 0.7:
            strengths.append("High model confidence across portfolio components")
        if avg_suitability > 0.7:
            strengths.append("Excellent alignment with target investor profile")
        if len(selected_stocks) >= 15:
            strengths.append("Strong diversification reducing concentration risk")
        
        # Check for strong buy signals
        strong_buy_count = assessment_summary.get('recommendation_distribution', {}).get('strong_buy', 0)
        if strong_buy_count > len(selected_stocks) * 0.3:
            strengths.append("Significant number of strong buy recommendations")
        
        return '\n'.join([f"- {strength}" for strength in strengths]) if strengths else "- Balanced risk-reward profile"
    
    def _identify_portfolio_risks(self, selected_stocks: List[Dict[str, Any]], assessment_summary: Dict[str, Any]) -> str:
        """Identify portfolio risks."""
        risks = []
        
        high_risk_count = assessment_summary.get('risk_distribution', {}).get('high', 0)
        if high_risk_count > len(selected_stocks) * 0.3:
            risks.append("Significant exposure to high-risk stocks")
        
        sell_count = assessment_summary.get('recommendation_distribution', {}).get('sell', 0)
        strong_sell_count = assessment_summary.get('recommendation_distribution', {}).get('strong_sell', 0)
        if sell_count + strong_sell_count > 0:
            risks.append("Some components have sell recommendations")
        
        if len(selected_stocks) < 10:
            risks.append("Limited diversification may increase concentration risk")
        
        return '\n'.join([f"- {risk}" for risk in risks]) if risks else "- Standard market risks apply"
    
    def _get_portfolio_characteristics(self, confidence: float, suitability: float, recommendation: float) -> str:
        """Get portfolio characteristics description."""
        characteristics = []
        
        if confidence > 0.7:
            characteristics.append("high confidence")
        if suitability > 0.7:
            characteristics.append("excellent suitability")
        if recommendation > 0.6:
            characteristics.append("strong investment recommendations")
        
        if not characteristics:
            characteristics = ["balanced characteristics"]
        
        return ", ".join(characteristics)
    
    def _estimate_risk_adjusted_returns(self, assessment_summary: Dict[str, Any]) -> str:
        """Estimate risk-adjusted returns."""
        avg_recommendation = assessment_summary.get('avg_recommendation_score', 0.5)
        
        if avg_recommendation > 0.7:
            return "Above-average risk-adjusted returns expected"
        elif avg_recommendation > 0.5:
            return "Moderate risk-adjusted returns expected"
        else:
            return "Below-average risk-adjusted returns expected"
    
    def _estimate_volatility_profile(self, assessment_summary: Dict[str, Any]) -> str:
        """Estimate volatility profile."""
        risk_dist = assessment_summary.get('risk_distribution', {})
        high_risk = risk_dist.get('high', 0)
        total = sum(risk_dist.values())
        
        if total > 0:
            high_risk_pct = high_risk / total
            if high_risk_pct > 0.4:
                return "Higher volatility expected"
            elif high_risk_pct < 0.2:
                return "Lower volatility expected"
            else:
                return "Moderate volatility expected"
        else:
            return "Moderate volatility expected"
    
    def _estimate_downsides_protection(self, assessment_summary: Dict[str, Any]) -> str:
        """Estimate downside protection."""
        low_risk = assessment_summary.get('risk_distribution', {}).get('low', 0)
        total = sum(assessment_summary.get('risk_distribution', {}).values())
        
        if total > 0 and low_risk / total > 0.4:
            return "Good downside protection from low-risk components"
        else:
            return "Standard downside protection"
    
    def _generate_stock_highlights(self, selected_stocks: List[Dict[str, Any]], text_assessments: List[Dict[str, Any]]) -> str:
        """Generate stock highlights from text assessments."""
        if not text_assessments:
            return "Individual stock assessments not available."
        
        highlights = []
        for i, assessment in enumerate(text_assessments[:5]):  # Show top 5
            symbol = assessment.get('symbol', '')
            text = assessment.get('assessment', '')
            
            # Extract key points from text assessment
            lines = text.split('\n')
            summary_line = ""
            for line in lines:
                if "Executive Summary" in line or "Recommendation" in line:
                    summary_line = line.strip()
                    break
            
            if summary_line:
                highlights.append(f"**{symbol}**: {summary_line}")
            else:
                highlights.append(f"**{symbol}**: Assessment available")
        
        if len(text_assessments) > 5:
            highlights.append(f"... and {len(text_assessments) - 5} more detailed assessments")
        
        return '\n'.join(highlights)
    
    def _get_overall_assessment(self, confidence: float, suitability: float, recommendation: float) -> str:
        """Get overall assessment description."""
        if confidence > 0.7 and suitability > 0.7 and recommendation > 0.6:
            return "compelling"
        elif confidence > 0.6 and suitability > 0.6 and recommendation > 0.5:
            return "attractive"
        else:
            return "balanced"
    
    def _generate_template_executive_summary(self, assessment_summary: Dict[str, Any], 
                                           user_preferences: Dict[str, Any], 
                                           product: Dict[str, Any]) -> str:
        """Generate template-based executive summary."""
        avg_confidence = assessment_summary.get('avg_confidence_score', 0.5)
        avg_suitability = assessment_summary.get('avg_suitability_score', 0.5)
        avg_recommendation = assessment_summary.get('avg_recommendation_score', 0.5)
        risk_dist = assessment_summary.get('risk_distribution', {})
        rec_dist = assessment_summary.get('recommendation_distribution', {})
        
        return f"""
# Executive Summary

## Investment Opportunity
This {product.get('product_type', 'UNKNOWN').lower().replace('_', ' ')} offers a balanced investment opportunity 
for {user_preferences.get('risk_tolerance', 'moderate')} investors with a {user_preferences.get('investment_horizon', 'long')}-term horizon.

## Key Metrics
- **Portfolio Confidence**: {avg_confidence:.1%}
- **Investor Suitability**: {avg_suitability:.1%}
- **Investment Recommendation**: {avg_recommendation:.1%}
- **Total Components**: {len(product.get('components', []))} stocks
- **Investment Amount**: ${product.get('notional_amount', 100000.0):,.2f}

## Risk-Reward Profile
The portfolio demonstrates appropriate risk management with {self._get_risk_summary(risk_dist)} 
risk distribution and {self._get_recommendation_summary(rec_dist)} 
investment recommendations.

## Recommendation
This portfolio represents a compelling investment opportunity with strong alignment 
to the target investor profile and appropriate risk management.
"""
    
    def _generate_template_risk_summary(self, assessment_summary: Dict[str, Any], 
                                      text_assessments: List[Dict[str, Any]], 
                                      user_preferences: Dict[str, Any]) -> str:
        """Generate template-based risk summary."""
        risk_dist = assessment_summary.get('risk_distribution', {})
        total = sum(risk_dist.values())
        
        return f"""
# Risk Analysis Summary

## Risk Distribution
- **Low Risk**: {risk_dist.get('low', 0)} stocks ({(risk_dist.get('low', 0)/total*100) if total > 0 else 0:.1f}%)
- **Moderate Risk**: {risk_dist.get('moderate', 0)} stocks ({(risk_dist.get('moderate', 0)/total*100) if total > 0 else 0:.1f}%)
- **High Risk**: {risk_dist.get('high', 0)} stocks ({(risk_dist.get('high', 0)/total*100) if total > 0 else 0:.1f}%)

## Risk Assessment
This portfolio demonstrates {self._get_risk_profile(risk_dist)} risk characteristics, 
which is {self._get_risk_suitability(risk_dist, user_preferences.get('risk_tolerance', 'moderate'))} for {user_preferences.get('risk_tolerance', 'moderate')} investors.

## Risk Management
The portfolio includes appropriate diversification across {len(text_assessments)} stocks 
to mitigate concentration risk and provide balanced exposure.
"""
    
    def _generate_template_recommendation_summary(self, assessment_summary: Dict[str, Any], 
                                                text_assessments: List[Dict[str, Any]], 
                                                user_preferences: Dict[str, Any]) -> str:
        """Generate template-based recommendation summary."""
        rec_dist = assessment_summary.get('recommendation_distribution', {})
        total = sum(rec_dist.values())
        avg_recommendation = assessment_summary.get('avg_recommendation_score', 0.5)
        
        return f"""
# Investment Recommendation Summary

## Recommendation Distribution
- **Strong Buy**: {rec_dist.get('strong_buy', 0)} stocks ({(rec_dist.get('strong_buy', 0)/total*100) if total > 0 else 0:.1f}%)
- **Buy**: {rec_dist.get('buy', 0)} stocks ({(rec_dist.get('buy', 0)/total*100) if total > 0 else 0:.1f}%)
- **Hold**: {rec_dist.get('hold', 0)} stocks ({(rec_dist.get('hold', 0)/total*100) if total > 0 else 0:.1f}%)
- **Sell**: {rec_dist.get('sell', 0)} stocks ({(rec_dist.get('sell', 0)/total*100) if total > 0 else 0:.1f}%)
- **Strong Sell**: {rec_dist.get('strong_sell', 0)} stocks ({(rec_dist.get('strong_sell', 0)/total*100) if total > 0 else 0:.1f}%)

## Overall Assessment
The portfolio shows an average recommendation score of {avg_recommendation:.1%}, 
indicating {self._get_recommendation_strength(avg_recommendation)} investment opportunities.

## Investment Thesis
This portfolio is well-suited for {user_preferences.get('risk_tolerance', 'moderate')} investors with a {user_preferences.get('investment_horizon', 'long')}-term horizon, 
offering {self._get_investment_characteristics(rec_dist)} investment characteristics.
"""
    
    def _get_risk_summary(self, risk_dist: Dict[str, int]) -> str:
        """Get risk summary description."""
        low = risk_dist.get('low', 0)
        moderate = risk_dist.get('moderate', 0)
        high = risk_dist.get('high', 0)
        total = low + moderate + high
        
        if total == 0:
            return "balanced"
        
        if low > high and low > moderate:
            return "conservative"
        elif high > low and high > moderate:
            return "aggressive"
        else:
            return "balanced"
    
    def _get_recommendation_summary(self, rec_dist: Dict[str, int]) -> str:
        """Get recommendation summary description."""
        strong_buy = rec_dist.get('strong_buy', 0)
        buy = rec_dist.get('buy', 0)
        sell = rec_dist.get('sell', 0)
        strong_sell = rec_dist.get('strong_sell', 0)
        
        positive = strong_buy + buy
        negative = sell + strong_sell
        
        if positive > negative:
            return "positive"
        elif negative > positive:
            return "negative"
        else:
            return "neutral"
    
    def _get_risk_profile(self, risk_dist: Dict[str, int]) -> str:
        """Get risk profile description."""
        high = risk_dist.get('high', 0)
        total = sum(risk_dist.values())
        
        if total == 0:
            return "balanced"
        
        high_pct = high / total
        if high_pct > 0.4:
            return "higher"
        elif high_pct < 0.2:
            return "lower"
        else:
            return "moderate"
    
    def _get_risk_suitability(self, risk_dist: Dict[str, int], risk_tolerance: str) -> str:
        """Get risk suitability description."""
        high = risk_dist.get('high', 0)
        total = sum(risk_dist.values())
        
        if total == 0:
            return "appropriate"
        
        high_pct = high / total
        
        if risk_tolerance == 'conservative' and high_pct > 0.3:
            return "inappropriate"
        elif risk_tolerance == 'aggressive' and high_pct < 0.2:
            return "too conservative"
        else:
            return "appropriate"
    
    def _get_recommendation_strength(self, avg_score: float) -> str:
        """Get recommendation strength description."""
        if avg_score > 0.7:
            return "strong"
        elif avg_score > 0.5:
            return "moderate"
        else:
            return "weak"
    
    def _get_investment_characteristics(self, rec_dist: Dict[str, int]) -> str:
        """Get investment characteristics description."""
        strong_buy = rec_dist.get('strong_buy', 0)
        buy = rec_dist.get('buy', 0)
        total = sum(rec_dist.values())
        
        if total == 0:
            return "balanced"
        
        positive_pct = (strong_buy + buy) / total
        if positive_pct > 0.6:
            return "strong positive"
        elif positive_pct > 0.4:
            return "moderate positive"
        else:
            return "balanced"

    def create_product_documentation(self, product_bundle: Dict[str, Any]) -> str:
        """
        Create human-readable documentation for the structured product.
        
        Args:
            product_bundle: The product bundle from bundle_product
            
        Returns:
            Formatted documentation string
        """
        try:
            product = product_bundle.get('product', {})
            template_info = product_bundle.get('template_info', {})
            stock_selection = product_bundle.get('stock_selection', {})
            
            doc = f"""
# Structured Equity Product Documentation

## Product Overview
- **Product ID**: {product.get('product_id', 'N/A')}
- **Product Type**: {product.get('product_type', 'N/A')}
- **Product Name**: {product.get('product_name', 'N/A')}
- **Issuer**: {product.get('issuer', 'N/A')}
- **Issue Date**: {product.get('issue_date', 'N/A')}
- **Maturity Date**: {product.get('maturity_date', 'N/A')}
- **Currency**: {product.get('currency', 'USD')}
- **Notional Amount**: ${product.get('notional_amount', 0):,.2f}

## Product Description
{template_info.get('description', 'N/A')}

## Investment Profile
- **Target Return**: {template_info.get('target_return', 'N/A')}
- **Risk Level**: {template_info.get('risk_level', 'N/A')}
- **Suitable For**: {template_info.get('suitable_for', 'N/A')}

## Stock Selection Summary
- **Total Candidates**: {stock_selection.get('total_candidates', 0)}
- **Selected Stocks**: {stock_selection.get('selected_count', 0)}
- **Selection Efficiency**: {stock_selection.get('selection_efficiency', 0):.1%}

## Components
"""
            
            components = product.get('components', [])
            for i, component in enumerate(components, 1):
                doc += f"""
### Component {i}
- **Asset**: {component.get('underlying_asset', 'N/A')}
- **Weight**: {component.get('weight', 0):.2%}
- **Score**: {component.get('score', 0):.2f}
- **Reason**: {component.get('retention_reason', 'N/A')}
"""
            
            # Add risk profile
            risk_profile = product.get('risk_profile', {})
            doc += f"""
## Risk Profile
- **Risk Level**: {risk_profile.get('risk_level', 'N/A')}
- **Weighted Risk Score**: {risk_profile.get('weighted_risk_score', 0):.2f}
- **Diversification Score**: {risk_profile.get('diversification_score', 0):.2f}
"""
            
            # Add performance metrics
            performance = product.get('performance_metrics', {})
            doc += f"""
## Performance Expectations
- **Expected Return**: {performance.get('expected_return', 0):.2%}
- **Portfolio Score**: {performance.get('portfolio_score', 0):.2f}
- **Growth Score**: {performance.get('growth_score', 0):.2f}
- **Value Score**: {performance.get('value_score', 0):.2f}
"""
            
            # Add CDM compliance info
            cdm_info = product_bundle.get('cdm_compliance', {})
            doc += f"""
## CDM Compliance
- **Standard**: {cdm_info.get('standard', 'N/A')}
- **Compliance Level**: {cdm_info.get('compliance_level', 'N/A')}
- **Product Model**: {cdm_info.get('product_model', 'N/A')}
"""
            
            return doc
            
        except Exception as e:
            self.logger.error(f"Error creating documentation: {e}")
            return f"Error creating documentation: {str(e)}" 
    
    def _initialize_llm_client(self, openai_api_key: str, anthropic_api_key: str, hf_api_key: str,
                              openai_model: str, anthropic_model: str, hf_model: str):
        """Initialize the LLM client based on provider."""
        try:
            if self.llm_provider == "openai" and openai_api_key:
                self.llm_client = ChatOpenAI(
                    openai_api_key=openai_api_key,
                    model_name=openai_model,
                    temperature=0.3
                )
                self.logger.info(f"Initialized OpenAI client with model: {openai_model}")
            
            elif self.llm_provider == "anthropic" and anthropic_api_key:
                try:
                    self.llm_client = ChatAnthropic(
                        anthropic_api_key=anthropic_api_key,
                        model=anthropic_model,
                        temperature=0.3
                    )
                    self.logger.info(f"Initialized Anthropic client with model: {anthropic_model}")
                except AttributeError as e:
                    if "count_tokens" in str(e):
                        self.logger.warning("Anthropic client version issue detected, falling back to template-based bundling")
                        self.use_llm = False
                        return
                    else:
                        raise e
            
            elif self.llm_provider == "huggingface" and hf_api_key:
                self.llm_client = ChatHuggingFace(
                    huggingfacehub_api_token=hf_api_key,
                    repo_id=hf_model,
                    temperature=0.3
                )
                self.logger.info(f"Initialized HuggingFace client with model: {hf_model}")
            
            else:
                self.logger.warning("No valid API key provided, falling back to template-based bundling")
                self.use_llm = False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {e}")
            self.use_llm = False
    
    def _initialize_product_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize CDM-compliant product templates."""
        return {
            "CONSERVATIVE_EQUITY_BASKET": {
                "description": "Low-risk equity basket with stable, dividend-paying stocks",
                "target_return": "8-12%",
                "risk_level": "LOW",
                "suitable_for": "Conservative investors, retirement planning"
            },
            "BALANCED_EQUITY_BASKET": {
                "description": "Balanced equity basket with growth and value stocks",
                "target_return": "12-18%",
                "risk_level": "MEDIUM",
                "suitable_for": "Moderate investors, long-term growth"
            },
            "AGGRESSIVE_EQUITY_BASKET": {
                "description": "High-growth equity basket with emerging market and tech stocks",
                "target_return": "18-25%",
                "risk_level": "HIGH",
                "suitable_for": "Aggressive investors, high growth potential"
            }
        }