"""
Analyzer Agent - Analyzes each stock using the MCP server and returns structured results with data-based assessments.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import requests
from datetime import datetime
import numpy as np



from ..prompts.analyzer_prompts import (
    ANALYZER_SYSTEM_PROMPT,
    ANALYZER_MCP_PROMPT,
    ANALYZER_EXAMPLES
)

# Import SummarizerAgent for individual stock summaries
try:
    from ..agents.summarizer_agent import SummarizerAgent
    SUMMARIZER_AVAILABLE = True
except ImportError:
    SUMMARIZER_AVAILABLE = False

try:
    from .gassist_llm import GAssistLLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

from ..tools import predictions
from ..tools.calendar_tool import CalendarTool

MCP_SERVER_URL = "https://tonic-stock-predictions.hf.space/gradio_api/mcp/sse"

class StockAssessment:
    """Data-based assessment of a stock with comprehensive metrics and recommendations."""
    
    def __init__(self, symbol: str, analysis_data: Dict[str, Any], processed_query: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.analysis_data = analysis_data
        self.processed_query = processed_query or {}
        print(f"[ASSESSMENT DEBUG] Creating StockAssessment for {symbol}")
        print(f"[ASSESSMENT DEBUG] Analysis data keys: {list(analysis_data.keys())}")
        print(f"[ASSESSMENT DEBUG] Analysis data has 'analysis' key: {'analysis' in analysis_data}")
        if 'analysis' in analysis_data:
            print(f"[ASSESSMENT DEBUG] Analysis keys: {list(analysis_data['analysis'].keys())}")
        self.assessment = self._generate_assessment()
        print(f"[ASSESSMENT DEBUG] Generated assessment for {symbol} with keys: {list(self.assessment.keys())}")
    
    def _generate_assessment(self) -> Dict[str, Any]:
        """Generate comprehensive data-based assessment."""
        print(f"[ASSESSMENT DEBUG] Generating assessment for {self.symbol}")
        analysis = self.analysis_data.get('analysis', {})
        print(f"[ASSESSMENT DEBUG] Analysis keys: {list(analysis.keys())}")
        
        # Extract key metrics
        signals = analysis.get('signals', {})
        metrics = analysis.get('metrics', {})
        risk = analysis.get('risk', {})
        sector = analysis.get('sector', {})
        regime = analysis.get('regime', {})
        stress = analysis.get('stress', {})
        ensemble = analysis.get('ensemble', {})
        advanced = analysis.get('advanced', {})
        
        print(f"[ASSESSMENT DEBUG] Extracted data sections:")
        print(f"[ASSESSMENT DEBUG]   signals: {type(signals)} - keys: {list(signals.keys()) if isinstance(signals, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   metrics: {type(metrics)} - keys: {list(metrics.keys()) if isinstance(metrics, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   risk: {type(risk)} - keys: {list(risk.keys()) if isinstance(risk, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   sector: {type(sector)} - keys: {list(sector.keys()) if isinstance(sector, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   regime: {type(regime)} - keys: {list(regime.keys()) if isinstance(regime, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   stress: {type(stress)} - keys: {list(stress.keys()) if isinstance(stress, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   ensemble: {type(ensemble)} - keys: {list(ensemble.keys()) if isinstance(ensemble, dict) else 'not dict'}")
        print(f"[ASSESSMENT DEBUG]   advanced: {type(advanced)} - keys: {list(advanced.keys()) if isinstance(advanced, dict) else 'not dict'}")
        
        # Calculate investment recommendation
        print(f"[ASSESSMENT DEBUG] Calculating investment recommendation for {self.symbol}")
        investment_recommendation = self._calculate_investment_recommendation(
            signals, metrics, risk, ensemble, advanced
        )
        print(f"[ASSESSMENT DEBUG] Investment recommendation: {investment_recommendation}")
        
        # Calculate risk assessment
        print(f"[ASSESSMENT DEBUG] Calculating risk assessment for {self.symbol}")
        risk_assessment = self._calculate_risk_assessment(risk, stress, regime)
        print(f"[ASSESSMENT DEBUG] Risk assessment: {risk_assessment}")
        
        # Calculate confidence score
        print(f"[ASSESSMENT DEBUG] Calculating confidence score for {self.symbol}")
        confidence_score = self._calculate_confidence_score(ensemble, signals, advanced)
        print(f"[ASSESSMENT DEBUG] Confidence score: {confidence_score}")
        
        # Calculate suitability score
        print(f"[ASSESSMENT DEBUG] Calculating suitability score for {self.symbol}")
        suitability_score = self._calculate_suitability_score(
            investment_recommendation, risk_assessment, confidence_score
        )
        print(f"[ASSESSMENT DEBUG] Suitability score: {suitability_score}")
        
        # Generate detailed insights
        print(f"[ASSESSMENT DEBUG] Generating insights for {self.symbol}")
        insights = self._generate_insights(
            signals, metrics, risk, sector, regime, stress, ensemble, advanced
        )
        print(f"[ASSESSMENT DEBUG] Generated insights: {list(insights.keys()) if isinstance(insights, dict) else 'not dict'}")
        
        # Generate prompt-based text assessment
        print(f"[ASSESSMENT DEBUG] Generating text assessment for {self.symbol}")
        text_assessment = self._generate_text_assessment(
            investment_recommendation, risk_assessment, confidence_score, 
            suitability_score, insights, signals, metrics, risk, sector
        )
        print(f"[ASSESSMENT DEBUG] Text assessment length: {len(text_assessment) if text_assessment else 0}")
        
        assessment = {
            'investment_recommendation': investment_recommendation,
            'risk_assessment': risk_assessment,
            'confidence_score': confidence_score,
            'suitability_score': suitability_score,
            'insights': insights,
            'text_assessment': text_assessment,
            'assessment_timestamp': datetime.now().isoformat(),
            'assessment_version': '2.0'
        }
        
        print(f"[ASSESSMENT DEBUG] Final assessment keys for {self.symbol}: {list(assessment.keys())}")
        return assessment
    
    def _calculate_investment_recommendation(self, signals: Dict, metrics: Dict, 
                                           risk: Dict, ensemble: Dict, advanced: Dict) -> Dict[str, Any]:
        """Calculate investment recommendation based on multiple factors."""
        
        # Signal analysis - handle both normalized and original signal formats
        overall_signal = signals.get('overall', signals.get('Overall', 'NEUTRAL'))
        rsi_signal = signals.get('rsi', signals.get('RSI', 'NEUTRAL'))
        macd_signal = signals.get('macd', signals.get('MACD', 'NEUTRAL'))
        
        # Convert signals to numeric scores
        signal_scores = {
            'BUY': 1.0, 'STRONG_BUY': 1.0,
            'HOLD': 0.5, 'NEUTRAL': 0.5,
            'SELL': 0.0, 'STRONG_SELL': 0.0
        }
        
        signal_score = (
            signal_scores.get(overall_signal, 0.5) * 0.4 +
            signal_scores.get(rsi_signal, 0.5) * 0.3 +
            signal_scores.get(macd_signal, 0.5) * 0.3
        )
        
        # Risk-adjusted metrics - handle MCP key names
        sharpe_ratio = risk.get('Sharpe_Ratio', risk.get('sharpe_ratio', 0))
        volatility = risk.get('Annual_Volatility', risk.get('volatility', 0.2))
        
        # Ensemble predictions - handle MCP key names
        ensemble_score = ensemble.get('ensemble_score', 0.5)
        model_agreement = ensemble.get('model_agreement', 0.5)
        
        # Advanced metrics - handle MCP key names
        momentum_score = advanced.get('momentum_score', 0.5)
        quality_score = advanced.get('quality_score', 0.5)
        
        # Calculate composite recommendation score
        recommendation_score = (
            signal_score * 0.25 +
            min(sharpe_ratio / 2.0, 1.0) * 0.2 +
            ensemble_score * 0.2 +
            momentum_score * 0.15 +
            quality_score * 0.1 +
            model_agreement * 0.1
        )
        
        # Determine recommendation level
        if recommendation_score >= 0.8:
            recommendation = "STRONG_BUY"
            strength = "HIGH"
        elif recommendation_score >= 0.6:
            recommendation = "BUY"
            strength = "MEDIUM"
        elif recommendation_score >= 0.4:
            recommendation = "HOLD"
            strength = "MEDIUM"
        elif recommendation_score >= 0.2:
            recommendation = "SELL"
            strength = "MEDIUM"
        else:
            recommendation = "STRONG_SELL"
            strength = "HIGH"
        
        return {
            'recommendation': recommendation,
            'strength': strength,
            'score': recommendation_score,
            'signal_breakdown': {
                'overall_signal': overall_signal,
                'rsi_signal': rsi_signal,
                'macd_signal': macd_signal,
                'signal_score': signal_score
            },
            'technical_factors': {
                'sharpe_ratio': sharpe_ratio,
                'ensemble_score': ensemble_score,
                'momentum_score': momentum_score,
                'quality_score': quality_score,
                'model_agreement': model_agreement
            }
        }
    
    def _calculate_risk_assessment(self, risk: Dict, stress: Dict, regime: Dict) -> Dict[str, Any]:
        """Calculate comprehensive risk assessment."""
        
        # Extract risk metrics - handle MCP key names
        sharpe_ratio = risk.get('Sharpe_Ratio', risk.get('sharpe_ratio', 0))
        var_95 = risk.get('VaR_95', risk.get('var_95', 0.05))
        volatility = risk.get('Annual_Volatility', risk.get('volatility', 0.2))
        max_drawdown = risk.get('Max_Drawdown', risk.get('max_drawdown', 0.2))
        
        # Stress testing - handle MCP key names
        stress_score = stress.get('stress_score', 0.5)
        scenario_analysis = stress.get('scenario_analysis', 'NEUTRAL')
        
        # Market regime - handle MCP key names
        current_regime = regime.get('regime', regime.get('current_regime', 'NEUTRAL'))
        regime_probability = regime.get('probabilities', [0.5])[0] if isinstance(regime.get('probabilities'), list) else regime.get('regime_probability', 0.5)
        
        # Calculate risk level
        risk_factors = []
        
        if volatility > 0.3:
            risk_factors.append("HIGH_VOLATILITY")
        elif volatility < 0.15:
            risk_factors.append("LOW_VOLATILITY")
        
        if var_95 > 0.08:
            risk_factors.append("HIGH_VAR")
        elif var_95 < 0.02:
            risk_factors.append("LOW_VAR")
        
        if sharpe_ratio < 0.5:
            risk_factors.append("LOW_SHARPE")
        elif sharpe_ratio > 1.5:
            risk_factors.append("HIGH_SHARPE")
        
        if stress_score > 0.7:
            risk_factors.append("HIGH_STRESS")
        elif stress_score < 0.3:
            risk_factors.append("LOW_STRESS")
        
        # Determine overall risk level
        risk_score = 0.5  # Default neutral
        
        if volatility > 0.3:
            risk_score += 0.2
        elif volatility < 0.15:
            risk_score -= 0.1
        
        if var_95 > 0.08:
            risk_score += 0.15
        elif var_95 < 0.02:
            risk_score -= 0.1
        
        if sharpe_ratio < 0.5:
            risk_score += 0.1
        elif sharpe_ratio > 1.5:
            risk_score -= 0.1
        
        if stress_score > 0.7:
            risk_score += 0.15
        elif stress_score < 0.3:
            risk_score -= 0.1
        
        # Clamp risk score between 0 and 1
        risk_score = max(0.0, min(1.0, risk_score))
        
        # Determine risk level category
        if risk_score >= 0.7:
            risk_level = "HIGH"
        elif risk_score >= 0.4:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'key_metrics': {
                'sharpe_ratio': sharpe_ratio,
                'var_95': var_95,
                'volatility': volatility,
                'max_drawdown': max_drawdown,
                'stress_score': stress_score
            },
            'market_context': {
                'current_regime': current_regime,
                'regime_probability': regime_probability,
                'scenario_analysis': scenario_analysis
            }
        }
    
    def _calculate_confidence_score(self, ensemble: Dict, signals: Dict, advanced: Dict) -> Dict[str, Any]:
        """Calculate confidence score based on model agreement and data quality."""
        
        # Ensemble metrics - handle MCP key names
        ensemble_score = ensemble.get('ensemble_score', 0.5)
        model_agreement = ensemble.get('model_agreement', 0.5)
        
        # Signal consistency - handle MCP key names
        signal_consistency = 0.5  # Default
        if isinstance(signals, dict):
            signal_values = []
            for key in ['rsi', 'macd', 'bollinger', 'sma', 'overall']:
                value = signals.get(key, signals.get(key.upper(), 'NEUTRAL'))
                if value in ['BUY', 'STRONG_BUY']:
                    signal_values.append(1.0)
                elif value in ['SELL', 'STRONG_SELL']:
                    signal_values.append(0.0)
                else:
                    signal_values.append(0.5)
            
            if signal_values:
                # Calculate consistency based on variance
                import statistics
                signal_consistency = 1.0 - min(statistics.variance(signal_values), 0.5) * 2
        
        # Momentum and quality metrics - handle MCP key names
        momentum_quality = advanced.get('momentum_score', 0.5)
        overall_quality = advanced.get('quality_score', 0.5)
        
        # Calculate composite confidence score
        confidence_score = (
            ensemble_score * 0.3 +
            model_agreement * 0.25 +
            signal_consistency * 0.2 +
            momentum_quality * 0.15 +
            overall_quality * 0.1
        )
        
        # Determine confidence level
        if confidence_score >= 0.8:
            confidence_level = "HIGH"
        elif confidence_score >= 0.6:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"
        
        return {
            'confidence_score': confidence_score,
            'confidence_level': confidence_level,
            'factors': {
                'ensemble_score': ensemble_score,
                'model_agreement': model_agreement,
                'signal_consistency': signal_consistency,
                'momentum_quality': momentum_quality,
                'overall_quality': overall_quality
            }
        }
    
    def _calculate_suitability_score(self, investment_recommendation: Dict, 
                                   risk_assessment: Dict, confidence_score: Dict) -> Dict[str, Any]:
        """Calculate suitability score based on user preferences and investment profile."""
        
        # Extract user preferences from processed query
        user_preferences = self.processed_query or {}
        risk_tolerance = user_preferences.get('risk_tolerance', 'moderate')
        investment_horizon = user_preferences.get('investment_horizon', 'medium')
        capital_amount = user_preferences.get('capital_amount', 10000)
        
        # Risk suitability based on risk tolerance
        risk_level = risk_assessment.get('risk_level', 'MODERATE')
        risk_score = risk_assessment.get('risk_score', 0.5)
        
        risk_suitability = 0.5  # Default neutral
        if risk_tolerance == 'conservative':
            if risk_level == 'LOW':
                risk_suitability = 0.9
            elif risk_level == 'MODERATE':
                risk_suitability = 0.6
            else:
                risk_suitability = 0.2
        elif risk_tolerance == 'moderate':
            if risk_level == 'LOW':
                risk_suitability = 0.7
            elif risk_level == 'MODERATE':
                risk_suitability = 0.9
            else:
                risk_suitability = 0.5
        elif risk_tolerance == 'aggressive':
            if risk_level == 'LOW':
                risk_suitability = 0.3
            elif risk_level == 'MODERATE':
                risk_suitability = 0.7
            else:
                risk_suitability = 0.9
        
        # Recommendation suitability based on investment horizon
        recommendation = investment_recommendation.get('recommendation', 'HOLD')
        recommendation_score = investment_recommendation.get('score', 0.5)
        
        recommendation_suitability = recommendation_score  # Default to recommendation score
        
        # Confidence suitability
        confidence_score_val = confidence_score.get('confidence_score', 0.5)
        confidence_suitability = confidence_score_val
        
        # Calculate overall suitability score
        suitability_score = (
            risk_suitability * 0.4 +
            recommendation_suitability * 0.4 +
            confidence_suitability * 0.2
        )
        
        # Determine suitability level
        if suitability_score >= 0.8:
            suitability_level = "EXCELLENT"
        elif suitability_score >= 0.6:
            suitability_level = "GOOD"
        elif suitability_score >= 0.4:
            suitability_level = "FAIR"
        else:
            suitability_level = "POOR"
        
        return {
            'suitability_score': suitability_score,
            'suitability_level': suitability_level,
            'risk_suitability': risk_suitability,
            'recommendation_suitability': recommendation_suitability,
            'confidence_suitability': confidence_suitability,
            'user_preferences': {
                'risk_tolerance': risk_tolerance,
                'investment_horizon': investment_horizon,
                'capital_amount': capital_amount
            }
        }
    
    def _generate_insights(self, signals: Dict, metrics: Dict, risk: Dict, 
                          sector: Dict, regime: Dict, stress: Dict, 
                          ensemble: Dict, advanced: Dict) -> Dict[str, Any]:
        """Generate comprehensive insights from all data sources."""
        
        insights = {}
        
        # Technical insights
        technical_insights = []
        overall_signal = signals.get('overall', signals.get('Overall', 'NEUTRAL'))
        rsi_signal = signals.get('rsi', signals.get('RSI', 'NEUTRAL'))
        macd_signal = signals.get('macd', signals.get('MACD', 'NEUTRAL'))
        
        if overall_signal in ['BUY', 'STRONG_BUY']:
            technical_insights.append("Strong bullish technical signals")
        elif overall_signal in ['SELL', 'STRONG_SELL']:
            technical_insights.append("Bearish technical momentum")
        else:
            technical_insights.append("Mixed technical indicators")
        
        if rsi_signal != 'NEUTRAL':
            technical_insights.append(f"RSI indicates {rsi_signal.lower()} conditions")
        
        if macd_signal != 'NEUTRAL':
            technical_insights.append(f"MACD shows {macd_signal.lower()} momentum")
        
        insights['technical_insights'] = technical_insights
        
        # Fundamental insights
        fundamental_insights = []
        market_cap = metrics.get('Market_Cap', metrics.get('market_cap'))
        pe_ratio = metrics.get('P/E_Ratio', metrics.get('pe_ratio'))
        dividend_yield = metrics.get('Dividend_Yield', metrics.get('dividend_yield'))
        
        if market_cap:
            if market_cap > 10000000000:  # 10B
                fundamental_insights.append("Large-cap company with established market position")
            elif market_cap > 2000000000:  # 2B
                fundamental_insights.append("Mid-cap company with growth potential")
            else:
                fundamental_insights.append("Small-cap company with higher growth/risk profile")
        
        if pe_ratio:
            if pe_ratio < 15:
                fundamental_insights.append("Undervalued based on P/E ratio")
            elif pe_ratio > 25:
                fundamental_insights.append("Premium valuation based on P/E ratio")
            else:
                fundamental_insights.append("Fairly valued based on P/E ratio")
        
        if dividend_yield and dividend_yield > 0:
            fundamental_insights.append(f"Attractive dividend yield of {dividend_yield:.2f}%")
        
        insights['fundamental_insights'] = fundamental_insights
        
        # Risk insights
        risk_insights = []
        sharpe_ratio = risk.get('Sharpe_Ratio', risk.get('sharpe_ratio', 0))
        volatility = risk.get('Annual_Volatility', risk.get('volatility', 0.2))
        var_95 = risk.get('VaR_95', risk.get('var_95', 0.05))
        
        if sharpe_ratio > 1.0:
            risk_insights.append("Excellent risk-adjusted returns")
        elif sharpe_ratio > 0.5:
            risk_insights.append("Good risk-adjusted performance")
        elif sharpe_ratio < 0:
            risk_insights.append("Poor risk-adjusted returns")
        
        if volatility > 0.3:
            risk_insights.append("High volatility indicates significant price swings")
        elif volatility < 0.15:
            risk_insights.append("Low volatility suggests price stability")
        
        if var_95 > 0.08:
            risk_insights.append("High downside risk potential")
        elif var_95 < 0.02:
            risk_insights.append("Limited downside risk exposure")
        
        insights['risk_insights'] = risk_insights
        
        # Market insights
        market_insights = []
        sector_name = sector.get('Sector', sector.get('sector', 'Unknown'))
        current_regime = regime.get('regime', regime.get('current_regime', 'NEUTRAL'))
        
        market_insights.append(f"Operating in {sector_name} sector")
        market_insights.append(f"Current market regime: {current_regime}")
        
        insights['market_insights'] = market_insights
        
        # Investment insights
        investment_insights = []
        ensemble_used = ensemble.get('ensemble_used', False)
        
        if ensemble_used:
            investment_insights.append("Multiple model ensemble analysis used")
        
        investment_insights.append("Comprehensive risk assessment completed")
        investment_insights.append("Technical and fundamental analysis integrated")
        
        insights['investment_insights'] = investment_insights
        
        return insights
    
    def _generate_text_assessment(self, investment_recommendation: Dict, 
                                  risk_assessment: Dict, confidence_score: Dict, 
                                  suitability_score: Dict, insights: Dict, 
                                  signals: Dict, metrics: Dict, risk: Dict, sector: Dict) -> str:
        """Generate comprehensive text assessment using LLM."""
        
        # Extract key data for assessment
        recommendation = investment_recommendation.get('recommendation', 'HOLD')
        recommendation_strength = investment_recommendation.get('strength', 'MEDIUM')
        recommendation_score = investment_recommendation.get('score', 0.5)
        
        risk_level = risk_assessment.get('risk_level', 'MODERATE')
        risk_score = risk_assessment.get('risk_score', 0.5)
        
        confidence_level = confidence_score.get('confidence_level', 'MEDIUM')
        confidence_score_val = confidence_score.get('confidence_score', 0.5)
        
        suitability_level = suitability_score.get('suitability_level', 'FAIR')
        suitability_score_val = suitability_score.get('suitability_score', 0.5)
        
        # Extract key metrics for context
        sharpe_ratio = risk.get('Sharpe_Ratio', risk.get('sharpe_ratio', 0))
        volatility = risk.get('Annual_Volatility', risk.get('volatility', 0.2))
        market_cap = metrics.get('Market_Cap', metrics.get('market_cap'))
        pe_ratio = metrics.get('P/E_Ratio', metrics.get('pe_ratio'))
        dividend_yield = metrics.get('Dividend_Yield', metrics.get('dividend_yield'))
        sector_name = sector.get('Sector', sector.get('sector', 'Unknown'))
        
        # Get user preferences
        user_preferences = suitability_score.get('user_preferences', {})
        risk_tolerance = user_preferences.get('risk_tolerance', 'moderate')
        investment_horizon = user_preferences.get('investment_horizon', 'medium')
        
        # Format insights for text
        technical_insights = insights.get('technical_insights', [])
        fundamental_insights = insights.get('fundamental_insights', [])
        risk_insights = insights.get('risk_insights', [])
        market_insights = insights.get('market_insights', [])
        investment_insights = insights.get('investment_insights', [])
        
        # Generate comprehensive text assessment
        assessment_text = f"""
{self.symbol} Stock Analysis Summary

