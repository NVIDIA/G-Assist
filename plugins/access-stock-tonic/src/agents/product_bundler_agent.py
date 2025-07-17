"""
Product Bundler Agent - Creates structured equity products based on analyzer outputs using FINOS CDM standards.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from langchain_core.tools import BaseTool
import json
from langchain.prompts import ChatPromptTemplate
from ..tools.stock_selection_tool import StockSelectionTool
from ..prompts.product_bundler_prompts import (
    PRODUCT_BUNDLER_SYSTEM_PROMPT,
    PRODUCT_BUNDLER_CDM_PROMPT,
    PRODUCT_BUNDLER_EXAMPLES,
    PRODUCT_BUNDLER_INPUT_TEMPLATE
)


# Import the summarizer agent
try:
    from .summarizer_agent import SummarizerAgent
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False
    print("Warning: SummarizerAgent not available. Will use template-based summaries.")

from .gassist_llm import GAssistLLM

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
        self.llm = GAssistLLM() # Always use GAssistLLM
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
    
    def __init__(self, llm=None, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.llm = llm or GAssistLLM()
        # Remove all cloud LLM logic and API key handling
        # ... existing code ...

    def bundle_product(self, analyzer_results, user_preferences=None, processed_query=None):
        # Use self.llm for all LLM calls
        # ... existing code ...
        return {}  # Replace with actual logic