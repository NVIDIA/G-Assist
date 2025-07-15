"""
Stock Selection Tool - LangChain tool for intelligently selecting and ranking stocks for structured products.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from langchain_core.tools import BaseTool
try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_community.chat_models import ChatHuggingFace
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
import json

@dataclass
class StockScore:
    """Stock scoring result."""
    symbol: str
    total_score: float
    risk_score: float
    growth_score: float
    value_score: float
    technical_score: float
    sector_score: float
    retention_reason: str
    weight_suggestion: float

class StockSelectionTool(BaseTool):
    """
    LangChain tool for intelligently selecting stocks for structured products
    based on comprehensive analysis data.
    """
    
    name: str = "stock_selection"
    description: str = """
    Intelligently selects and ranks stocks for structured products based on analysis data and user preferences.
    Takes stock analysis results and user preferences, returns selected stocks with scores and weights.
    """
    logger: Optional[Any] = None
    use_llm: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm: Optional[Any] = None
    
    def __init__(self, openai_api_key: str, use_llm: bool = True, llm_provider: str = "openai", 
                 anthropic_api_key: Optional[str] = None, hf_api_key: Optional[str] = None,
                 openai_model: str = "gpt-4", anthropic_model: str = "claude-3-opus-20240229", 
                 hf_model: str = "HuggingFaceH4/zephyr-7b-beta"):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.use_llm = use_llm and LLM_AVAILABLE and (openai_api_key or anthropic_api_key or hf_api_key)
        self.llm_provider = llm_provider
        
        if self.use_llm:
            if llm_provider == "openai":
                self.llm = ChatOpenAI(
                    model=openai_model,
                    temperature=0.1,
                    openai_api_key=openai_api_key
                )
            elif llm_provider == "anthropic":
                try:
                    self.llm = ChatAnthropic(
                        model=anthropic_model,
                        temperature=0.1,
                        anthropic_api_key=anthropic_api_key
                    )
                except AttributeError as e:
                    if "count_tokens" in str(e):
                        self.logger.warning("Anthropic client version issue detected, falling back to rule-based selection")
                        self.use_llm = False
                    else:
                        raise e
            elif llm_provider == "huggingface":
                self.llm = ChatHuggingFace(
                    model=hf_model,
                    temperature=0.1,
                    huggingfacehub_api_token=hf_api_key
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {llm_provider}")
    
    def _run(self, analysis_results: str, user_preferences: str = None, 
             target_count: int = 15, min_count: int = 5) -> str:
        """
        Select the best stocks from analysis results based on user preferences.
        
        Args:
            analysis_results: JSON string of stock analysis results
            user_preferences: JSON string of user investment preferences
            target_count: Target number of stocks to select
            min_count: Minimum number of stocks to select
            
        Returns:
            JSON string of selected stocks with scores and weights
        """
        try:
            # Parse inputs
            results = json.loads(analysis_results)
            preferences = json.loads(user_preferences) if user_preferences else {}
            
            self.logger.info(f"Selecting stocks from {len(results)} candidates")
            
            # Score all stocks
            scored_stocks = self._score_stocks(results, preferences)
            
            # Rank stocks by total score
            ranked_stocks = sorted(scored_stocks, key=lambda x: x.total_score, reverse=True)
            
            # Apply diversification rules
            diversified_stocks = self._apply_diversification_rules(ranked_stocks, preferences)
            
            # Select final stocks
            selected_stocks = self._select_final_stocks(
                diversified_stocks, 
                target_count, 
                min_count,
                preferences
            )
            
            # Calculate weights
            weighted_stocks = self._calculate_weights(selected_stocks, preferences)
            
            self.logger.info(f"Selected {len(weighted_stocks)} stocks from {len(results)} candidates")
            
            return json.dumps(weighted_stocks, indent=2)
            
        except Exception as e:
            self.logger.error(f"Error selecting stocks: {e}")
            # Fallback: return top stocks by simple ranking
            return json.dumps(self._fallback_selection(results, target_count, min_count), indent=2)
    
    def _score_stocks(self, analysis_results: List[Dict[str, Any]], 
                     user_preferences: Dict[str, Any]) -> List[StockScore]:
        """Score stocks based on analysis data and user preferences."""
        
        scored_stocks = []
        
        for result in analysis_results:
            symbol = result.get('symbol', '')
            analysis = result.get('analysis', {})
            
            if not analysis:
                continue
            
            # Calculate individual scores
            risk_score = self._calculate_risk_score(analysis, user_preferences)
            growth_score = self._calculate_growth_score(analysis, user_preferences)
            value_score = self._calculate_value_score(analysis, user_preferences)
            technical_score = self._calculate_technical_score(analysis, user_preferences)
            sector_score = self._calculate_sector_score(analysis, user_preferences)
            
            # Calculate total score with preference weighting
            total_score = self._calculate_total_score(
                risk_score, growth_score, value_score, technical_score, sector_score,
                user_preferences
            )
            
            # Generate retention reason
            retention_reason = self._generate_retention_reason(
                analysis, risk_score, growth_score, value_score, technical_score, sector_score
            )
            
            # Suggest weight based on score
            weight_suggestion = self._suggest_weight(total_score, user_preferences)
            
            scored_stock = StockScore(
                symbol=symbol,
                total_score=total_score,
                risk_score=risk_score,
                growth_score=growth_score,
                value_score=value_score,
                technical_score=technical_score,
                sector_score=sector_score,
                retention_reason=retention_reason,
                weight_suggestion=weight_suggestion
            )
            
            scored_stocks.append(scored_stock)
        
        return scored_stocks
    
    def _calculate_risk_score(self, analysis: Dict[str, Any], 
                            user_preferences: Dict[str, Any]) -> float:
        """Calculate risk score based on risk metrics."""
        
        risk_metrics = analysis.get('risk', {})
        if not risk_metrics:
            return 0.5
        
        # Extract risk metrics
        sharpe_ratio = risk_metrics.get('sharpe_ratio', 0)
        volatility = risk_metrics.get('volatility', 0.2)
        var_95 = risk_metrics.get('var_95', 0.05)
        max_drawdown = risk_metrics.get('max_drawdown', 0.1)
        
        # Calculate risk score (higher is better)
        risk_score = 0.0
        
        # Sharpe ratio component (0-1 scale)
        if sharpe_ratio > 2.0:
            risk_score += 0.3
        elif sharpe_ratio > 1.5:
            risk_score += 0.25
        elif sharpe_ratio > 1.0:
            risk_score += 0.2
        elif sharpe_ratio > 0.5:
            risk_score += 0.15
        else:
            risk_score += 0.1
        
        # Volatility component (lower is better)
        if volatility < 0.1:
            risk_score += 0.25
        elif volatility < 0.15:
            risk_score += 0.2
        elif volatility < 0.2:
            risk_score += 0.15
        elif volatility < 0.25:
            risk_score += 0.1
        else:
            risk_score += 0.05
        
        # VaR component (lower is better)
        if var_95 < 0.02:
            risk_score += 0.25
        elif var_95 < 0.03:
            risk_score += 0.2
        elif var_95 < 0.05:
            risk_score += 0.15
        elif var_95 < 0.08:
            risk_score += 0.1
        else:
            risk_score += 0.05
        
        # Max drawdown component (lower is better)
        if max_drawdown < 0.05:
            risk_score += 0.2
        elif max_drawdown < 0.1:
            risk_score += 0.15
        elif max_drawdown < 0.15:
            risk_score += 0.1
        elif max_drawdown < 0.2:
            risk_score += 0.05
        else:
            risk_score += 0.02
        
        return min(risk_score, 1.0)
    
    def _calculate_growth_score(self, analysis: Dict[str, Any], 
                              user_preferences: Dict[str, Any]) -> float:
        """Calculate growth score based on growth metrics."""
        
        metrics = analysis.get('metrics', {})
        if not metrics:
            return 0.5
        
        # Extract growth metrics
        revenue_growth = metrics.get('revenue_growth', 0)
        earnings_growth = metrics.get('earnings_growth', 0)
        pe_ratio = metrics.get('pe_ratio', 15)
        peg_ratio = metrics.get('peg_ratio', 1.0)
        
        # Calculate growth score (higher is better)
        growth_score = 0.0
        
        # Revenue growth component
        if revenue_growth > 0.2:  # 20%+
            growth_score += 0.3
        elif revenue_growth > 0.1:  # 10%+
            growth_score += 0.25
        elif revenue_growth > 0.05:  # 5%+
            growth_score += 0.2
        elif revenue_growth > 0:  # Positive
            growth_score += 0.15
        else:
            growth_score += 0.05
        
        # Earnings growth component
        if earnings_growth > 0.15:  # 15%+
            growth_score += 0.25
        elif earnings_growth > 0.1:  # 10%+
            growth_score += 0.2
        elif earnings_growth > 0.05:  # 5%+
            growth_score += 0.15
        elif earnings_growth > 0:  # Positive
            growth_score += 0.1
        else:
            growth_score += 0.05
        
        # P/E ratio component (lower is better for growth)
        if pe_ratio < 15:
            growth_score += 0.25
        elif pe_ratio < 20:
            growth_score += 0.2
        elif pe_ratio < 25:
            growth_score += 0.15
        elif pe_ratio < 30:
            growth_score += 0.1
        else:
            growth_score += 0.05
        
        # PEG ratio component (lower is better)
        if peg_ratio < 0.8:
            growth_score += 0.2
        elif peg_ratio < 1.0:
            growth_score += 0.15
        elif peg_ratio < 1.2:
            growth_score += 0.1
        elif peg_ratio < 1.5:
            growth_score += 0.05
        else:
            growth_score += 0.02
        
        return min(growth_score, 1.0)
    
    def _calculate_value_score(self, analysis: Dict[str, Any], 
                             user_preferences: Dict[str, Any]) -> float:
        """Calculate value score based on value metrics."""
        
        metrics = analysis.get('metrics', {})
        if not metrics:
            return 0.5
        
        # Extract value metrics
        pe_ratio = metrics.get('pe_ratio', 15)
        pb_ratio = metrics.get('pb_ratio', 1.5)
        ps_ratio = metrics.get('ps_ratio', 2.0)
        dividend_yield = metrics.get('dividend_yield', 0)
        book_value = metrics.get('book_value', 0)
        
        # Calculate value score (higher is better)
        value_score = 0.0
        
        # P/E ratio component (lower is better)
        if pe_ratio < 10:
            value_score += 0.25
        elif pe_ratio < 15:
            value_score += 0.2
        elif pe_ratio < 20:
            value_score += 0.15
        elif pe_ratio < 25:
            value_score += 0.1
        else:
            value_score += 0.05
        
        # P/B ratio component (lower is better)
        if pb_ratio < 1.0:
            value_score += 0.2
        elif pb_ratio < 1.5:
            value_score += 0.15
        elif pb_ratio < 2.0:
            value_score += 0.1
        elif pb_ratio < 3.0:
            value_score += 0.05
        else:
            value_score += 0.02
        
        # P/S ratio component (lower is better)
        if ps_ratio < 1.0:
            value_score += 0.2
        elif ps_ratio < 2.0:
            value_score += 0.15
        elif ps_ratio < 3.0:
            value_score += 0.1
        elif ps_ratio < 5.0:
            value_score += 0.05
        else:
            value_score += 0.02
        
        # Dividend yield component (higher is better for value)
        if dividend_yield > 0.05:  # 5%+
            value_score += 0.2
        elif dividend_yield > 0.03:  # 3%+
            value_score += 0.15
        elif dividend_yield > 0.02:  # 2%+
            value_score += 0.1
        elif dividend_yield > 0.01:  # 1%+
            value_score += 0.05
        else:
            value_score += 0.02
        
        # Book value component
        if book_value > 0:
            value_score += 0.15
        
        return min(value_score, 1.0)
    
    def _calculate_technical_score(self, analysis: Dict[str, Any], 
                                 user_preferences: Dict[str, Any]) -> float:
        """Calculate technical score based on technical indicators."""
        
        technical = analysis.get('technical', {})
        if not technical:
            return 0.5
        
        # Extract technical indicators
        rsi = technical.get('rsi', 50)
        macd_signal = technical.get('macd_signal', 'neutral')
        moving_averages = technical.get('moving_averages', {})
        
        # Calculate technical score (higher is better)
        technical_score = 0.0
        
        # RSI component (30-70 is good)
        if 30 <= rsi <= 70:
            technical_score += 0.4
        elif 20 <= rsi <= 80:
            technical_score += 0.3
        elif 10 <= rsi <= 90:
            technical_score += 0.2
        else:
            technical_score += 0.1
        
        # MACD component
        if macd_signal == 'bullish':
            technical_score += 0.3
        elif macd_signal == 'neutral':
            technical_score += 0.2
        else:
            technical_score += 0.1
        
        # Moving averages component
        if moving_averages:
            price_above_ma = moving_averages.get('price_above_ma', False)
            if price_above_ma:
                technical_score += 0.3
            else:
                technical_score += 0.1
        
        return min(technical_score, 1.0)
    
    def _calculate_sector_score(self, analysis: Dict[str, Any], 
                              user_preferences: Dict[str, Any]) -> float:
        """Calculate sector score based on sector analysis and preferences."""
        
        sector_analysis = analysis.get('sector', {})
        if not sector_analysis:
            return 0.5
        
        # Extract sector information
        sector = sector_analysis.get('sector', 'UNKNOWN')
        sector_performance = sector_analysis.get('performance', 0)
        sector_outlook = sector_analysis.get('outlook', 'neutral')
        
        # Calculate sector score (higher is better)
        sector_score = 0.0
        
        # Sector performance component
        if sector_performance > 0.1:  # 10%+ outperformance
            sector_score += 0.4
        elif sector_performance > 0.05:  # 5%+ outperformance
            sector_score += 0.3
        elif sector_performance > 0:  # Positive performance
            sector_score += 0.2
        else:
            sector_score += 0.1
        
        # Sector outlook component
        if sector_outlook == 'bullish':
            sector_score += 0.3
        elif sector_outlook == 'neutral':
            sector_score += 0.2
        else:
            sector_score += 0.1
        
        # Sector preference component (if user has preferences)
        preferred_sectors = user_preferences.get('sectors', [])
        if preferred_sectors and sector in preferred_sectors:
            sector_score += 0.3
        
        return min(sector_score, 1.0)
    
    def _calculate_total_score(self, risk_score: float, growth_score: float, 
                             value_score: float, technical_score: float, 
                             sector_score: float, user_preferences: Dict[str, Any]) -> float:
        """Calculate total score with preference weighting."""
        
        # Default weights
        weights = {
            'risk': 0.25,
            'growth': 0.25,
            'value': 0.2,
            'technical': 0.15,
            'sector': 0.15
        }
        
        # Adjust weights based on user preferences
        risk_tolerance = user_preferences.get('risk_tolerance', 'moderate')
        investment_style = user_preferences.get('investment_style', 'balanced')
        
        if risk_tolerance == 'low':
            weights['risk'] = 0.4
            weights['growth'] = 0.15
            weights['value'] = 0.25
            weights['technical'] = 0.1
            weights['sector'] = 0.1
        elif risk_tolerance == 'high':
            weights['risk'] = 0.15
            weights['growth'] = 0.35
            weights['value'] = 0.15
            weights['technical'] = 0.2
            weights['sector'] = 0.15
        
        if investment_style == 'growth':
            weights['growth'] = 0.4
            weights['value'] = 0.1
            weights['risk'] = 0.2
            weights['technical'] = 0.2
            weights['sector'] = 0.1
        elif investment_style == 'value':
            weights['value'] = 0.4
            weights['growth'] = 0.1
            weights['risk'] = 0.25
            weights['technical'] = 0.15
            weights['sector'] = 0.1
        
        # Calculate weighted total score
        total_score = (
            risk_score * weights['risk'] +
            growth_score * weights['growth'] +
            value_score * weights['value'] +
            technical_score * weights['technical'] +
            sector_score * weights['sector']
        )
        
        return min(total_score, 1.0)
    
    def _generate_retention_reason(self, analysis: Dict[str, Any], 
                                 risk_score: float, growth_score: float, 
                                 value_score: float, technical_score: float, 
                                 sector_score: float) -> str:
        """Generate retention reason based on scores."""
        
        reasons = []
        
        if risk_score > 0.7:
            reasons.append("Strong risk-adjusted returns")
        elif risk_score > 0.5:
            reasons.append("Acceptable risk profile")
        
        if growth_score > 0.7:
            reasons.append("Strong growth potential")
        elif growth_score > 0.5:
            reasons.append("Moderate growth outlook")
        
        if value_score > 0.7:
            reasons.append("Attractive valuation")
        elif value_score > 0.5:
            reasons.append("Fair valuation")
        
        if technical_score > 0.7:
            reasons.append("Positive technical indicators")
        elif technical_score > 0.5:
            reasons.append("Neutral technical outlook")
        
        if sector_score > 0.7:
            reasons.append("Favorable sector outlook")
        elif sector_score > 0.5:
            reasons.append("Stable sector performance")
        
        if not reasons:
            reasons.append("Balanced overall profile")
        
        return "; ".join(reasons)
    
    def _suggest_weight(self, total_score: float, user_preferences: Dict[str, Any]) -> float:
        """Suggest portfolio weight based on total score."""
        
        # Base weight on score
        if total_score > 0.8:
            base_weight = 0.08  # 8%
        elif total_score > 0.7:
            base_weight = 0.06  # 6%
        elif total_score > 0.6:
            base_weight = 0.05  # 5%
        elif total_score > 0.5:
            base_weight = 0.04  # 4%
        else:
            base_weight = 0.03  # 3%
        
        # Adjust for risk tolerance
        risk_tolerance = user_preferences.get('risk_tolerance', 'moderate')
        if risk_tolerance == 'low':
            base_weight *= 0.8
        elif risk_tolerance == 'high':
            base_weight *= 1.2
        
        return min(base_weight, 0.1)  # Cap at 10%
    
    def _apply_diversification_rules(self, ranked_stocks: List[StockScore], 
                                   user_preferences: Dict[str, Any]) -> List[StockScore]:
        """Apply diversification rules to ranked stocks."""
        
        diversified = []
        sectors_seen = set()
        market_caps_seen = {'large': 0, 'mid': 0, 'small': 0}
        
        for stock in ranked_stocks:
            # Get sector and market cap (simplified)
            sector = self._get_stock_sector(stock.symbol)
            market_cap = self._get_stock_market_cap_category(stock.symbol)
            
            # Sector diversification (max 30% per sector)
            if sector in sectors_seen:
                sector_count = sum(1 for s in diversified if self._get_stock_sector(s.symbol) == sector)
                if sector_count >= 3:  # Max 3 stocks per sector
                    continue
            
            # Market cap diversification
            if market_cap in market_caps_seen:
                if market_caps_seen[market_cap] >= 5:  # Max 5 stocks per market cap category
                    continue
            
            diversified.append(stock)
            sectors_seen.add(sector)
            market_caps_seen[market_cap] += 1
        
        return diversified
    
    def _select_final_stocks(self, diversified_stocks: List[StockScore], 
                           target_count: int, min_count: int,
                           user_preferences: Dict[str, Any]) -> List[StockScore]:
        """Select final stocks based on target count and preferences."""
        
        if len(diversified_stocks) <= target_count:
            return diversified_stocks[:target_count]
        
        # Ensure minimum count
        if len(diversified_stocks) < min_count:
            return diversified_stocks
        
        # Select top stocks up to target count
        return diversified_stocks[:target_count]
    
    def _calculate_weights(self, selected_stocks: List[StockScore], 
                         user_preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate final weights for selected stocks."""
        
        if not selected_stocks:
            return []
        
        # Calculate total suggested weight
        total_suggested = sum(stock.weight_suggestion for stock in selected_stocks)
        
        # Normalize weights to sum to 1.0
        normalized_stocks = []
        for stock in selected_stocks:
            normalized_weight = stock.weight_suggestion / total_suggested if total_suggested > 0 else 1.0 / len(selected_stocks)
            
            stock_dict = {
                'symbol': stock.symbol,
                'total_score': stock.total_score,
                'risk_score': stock.risk_score,
                'growth_score': stock.growth_score,
                'value_score': stock.value_score,
                'technical_score': stock.technical_score,
                'sector_score': stock.sector_score,
                'retention_reason': stock.retention_reason,
                'weight': normalized_weight
            }
            
            normalized_stocks.append(stock_dict)
        
        return normalized_stocks
    
    def _fallback_selection(self, analysis_results: List[Dict[str, Any]], 
                          target_count: int, min_count: int) -> List[Dict[str, Any]]:
        """Fallback selection method."""
        
        # Simple selection based on available data
        selected = []
        for result in analysis_results[:target_count]:
            symbol = result.get('symbol', '')
            analysis = result.get('analysis', {})
            
            if symbol and analysis:
                selected.append({
                    'symbol': symbol,
                    'total_score': 0.6,  # Default score
                    'risk_score': 0.5,
                    'growth_score': 0.5,
                    'value_score': 0.5,
                    'technical_score': 0.5,
                    'sector_score': 0.5,
                    'retention_reason': 'Selected via fallback method',
                    'weight': 1.0 / len(selected) if selected else 1.0
                })
        
        return selected
    
    def _get_stock_sector(self, symbol: str) -> str:
        """Get stock sector (simplified implementation)."""
        # This would typically query a database or API
        # For now, return a default sector
        return "TECHNOLOGY"
    
    def _get_stock_market_cap_category(self, symbol: str) -> str:
        """Get stock market cap category (simplified implementation)."""
        # This would typically query a database or API
        # For now, return a default category
        return "large" 