Executive Summary
{self.symbol} presents a {recommendation} recommendation with {recommendation_strength.lower()} conviction at the current market conditions. The analysis reveals a {risk_level.lower()}-risk investment with {suitability_level.lower()} suitability for {risk_tolerance} investors with {investment_horizon}-term horizons. The {confidence_level.lower()} confidence level indicates {confidence_score_val:.1%} reliability in the analytical framework.

Price Analysis and Investment Thesis
The technical analysis indicates {recommendation.lower()} momentum with a {recommendation_score:.1%} confidence score. The investment thesis centers on {self._get_recommendation_rationale(recommendation, recommendation_score)}. The stock's Sharpe ratio of {sharpe_ratio:.3f} indicates {'excellent' if sharpe_ratio > 1.0 else 'good' if sharpe_ratio > 0.5 else 'poor'} risk-adjusted returns, while the {volatility:.1%} annualized volatility suggests {'high' if volatility > 0.3 else 'moderate' if volatility > 0.15 else 'low'} price variability.

Risk Assessment and Suitability
{self.symbol} maintains a {risk_level} risk profile ({risk_score:.1%} risk score) with {volatility:.1%} annualized volatility and {'significant' if risk_score > 0.7 else 'moderate' if risk_score > 0.4 else 'minimal'} downside exposure. The analysis reveals {'significant' if confidence_score_val < 0.6 else 'moderate' if confidence_score_val < 0.8 else 'high'} confidence levels ({confidence_score_val:.1%}), {'poor' if suitability_score_val < 0.4 else 'fair' if suitability_score_val < 0.6 else 'good'} suitability rating ({suitability_score_val:.1%}), and {'weak' if recommendation_score < 0.4 else 'moderate' if recommendation_score < 0.6 else 'strong'} fundamental positioning.

Investment Recommendation
Given the {'conflicting' if recommendation_score < 0.4 else 'mixed' if recommendation_score < 0.6 else 'supportive'} signals between {'bearish' if recommendation in ['SELL', 'STRONG_SELL'] else 'bullish' if recommendation in ['BUY', 'STRONG_BUY'] else 'neutral'} price predictions and {'weak' if recommendation_score < 0.4 else 'moderate' if recommendation_score < 0.6 else 'strong'} fundamental performance, {self.symbol} warrants a {recommendation} recommendation with {recommendation_strength.lower()} strength. The {confidence_score_val:.1%} confidence score reflects {'substantial' if confidence_score_val < 0.6 else 'moderate' if confidence_score_val < 0.8 else 'high'} analytical certainty, while the {suitability_score_val:.1%} suitability assessment suggests the stock may {'not align' if suitability_score_val < 0.4 else 'partially align' if suitability_score_val < 0.6 else 'well align'} with {risk_tolerance} investment objectives.

Key Strengths and Concerns
{self._identify_strengths(investment_recommendation, risk_assessment, insights)}

{self._identify_concerns(investment_recommendation, risk_assessment, insights)}

Market Context and Opportunities
{self._identify_opportunities(investment_recommendation, sector, insights)}

Risk Factors
{self._identify_risks(risk_assessment, insights)}

Next Steps: {'Consider reducing position size or avoiding new positions' if recommendation in ['SELL', 'STRONG_SELL'] else 'Monitor for entry opportunities' if recommendation in ['BUY', 'STRONG_BUY'] else 'Maintain current position with monitoring'} until {'fundamental metrics improve and model confidence increases' if confidence_score_val < 0.6 else 'market conditions become more favorable' if recommendation_score < 0.5 else 'risk-reward profile becomes more attractive'}. The stock may be suitable for {'highly conservative' if risk_level == 'LOW' else 'moderate' if risk_level == 'MODERATE' else 'aggressive'} investors seeking {'minimal' if risk_level == 'LOW' else 'moderate' if risk_level == 'MODERATE' else 'high'} volatility exposure.
"""
        
        return assessment_text.strip()
    
    def _get_recommendation_rationale(self, recommendation: str, score: float) -> str:
        """Get rationale for investment recommendation."""
        if recommendation == "STRONG_BUY":
            return "exceptional growth potential with strong technical and fundamental support"
        elif recommendation == "BUY":
            return "attractive investment opportunity with positive momentum and reasonable valuation"
        elif recommendation == "HOLD":
            return "neutral position with balanced risk-reward profile"
        elif recommendation == "SELL":
            return "potential downside risk with deteriorating fundamentals or technical indicators"
        elif recommendation == "STRONG_SELL":
            return "significant downside risk with poor fundamentals and negative momentum"
        else:
            return "mixed signals requiring further analysis"
    
    def _format_insights_for_text(self, insights: Dict) -> str:
        """Format insights for text assessment."""
        formatted_insights = []
        
        for category, insight_list in insights.items():
            if insight_list:
                category_name = category.replace('_', ' ').title()
                formatted_insights.append(f"**{category_name}**: {'; '.join(insight_list)}")
        
        return '\n'.join(formatted_insights) if formatted_insights else "No specific insights available."
    
    def _identify_strengths(self, investment_recommendation: Dict, risk_assessment: Dict, insights: Dict) -> str:
        """Identify key strengths of the investment."""
        strengths = []
        
        if investment_recommendation.get('score', 0) > 0.6:
            strengths.append("Strong investment recommendation")
        
        if risk_assessment.get('risk_level') == 'LOW':
            strengths.append("Low risk profile")
        
        if risk_assessment.get('key_metrics', {}).get('sharpe_ratio', 0) > 1.0:
            strengths.append("Good risk-adjusted returns")
        
        technical_insights = insights.get('technical_insights', [])
        if any('momentum' in insight.lower() for insight in technical_insights):
            strengths.append("Positive technical momentum")
        
        return '; '.join(strengths) if strengths else "No significant strengths identified"
    
    def _identify_concerns(self, investment_recommendation: Dict, risk_assessment: Dict, insights: Dict) -> str:
        """Identify key concerns about the investment."""
        concerns = []
        
        if investment_recommendation.get('score', 0) < 0.4:
            concerns.append("Weak investment recommendation")
        
        if risk_assessment.get('risk_level') == 'HIGH':
            concerns.append("High risk profile")
        
        if risk_assessment.get('key_metrics', {}).get('sharpe_ratio', 0) < 0.5:
            concerns.append("Poor risk-adjusted returns")
        
        risk_insights = insights.get('risk_insights', [])
        if any('poor' in insight.lower() or 'high' in insight.lower() for insight in risk_insights):
            concerns.append("Risk-related concerns")
        
        return '; '.join(concerns) if concerns else "No significant concerns identified"
    
    def _identify_opportunities(self, investment_recommendation: Dict, sector: Dict, insights: Dict) -> str:
        """Identify investment opportunities."""
        opportunities = []
        
        if investment_recommendation.get('recommendation') in ['BUY', 'STRONG_BUY']:
            opportunities.append("Strong buy signal")
        
        sector_name = sector.get('sector', '')
        if sector_name in ['Technology', 'Healthcare']:
            opportunities.append(f"Growth sector exposure ({sector_name})")
        
        fundamental_insights = insights.get('fundamental_insights', [])
        if any('value' in insight.lower() for insight in fundamental_insights):
            opportunities.append("Value opportunity")
        
        return '; '.join(opportunities) if opportunities else "Limited opportunities identified"
    
    def _identify_risks(self, risk_assessment: Dict, insights: Dict) -> str:
        """Identify investment risks."""
        risks = []
        
        risk_factors = risk_assessment.get('risk_factors', [])
        if 'HIGH_VOLATILITY' in risk_factors:
            risks.append("High volatility")
        if 'HIGH_VAR' in risk_factors:
            risks.append("High downside risk")
        
        market_insights = insights.get('market_insights', [])
        if any('bear' in insight.lower() for insight in market_insights):
            risks.append("Bear market exposure")
        
        return '; '.join(risks) if risks else "Standard market risks apply"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert assessment to dictionary format."""
        print(f"[ASSESSMENT DEBUG] Converting {self.symbol} to dict format")
        print(f"[ASSESSMENT DEBUG] Analysis data keys: {list(self.analysis_data.keys())}")
        print(f"[ASSESSMENT DEBUG] Assessment keys: {list(self.assessment.keys())}")
        
        result = {
            'symbol': self.symbol,
            'analysis': self.analysis_data,
            'assessment': self.assessment,
            'processed_query': self.processed_query,
            'price_data': self.analysis_data.get('price_data', {}),
            'historical_data': self.analysis_data.get('historical_data', {}),
            'predicted_data': self.analysis_data.get('predicted_data', {})
        }
        
        print(f"[ASSESSMENT DEBUG] Final to_dict result keys for {self.symbol}: {list(result.keys())}")
        print(f"[ASSESSMENT DEBUG] Final to_dict has 'assessment' key: {'assessment' in result}")
        print(f"[ASSESSMENT DEBUG] Final to_dict has 'analysis' key: {'analysis' in result}")
        
        return result

class AnalyzerAgent:
    """
    Analyzer Agent that analyzes stocks using predictions.py and calendar events to select the best prediction window.
    """
    def __init__(self, llm=None, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.llm = llm
        self.calendar_tool = CalendarTool()

    def _select_prediction_window(self, symbol: str) -> str:
        """Select prediction window based on system time and calendar events for the symbol."""
        from datetime import datetime, timedelta
        today = datetime.now().date()
        # Fetch events for the symbol
        events = self.calendar_tool.fetch_ticker_events(symbol).events
        # Find the soonest event in the future
        soonest_days = None
        for event in events:
            try:
                event_date = datetime.strptime(event.date, "%Y-%m-%d").date()
                days_until = (event_date - today).days
                if days_until >= 0 and (soonest_days is None or days_until < soonest_days):
                    soonest_days = days_until
            except Exception:
                continue
        # Select prediction window
        if soonest_days is not None:
            if soonest_days <= 1:
                return "min15"
            elif soonest_days <= 3:
                return "hourly"
        # Default to daily
        return "daily"

    def analyze_tickers(self, tickers: List[str], horizon_days: Optional[int] = None, processed_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        results = []
        for symbol in tickers:
            try:
                window = self._select_prediction_window(symbol)
                if window == "min15":
                    analysis = predictions.predict_min15(symbol)
                elif window == "hourly":
                    analysis = predictions.predict_hourly(symbol)
                else:
                    analysis = predictions.predict_daily(symbol)
                assessment = StockAssessment(symbol, {'analysis': analysis}, processed_query)
                results.append(assessment.to_dict())
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                results.append({'symbol': symbol, 'error': str(e)})
        return results

    def analyze_single_ticker(self, symbol: str, horizon_days: Optional[int] = None, processed_query: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            window = self._select_prediction_window(symbol)
            if window == "min15":
                analysis = predictions.predict_min15(symbol)
            elif window == "hourly":
                analysis = predictions.predict_hourly(symbol)
            else:
                analysis = predictions.predict_daily(symbol)
            assessment = StockAssessment(symbol, {'analysis': analysis}, processed_query)
            return assessment.to_dict()
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return {'symbol': symbol, 'error': str(e)}
    
    def _enhance_analysis_with_llm(self, symbol: str, processed_query: Dict[str, Any], risk_params: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analysis results using LLM insights."""
        try:
            # Create prompt for analysis enhancement
            prompt = ANALYZER_MCP_PROMPT.format(
                symbol=symbol,
                risk_tolerance=processed_query.get('risk_tolerance', 'moderate'),
                investment_horizon=processed_query.get('investment_horizon', 'long'),
                capital_amount=processed_query.get('capital_amount', 100000.0),
                horizon_days=180,  # Default
                volatility_threshold=risk_params['volatility_threshold'],
                risk_aversion=risk_params['risk_aversion'],
                confidence_threshold=risk_params['confidence_threshold']
            )
            
            response = self.llm_client.invoke(prompt)
            
            # Parse LLM response for additional insights
            content = response.content
            
            enhanced_analysis = {
                'llm_insights': {
                    'analysis_summary': content,
                    'risk_assessment': self._extract_risk_assessment(content),
                    'investment_recommendation': self._extract_recommendation(content)
                }
            }
            
            return enhanced_analysis
            
        except Exception as e:
            self.logger.error(f"Error enhancing analysis with LLM: {e}")
            return {}
    
    def _extract_risk_assessment(self, content: str) -> str:
        """Extract risk assessment from LLM response."""
        content_lower = content.lower()
        if 'high risk' in content_lower or 'volatile' in content_lower:
            return 'HIGH'
        elif 'low risk' in content_lower or 'stable' in content_lower:
            return 'LOW'
        else:
            return 'MODERATE'
    
    def _extract_recommendation(self, content: str) -> str:
        """Extract investment recommendation from LLM response."""
        content_lower = content.lower()
        if 'buy' in content_lower and 'strong' in content_lower:
            return 'STRONG_BUY'
        elif 'buy' in content_lower:
            return 'BUY'
        elif 'sell' in content_lower:
            return 'SELL'
        elif 'hold' in content_lower:
            return 'HOLD'
        else:
            return 'NEUTRAL' 