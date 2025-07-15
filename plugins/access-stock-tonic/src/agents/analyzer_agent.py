"""
Analyzer Agent - Analyzes each stock using the MCP server and returns structured results with data-based assessments.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import requests
from datetime import datetime
import numpy as np

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_community.chat_models import ChatHuggingFace
    from langchain.prompts import ChatPromptTemplate
    from langchain_mcp_adapters.client import MultiServerMCPClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

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
    Analyzer Agent that analyzes stocks using MCP server and generates comprehensive assessments.
    """
    
    def __init__(self, mcp_url: str = MCP_SERVER_URL, openai_api_key: Optional[str] = None, use_llm: bool = False, 
                 llm_provider: str = "openai", anthropic_api_key: Optional[str] = None, hf_api_key: Optional[str] = None,
                 openai_model: str = "gpt-4", anthropic_model: str = "claude-3-opus-20240229", 
                 hf_model: str = "HuggingFaceH4/zephyr-7b-beta"):
        """
        Initialize the Analyzer Agent.
        
        Args:
            mcp_url: MCP server URL
            openai_api_key: OpenAI API key for LLM operations
            use_llm: Whether to use LLM for enhanced analysis
            llm_provider: LLM provider ("openai", "anthropic", "huggingface")
            anthropic_api_key: Anthropic API key
            hf_api_key: HuggingFace API key
            openai_model: OpenAI model name
            anthropic_model: Anthropic model name
            hf_model: HuggingFace model name
        """
        self.logger = logging.getLogger(__name__)
        self.mcp_url = mcp_url
        self.openai_api_key = openai_api_key
        self.use_llm = use_llm
        self.llm_provider = llm_provider
        self.anthropic_api_key = anthropic_api_key
        self.hf_api_key = hf_api_key
        self.openai_model = openai_model
        self.anthropic_model = anthropic_model
        self.hf_model = hf_model
        
        # Initialize MCP client
        self.mcp_client = None
        self._initialize_mcp_client()
        
        # Initialize LLM client for enhanced analysis
        self.llm_client = None
        if self.use_llm:
            self._initialize_llm_client()
        
        # Initialize SummarizerAgent for individual stock summaries
        self.summarizer = None
        if SUMMARIZER_AVAILABLE:
            self.summarizer = SummarizerAgent(
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
                use_llm=use_llm,
                llm_provider=llm_provider,
                openai_model=openai_model,
                anthropic_model=anthropic_model,
                temperature=0.3
            )
            self.logger.info("SummarizerAgent initialized for individual stock summaries")
        else:
            self.logger.warning("SummarizerAgent not available - individual summaries will be skipped")

    def _initialize_mcp_client(self):
        """Initialize the MCP client with proper authentication."""
        try:
            if self.hf_api_key and self.hf_api_key != "your_huggingface_api_key_here":
                # Debug logging with print statements
                print(f"[MCP DEBUG] Initializing MCP client with HF API key: {self.hf_api_key[:10]}...")
                print(f"[MCP DEBUG] MCP Server URL: {self.mcp_url}")
                
                # Try MultiServerMCPClient first
                try:
                    print("[MCP DEBUG] Attempting MultiServerMCPClient initialization...")
                    self.mcp_client = MultiServerMCPClient({
                        "stock_predictions": {
                            "transport": "sse",
                            "url": self.mcp_url,
                            "headers": {
                                "Authorization": f"Bearer {self.hf_api_key}",
                                "Content-Type": "application/json"
                            }
                        }
                    })
                    print("[MCP DEBUG] MultiServerMCPClient initialized successfully")
                    
                    # Test the connection by getting tools
                    print("[MCP DEBUG] Testing MCP connection...")
                    tools = asyncio.run(self.mcp_client.get_tools())
                    print(f"[MCP DEBUG] MCP connection test successful - found {len(tools)} tools")
                    for i, tool in enumerate(tools):
                        print(f"[MCP DEBUG]   Tool {i}: {tool.name}")
                        
                except Exception as e:
                    print(f"[MCP DEBUG] MultiServerMCPClient failed: {e}")
                    
                    # Fallback to direct SSE client approach
                    try:
                        from mcp import ClientSession
                        from mcp.client.sse import sse_client
                        from langchain_mcp_adapters.tools import load_mcp_tools
                        
                        print("[MCP DEBUG] Attempting direct SSE client connection...")
                        
                        # Create a wrapper class for the direct SSE client
                        class DirectSSEMCPClient:
                            def __init__(self, url, headers):
                                self.url = url
                                self.headers = headers
                                self.session = None
                                self.tools = None
                            
                            async def get_tools(self):
                                if self.tools is None:
                                    async with sse_client(self.url, headers=self.headers) as (read, write):
                                        async with ClientSession(read, write) as session:
                                            await session.initialize()
                                            self.tools = await load_mcp_tools(session)
                                            self.session = session
                                return self.tools
                            
                            async def invoke_tool(self, tool_name, arguments):
                                if self.session is None:
                                    await self.get_tools()
                                
                                # Find the tool
                                tool = None
                                for t in self.tools:
                                    if tool_name in t.name:
                                        tool = t
                                        break
                                
                                if tool:
                                    return await tool.ainvoke(arguments)
                                else:
                                    raise ValueError(f"Tool {tool_name} not found")
                        
                        self.mcp_client = DirectSSEMCPClient(
                            self.mcp_url,
                            {
                                "Authorization": f"Bearer {self.hf_api_key}",
                                "Content-Type": "application/json"
                            }
                        )
                        print("[MCP DEBUG] Direct SSE client initialized successfully")
                        
                        # Test the connection
                        tools = asyncio.run(self.mcp_client.get_tools())
                        print(f"[MCP DEBUG] Direct SSE connection test successful - found {len(tools)} tools")
                        for i, tool in enumerate(tools):
                            print(f"[MCP DEBUG]   Tool {i}: {tool.name}")
                            
                    except Exception as e2:
                        print(f"[MCP DEBUG] Direct SSE client also failed: {e2}")
                        self.mcp_client = None
                        
            else:
                print(f"[MCP DEBUG] No valid HuggingFace API key provided, MCP client not initialized")
                print(f"[MCP DEBUG] HF API key value: {self.hf_api_key}")
        except Exception as e:
            print(f"[MCP DEBUG] Error initializing MCP client: {e}")
            self.mcp_client = None
        
        # Final status check
        if self.mcp_client:
            print(f"[MCP DEBUG] MCP client initialization completed successfully")
        else:
            print(f"[MCP DEBUG] MCP client initialization failed - client is None")

    def _initialize_llm_client(self):
        """Initialize the LLM client for enhanced analysis."""
        try:
            if self.llm_provider == "openai" and self.openai_api_key:
                self.llm_client = ChatOpenAI(
                    model=self.openai_model,
                    temperature=0.1,
                    openai_api_key=self.openai_api_key
                )
                self.logger.info(f"Initialized OpenAI client with model: {self.openai_model}")
            elif self.llm_provider == "anthropic" and self.anthropic_api_key:
                self.llm_client = ChatAnthropic(
                    model=self.anthropic_model,
                    temperature=0.1,
                    anthropic_api_key=self.anthropic_api_key
                )
                self.logger.info(f"Initialized Anthropic client with model: {self.anthropic_model}")
            elif self.llm_provider == "huggingface" and self.hf_api_key:
                self.llm_client = ChatHuggingFace(
                    model=self.hf_model,
                    temperature=0.1,
                    huggingfacehub_api_token=self.hf_api_key
                )
                self.logger.info(f"Initialized HuggingFace client with model: {self.hf_model}")
            else:
                self.logger.warning(f"No valid API key provided for {self.llm_provider}, LLM client not initialized")
                self.llm_client = None
                
            # Initialize prompt template if LLM client is available
            if self.llm_client:
                self.prompt_template = ChatPromptTemplate.from_messages([
                    ("system", ANALYZER_SYSTEM_PROMPT),
                    ("human", ANALYZER_MCP_PROMPT)
                ])
                
        except Exception as e:
            self.logger.error(f"Error initializing LLM client: {e}")
            self.llm_client = None

    def analyze_tickers(self, tickers: List[str], 
                       horizon_days: Optional[int] = None,
                       processed_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Analyze each ticker using the MCP server's daily_analysis endpoint.
        Returns structured results with comprehensive assessments and individual summaries for each ticker.
        
        Args:
            tickers: List of ticker symbols
            horizon_days: Prediction horizon in days (from processed_query if not provided)
            processed_query: Structured query data from query processor
            
        Returns:
            List of dicts: [{ 'symbol': str, 'analysis': dict, 'assessment': dict, 'summary': str }]
        """
        print(f"[ANALYZER DEBUG] Starting analyze_tickers with {len(tickers)} tickers: {tickers}")
        print(f"[ANALYZER DEBUG] Processed query: {processed_query}")
        
        # Determine horizon from processed query if available
        if horizon_days is None and processed_query:
            investment_horizon = processed_query.get('investment_horizon', 'long')
            # Map investment horizon to days
            horizon_mapping = {
                'short': 30,
                'medium': 90,
                'long': 180
            }
            horizon_days = horizon_mapping.get(investment_horizon, 180)
        elif horizon_days is None:
            horizon_days = 180  # Default fallback
            
        print(f"[ANALYZER DEBUG] Using horizon_days: {horizon_days}")
            
        results = []
        for i, symbol in enumerate(tickers):
            try:
                print(f"[ANALYZER DEBUG] Analyzing stock {i+1}/{len(tickers)}: {symbol}")
                
                # Analyze the stock
                analysis_result = self.analyze_single_ticker(symbol, horizon_days, processed_query)
                
                print(f"[ANALYZER DEBUG] Analysis result for {symbol}: {type(analysis_result)}")
                if analysis_result:
                    print(f"[ANALYZER DEBUG] Analysis result keys: {list(analysis_result.keys())}")
                    print(f"[ANALYZER DEBUG] Analysis result has 'analysis' key: {'analysis' in analysis_result}")
                    if 'analysis' in analysis_result:
                        print(f"[ANALYZER DEBUG] Analysis keys: {list(analysis_result['analysis'].keys())}")
                
                if analysis_result:
                    # Create comprehensive assessment
                    print(f"[ANALYZER DEBUG] Creating StockAssessment for {symbol}")
                    stock_assessment = StockAssessment(symbol, analysis_result, processed_query)
                    assessment_data = stock_assessment.to_dict()
                    
                    print(f"[ANALYZER DEBUG] Assessment data keys for {symbol}: {list(assessment_data.keys())}")
                    print(f"[ANALYZER DEBUG] Assessment data has 'assessment' key: {'assessment' in assessment_data}")
                    if 'assessment' in assessment_data:
                        print(f"[ANALYZER DEBUG] Assessment keys: {list(assessment_data['assessment'].keys())}")
                    
                    # Generate individual stock summary
                    if self.summarizer:
                        try:
                            print(f"[ANALYZER DEBUG] Generating summary for {symbol}")
                            stock_summary = self.summarizer.generate_stock_summary(assessment_data)
                            assessment_data['summary'] = stock_summary
                            print(f"[ANALYZER DEBUG] Generated summary for {symbol}")
                        except Exception as summary_error:
                            print(f"[ANALYZER DEBUG] Failed to generate summary for {symbol}: {summary_error}")
                            self.logger.warning(f"Failed to generate summary for {symbol}: {summary_error}")
                            assessment_data['summary'] = f"Summary generation failed for {symbol}"
                    else:
                        print(f"[ANALYZER DEBUG] No summarizer available for {symbol}")
                        assessment_data['summary'] = f"No summarizer available for {symbol}"
                    
                    results.append(assessment_data)
                    print(f"[ANALYZER DEBUG] Completed analysis, assessment, and summary for {symbol}")
                else:
                    print(f"[ANALYZER DEBUG] No analysis result for {symbol}")
                    self.logger.warning(f"No analysis result for {symbol}")
                    
            except Exception as e:
                print(f"[ANALYZER DEBUG] Error analyzing {symbol}: {e}")
                import traceback
                print(f"[ANALYZER DEBUG] Error traceback: {traceback.format_exc()}")
                self.logger.error(f"Error analyzing {symbol}: {e}")
                # Create fallback assessment with simulated data
                fallback_analysis = self._simulate_stock_analysis(symbol, horizon_days, {}, None)
                stock_assessment = StockAssessment(symbol, fallback_analysis, processed_query)
                assessment_data = stock_assessment.to_dict()
                
                # Generate fallback summary
                if self.summarizer:
                    try:
                        stock_summary = self.summarizer.generate_stock_summary(assessment_data)
                        assessment_data['summary'] = stock_summary
                    except Exception as summary_error:
                        print(f"[ANALYZER DEBUG] Failed to generate fallback summary for {symbol}: {summary_error}")
                        self.logger.warning(f"Failed to generate fallback summary for {symbol}: {summary_error}")
                        assessment_data['summary'] = f"Fallback summary generation failed for {symbol}"
                else:
                    assessment_data['summary'] = f"No summarizer available for {symbol}"
                
                results.append(assessment_data)
        
        print(f"[ANALYZER DEBUG] Completed analysis for all {len(tickers)} stocks with individual summaries")
        print(f"[ANALYZER DEBUG] Final results count: {len(results)}")
        for i, result in enumerate(results):
            symbol = result.get('symbol', 'UNKNOWN')
            has_assessment = 'assessment' in result
            has_analysis = 'analysis' in result
            print(f"[ANALYZER DEBUG] Result {i+1}: {symbol} - has_assessment={has_assessment}, has_analysis={has_analysis}")
        
        self.logger.info(f"Completed analysis for all {len(tickers)} stocks with individual summaries")
        return results

    def analyze_single_ticker(self, symbol: str, 
                            horizon_days: Optional[int] = None,
                            processed_query: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Analyze a single ticker using the MCP server's daily_analysis endpoint.
        Args:
            symbol: Ticker symbol
            horizon_days: Prediction horizon in days (from processed_query if not provided)
            processed_query: Structured query data from query processor
        Returns:
            Dict with analysis results, or None if error
        """
        # Determine horizon from processed query if available
        if horizon_days is None and processed_query:
            investment_horizon = processed_query.get('investment_horizon', 'long')
            horizon_mapping = {
                'short': 30,
                'medium': 90,
                'long': 180
            }
            horizon_days = horizon_mapping.get(investment_horizon, 180)
        elif horizon_days is None:
            horizon_days = 180  # Default fallback
        
        # Adjust MCP parameters based on user preferences
        risk_tolerance = processed_query.get('risk_tolerance', 'moderate') if processed_query else 'moderate'
        
        # Map risk tolerance to MCP parameters
        risk_mapping = {
            'conservative': {
                'volatility_threshold': 0.01,  # Lower volatility threshold
                'confidence_threshold': 0.8,   # Higher confidence requirement
                'risk_aversion': 0.8
            },
            'moderate': {
                'volatility_threshold': 0.02,
                'confidence_threshold': 0.6,
                'risk_aversion': 0.6
            },
            'aggressive': {
                'volatility_threshold': 0.03,  # Higher volatility tolerance
                'confidence_threshold': 0.4,   # Lower confidence requirement
                'risk_aversion': 0.2
            }
        }
        
        risk_params = risk_mapping.get(risk_tolerance, risk_mapping['moderate'])
        
        # Use LLM to enhance analysis if available
        if self.use_llm and processed_query:
            enhanced_analysis = self._enhance_analysis_with_llm(symbol, processed_query, risk_params)
        else:
            enhanced_analysis = None
        
        # Try MCP client first, fallback to direct HTTP if not available
        if self.mcp_client:
            print(f"[ANALYSIS DEBUG] Attempting MCP client analysis for {symbol}")
            try:
                result = self._analyze_with_mcp_client(symbol, horizon_days, risk_params, enhanced_analysis)
                if result:
                    print(f"[ANALYSIS DEBUG] MCP client analysis successful for {symbol} - source: {result.get('source', 'unknown')}")
                    return result
                else:
                    print(f"[ANALYSIS DEBUG] MCP client returned None for {symbol}, falling back to HTTP")
            except Exception as e:
                print(f"[ANALYSIS DEBUG] MCP client failed for {symbol}, falling back to HTTP: {e}")
                import traceback
                print(f"[ANALYSIS DEBUG] MCP client error traceback: {traceback.format_exc()}")
        else:
            print(f"[ANALYSIS DEBUG] No MCP client available for {symbol}, using HTTP fallback")
        
        # Fallback to direct HTTP request (original method)
        print(f"[ANALYSIS DEBUG] Attempting HTTP analysis for {symbol}")
        http_result = self._analyze_with_http(symbol, horizon_days, risk_params, enhanced_analysis)
        if http_result:
            print(f"[ANALYSIS DEBUG] HTTP analysis successful for {symbol} - source: {http_result.get('source', 'unknown')}")
        else:
            print(f"[ANALYSIS DEBUG] HTTP analysis failed for {symbol}, using simulated data")
        return http_result
    
    def _analyze_with_mcp_client(self, symbol: str, horizon_days: int, risk_params: Dict[str, Any], enhanced_analysis: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze using MCP client."""
        try:
            self.logger.info(f"Starting MCP client analysis for {symbol}")
            
            # Get tools from MCP client
            self.logger.info("Getting tools from MCP client...")
            tools = asyncio.run(self.mcp_client.get_tools())
            self.logger.info(f"Found {len(tools)} tools in MCP server")
            
            # Log all available tools
            for i, tool in enumerate(tools):
                self.logger.info(f"Tool {i}: {tool.name}")
            
            # Find the stock analysis tool
            analysis_tool = None
            for tool in tools:
                if "stock_predictions_daily_analysis" in tool.name or "daily_analysis" in tool.name:
                    analysis_tool = tool
                    self.logger.info(f"Found analysis tool: {tool.name}")
                    break
            
            if not analysis_tool:
                self.logger.warning("Stock analysis tool not found in MCP server")
                return None
            
            self.logger.info(f"Calling MCP tool {analysis_tool.name} for {symbol}")
            
            # Call the tool with the correct MCP format using the API parameter names
            # Based on the API documentation: s, pd, ld, st, ue, urd, ust, rfr, mi, cw, tw, sw, rrp, usm, smt, sww, sa, uc, us
            try:
                result = asyncio.run(analysis_tool.ainvoke({
                    "s": symbol,  # Stock Symbol
                    "pd": horizon_days,  # Days to Predict
                    "ld": 365,  # Historical Lookback (Days)
                    "st": "chronos",  # Prediction Strategy
                    "ue": True,  # Use Ensemble Methods
                    "urd": True,  # Use Regime Detection
                    "ust": True,  # Use Stress Testing
                    "rfr": 0.02,  # Risk-Free Rate (Annual)
                    "mi": "^GSPC",  # Market Index for Correlation
                    "cw": 0.6,  # Chronos Weight
                    "tw": 0.2,  # Technical Weight
                    "sw": 0.2,  # Statistical Weight
                    "rrp": 4,  # Random Real Points in Long-Horizon Context
                    "usm": True,  # Use Smoothing
                    "smt": "exponential",  # Smoothing Type
                    "sww": 5,  # Smoothing Window Size
                    "sa": 0.3,  # Smoothing Alpha
                    "uc": True,  # Use Enhanced Covariate Data
                    "us": True   # Use Sentiment Analysis
                }))
                self.logger.info(f"MCP tool call successful for {symbol}")
            except Exception as e:
                self.logger.warning(f"API parameter format failed for {symbol}, trying positional arguments: {e}")
                # Fallback to positional arguments in the correct order
                try:
                    result = asyncio.run(analysis_tool.ainvoke([
                        symbol,  # s - Stock Symbol
                        horizon_days,  # pd - Days to Predict
                        365,  # ld - Historical Lookback (Days)
                        "chronos",  # st - Prediction Strategy
                        True,  # ue - Use Ensemble Methods
                        True,  # urd - Use Regime Detection
                        True,  # ust - Use Stress Testing
                        0.02,  # rfr - Risk-Free Rate (Annual)
                        "^GSPC",  # mi - Market Index for Correlation
                        0.6,  # cw - Chronos Weight
                        0.2,  # tw - Technical Weight
                        0.2,  # sw - Statistical Weight
                        4,  # rrp - Random Real Points in Long-Horizon Context
                        True,  # usm - Use Smoothing
                        "exponential",  # smt - Smoothing Type
                        5,  # sww - Smoothing Window Size
                        0.3,  # sa - Smoothing Alpha
                        True,  # uc - Use Enhanced Covariate Data
                        True   # us - Use Sentiment Analysis
                    ]))
                    self.logger.info(f"MCP tool call with positional arguments successful for {symbol}")
                except Exception as e2:
                    self.logger.error(f"Both MCP tool call formats failed for {symbol}: {e2}")
                    # Return None to trigger fallback analysis
                    return None
            
            # Debug logging to see the result format
            print(f"[MCP RESULT DEBUG] MCP result for {symbol} - Type: {type(result)}")
            if hasattr(result, '__len__'):
                print(f"[MCP RESULT DEBUG] MCP result length: {len(result)}")
            if isinstance(result, (list, tuple)):
                print(f"[MCP RESULT DEBUG] MCP result elements: {[type(x) for x in result[:3]] if len(result) >= 3 else [type(x) for x in result]}")
                if len(result) >= 1:
                    print(f"[MCP RESULT DEBUG] First element (signals): {result[0]}")
            elif isinstance(result, dict):
                print(f"[MCP RESULT DEBUG] MCP result keys: {list(result.keys())}")
            
            # Structure the MCP outputs properly for the product bundler
            # MCP returns a tuple of 11 elements: [signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced, historical_data, predicted_data]
            try:
                if isinstance(result, (list, tuple)) and len(result) >= 11:
                    # Handle tuple/list format from API with all 11 elements
                    signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced, historical_data, predicted_data = result[:11]
                    
                    # Enhanced parsing function to handle the specific MCP string format
                    def enhanced_parse_data(data):
                        """Enhanced parsing for MCP data that might be in string format."""
                        print(f"[PARSE DEBUG] Parsing data type: {type(data)}")
                        print(f"[PARSE DEBUG] Data content: {str(data)[:200]}...")
                        
                        if isinstance(data, dict):
                            print(f"[PARSE DEBUG] Data is already dict with keys: {list(data.keys())}")
                            # Normalize signal keys if this is a signals dictionary
                            if any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in data.keys()):
                                normalized_data = {}
                                for key, value in data.items():
                                    # Convert signal keys to lowercase
                                    if key.upper() == 'RSI':
                                        normalized_data['rsi'] = value
                                    elif key.upper() == 'MACD':
                                        normalized_data['macd'] = value
                                    elif key.upper() == 'BOLLINGER':
                                        normalized_data['bollinger'] = value
                                    elif key.upper() == 'SMA':
                                        normalized_data['sma'] = value
                                    elif key.upper() == 'OVERALL':
                                        normalized_data['overall'] = value
                                    else:
                                        normalized_data[key.lower()] = value
                                print(f"[PARSE DEBUG] Normalized signals dict: {list(normalized_data.keys())}")
                                return normalized_data
                            return data
                        elif isinstance(data, str):
                            print(f"[PARSE DEBUG] Data is string, attempting to parse")
                            try:
                                # First try to parse as JSON
                                import json
                                parsed = json.loads(data)
                                print(f"[PARSE DEBUG] JSON parsing successful, type: {type(parsed)}")
                                # If it's a signals dictionary, normalize the keys
                                if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                    normalized_data = {}
                                    for key, value in parsed.items():
                                        # Convert signal keys to lowercase
                                        if key.upper() == 'RSI':
                                            normalized_data['rsi'] = value
                                        elif key.upper() == 'MACD':
                                            normalized_data['macd'] = value
                                        elif key.upper() == 'BOLLINGER':
                                            normalized_data['bollinger'] = value
                                        elif key.upper() == 'SMA':
                                            normalized_data['sma'] = value
                                        elif key.upper() == 'OVERALL':
                                            normalized_data['overall'] = value
                                        else:
                                            normalized_data[key.lower()] = value
                                    print(f"[PARSE DEBUG] Normalized signals from JSON: {list(normalized_data.keys())}")
                                    return normalized_data
                                return parsed
                            except (json.JSONDecodeError, TypeError):
                                print(f"[PARSE DEBUG] JSON parsing failed, trying root= format")
                                # Handle the specific MCP format: "root={...}"
                                if data.startswith("root="):
                                    try:
                                        # Extract the dictionary part after "root="
                                        dict_str = data[5:]  # Remove "root=" prefix
                                        # Convert single quotes to double quotes for JSON parsing
                                        dict_str = dict_str.replace("'", '"')
                                        # Handle boolean values
                                        dict_str = dict_str.replace('True', 'true').replace('False', 'false')
                                        # Handle None values
                                        dict_str = dict_str.replace('None', 'null')
                                        parsed = json.loads(dict_str)
                                        print(f"[PARSE DEBUG] Root= parsing successful, type: {type(parsed)}")
                                        # If it's a signals dictionary, normalize the keys
                                        if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                            normalized_data = {}
                                            for key, value in parsed.items():
                                                # Convert signal keys to lowercase
                                                if key.upper() == 'RSI':
                                                    normalized_data['rsi'] = value
                                                elif key.upper() == 'MACD':
                                                    normalized_data['macd'] = value
                                                elif key.upper() == 'BOLLINGER':
                                                    normalized_data['bollinger'] = value
                                                elif key.upper() == 'SMA':
                                                    normalized_data['sma'] = value
                                                elif key.upper() == 'OVERALL':
                                                    normalized_data['overall'] = value
                                                else:
                                                    normalized_data[key.lower()] = value
                                            print(f"[PARSE DEBUG] Normalized signals from root=: {list(normalized_data.keys())}")
                                            return normalized_data
                                        return parsed
                                    except (json.JSONDecodeError, TypeError) as e:
                                        print(f"[PARSE DEBUG] Failed to parse root= format: {e}")
                                        return {"raw_data": data, "parsed": False}
                                else:
                                    print(f"[PARSE DEBUG] Trying ast.literal_eval")
                                    # Try to evaluate as Python literal (safer than eval)
                                    try:
                                        import ast
                                        parsed = ast.literal_eval(data)
                                        print(f"[PARSE DEBUG] ast.literal_eval successful, type: {type(parsed)}")
                                        # If it's a signals dictionary, normalize the keys
                                        if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                            normalized_data = {}
                                            for key, value in parsed.items():
                                                # Convert signal keys to lowercase
                                                if key.upper() == 'RSI':
                                                    normalized_data['rsi'] = value
                                                elif key.upper() == 'MACD':
                                                    normalized_data['macd'] = value
                                                elif key.upper() == 'BOLLINGER':
                                                    normalized_data['bollinger'] = value
                                                elif key.upper() == 'SMA':
                                                    normalized_data['sma'] = value
                                                elif key.upper() == 'OVERALL':
                                                    normalized_data['overall'] = value
                                                else:
                                                    normalized_data[key.lower()] = value
                                            print(f"[PARSE DEBUG] Normalized signals from ast: {list(normalized_data.keys())}")
                                            return normalized_data
                                        return parsed
                                    except (ValueError, SyntaxError) as e:
                                        print(f"[PARSE DEBUG] ast.literal_eval failed: {e}")
                                        return {"raw_data": data, "parsed": False}
                        else:
                            print(f"[PARSE DEBUG] Data is neither dict nor string, returning as is")
                            return {"raw_data": str(data), "parsed": False}
                    
                    # Parse all the data components with detailed debugging
                    print(f"[MCP PARSE DEBUG] Starting to parse MCP result components")
                    print(f"[MCP PARSE DEBUG] Signals (index 0): {type(signals)}")
                    parsed_signals = enhanced_parse_data(signals)
                    print(f"[MCP PARSE DEBUG] Parsed signals: {type(parsed_signals)} - keys: {list(parsed_signals.keys()) if isinstance(parsed_signals, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Metrics (index 2): {type(metrics)}")
                    parsed_metrics = enhanced_parse_data(metrics)
                    print(f"[MCP PARSE DEBUG] Parsed metrics: {type(parsed_metrics)} - keys: {list(parsed_metrics.keys()) if isinstance(parsed_metrics, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Risk (index 3): {type(risk)}")
                    parsed_risk = enhanced_parse_data(risk)
                    print(f"[MCP PARSE DEBUG] Parsed risk: {type(parsed_risk)} - keys: {list(parsed_risk.keys()) if isinstance(parsed_risk, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Sector (index 4): {type(sector)}")
                    parsed_sector = enhanced_parse_data(sector)
                    print(f"[MCP PARSE DEBUG] Parsed sector: {type(parsed_sector)} - keys: {list(parsed_sector.keys()) if isinstance(parsed_sector, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Regime (index 5): {type(regime)}")
                    parsed_regime = enhanced_parse_data(regime)
                    print(f"[MCP PARSE DEBUG] Parsed regime: {type(parsed_regime)} - keys: {list(parsed_regime.keys()) if isinstance(parsed_regime, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Stress (index 6): {type(stress)}")
                    parsed_stress = enhanced_parse_data(stress)
                    print(f"[MCP PARSE DEBUG] Parsed stress: {type(parsed_stress)} - keys: {list(parsed_stress.keys()) if isinstance(parsed_stress, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Ensemble (index 7): {type(ensemble)}")
                    parsed_ensemble = enhanced_parse_data(ensemble)
                    print(f"[MCP PARSE DEBUG] Parsed ensemble: {type(parsed_ensemble)} - keys: {list(parsed_ensemble.keys()) if isinstance(parsed_ensemble, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Advanced (index 8): {type(advanced)}")
                    parsed_advanced = enhanced_parse_data(advanced)
                    print(f"[MCP PARSE DEBUG] Parsed advanced: {type(parsed_advanced)} - keys: {list(parsed_advanced.keys()) if isinstance(parsed_advanced, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Historical (index 9): {type(historical_data)}")
                    parsed_historical = enhanced_parse_data(historical_data)
                    print(f"[MCP PARSE DEBUG] Parsed historical: {type(parsed_historical)} - keys: {list(parsed_historical.keys()) if isinstance(parsed_historical, dict) else 'not dict'}")
                    
                    print(f"[MCP PARSE DEBUG] Predicted (index 10): {type(predicted_data)}")
                    parsed_predicted = enhanced_parse_data(predicted_data)
                    print(f"[MCP PARSE DEBUG] Parsed predicted: {type(parsed_predicted)} - keys: {list(parsed_predicted.keys()) if isinstance(parsed_predicted, dict) else 'not dict'}")
                    
                    # Extract price data for summarizer and product bundler
                    current_price = None
                    predicted_price = None
                    current_date = None
                    predicted_date = None
                    
                    # Extract current price from historical data
                    if isinstance(parsed_historical, dict):
                        prices = parsed_historical.get('prices', [])
                        dates = parsed_historical.get('dates', [])
                        if prices and dates and len(prices) > 0 and len(dates) > 0:
                            current_price = float(prices[-1])  # Last historical price
                            current_date = str(dates[-1])      # Last historical date
                            print(f"[PRICE DEBUG] Extracted current price: {current_price} on {current_date}")
                    
                    # Extract predicted price from predicted data
                    if isinstance(parsed_predicted, dict):
                        pred_prices = parsed_predicted.get('prices', [])
                        pred_dates = parsed_predicted.get('dates', [])
                        if pred_prices and pred_dates and len(pred_prices) > 0 and len(pred_dates) > 0:
                            predicted_price = float(pred_prices[-1])  # Last predicted price
                            predicted_date = str(pred_dates[-1])      # Last predicted date
                            print(f"[PRICE DEBUG] Extracted predicted price: {predicted_price} on {predicted_date}")
                    
                    # Calculate price change if both prices are available
                    price_change = None
                    price_change_pct = None
                    if current_price and predicted_price:
                        price_change = predicted_price - current_price
                        price_change_pct = (price_change / current_price) * 100
                        print(f"[PRICE DEBUG] Price change: ${price_change:.2f} ({price_change_pct:+.2f}%)")
                    
                    structured_result = {
                        "symbol": symbol,
                        "analysis": {
                            "signals": parsed_signals,
                            "metrics": parsed_metrics,
                            "risk": parsed_risk,
                            "sector": parsed_sector,
                            "regime": parsed_regime,
                            "stress": parsed_stress,
                            "ensemble": parsed_ensemble,
                            "advanced": parsed_advanced
                        },
                        "plot": plot if plot else None,
                        "historical_data": parsed_historical,
                        "predicted_data": parsed_predicted,
                        "price_data": {
                            "current_price": current_price,
                            "current_date": current_date,
                            "predicted_price": predicted_price,
                            "predicted_date": predicted_date,
                            "price_change": price_change,
                            "price_change_pct": price_change_pct
                        },
                        "source": "mcp_server"
                    }
                    
                    print(f"[MCP FINAL DEBUG] Final structured result for {symbol}:")
                    print(f"[MCP FINAL DEBUG]   Source: {structured_result['source']}")
                    print(f"[MCP FINAL DEBUG]   Analysis keys: {list(structured_result['analysis'].keys())}")
                    print(f"[MCP FINAL DEBUG]   Signals: {parsed_signals}")
                    print(f"[MCP FINAL DEBUG]   Price data: {structured_result['price_data']}")
                    
                    # Add LLM insights if available
                    if enhanced_analysis:
                        structured_result["analysis"]["llm_insights"] = enhanced_analysis
                    
                    print(f"[MCP FINAL DEBUG] Final structured result for {symbol}:")
                    print(f"[MCP FINAL DEBUG]   Source: {structured_result['source']}")
                    print(f"[MCP FINAL DEBUG]   Analysis keys: {list(structured_result['analysis'].keys())}")
                    print(f"[MCP FINAL DEBUG]   Signals: {parsed_signals}")
                    print(f"[MCP FINAL DEBUG]   Price data: {structured_result['price_data']}")
                    
                    # Ensure all required fields are present for assessment generation
                    if not isinstance(parsed_signals, dict):
                        parsed_signals = {"raw_data": str(parsed_signals), "parsed": False}
                    if not isinstance(parsed_metrics, dict):
                        parsed_metrics = {"raw_data": str(parsed_metrics), "parsed": False}
                    if not isinstance(parsed_risk, dict):
                        parsed_risk = {"raw_data": str(parsed_risk), "parsed": False}
                    if not isinstance(parsed_sector, dict):
                        parsed_sector = {"raw_data": str(parsed_sector), "parsed": False}
                    if not isinstance(parsed_regime, dict):
                        parsed_regime = {"raw_data": str(parsed_regime), "parsed": False}
                    if not isinstance(parsed_stress, dict):
                        parsed_stress = {"raw_data": str(parsed_stress), "parsed": False}
                    if not isinstance(parsed_ensemble, dict):
                        parsed_ensemble = {"raw_data": str(parsed_ensemble), "parsed": False}
                    if not isinstance(parsed_advanced, dict):
                        parsed_advanced = {"raw_data": str(parsed_advanced), "parsed": False}
                    
                    # Update the analysis structure with validated data
                    structured_result["analysis"] = {
                        "signals": parsed_signals,
                        "metrics": parsed_metrics,
                        "risk": parsed_risk,
                        "sector": parsed_sector,
                        "regime": parsed_regime,
                        "stress": parsed_stress,
                        "ensemble": parsed_ensemble,
                        "advanced": parsed_advanced
                    }
                    
                    # Add LLM insights if available
                    if enhanced_analysis:
                        structured_result["analysis"]["llm_insights"] = enhanced_analysis
                    
                    self.logger.info(f"Successfully structured MCP result for {symbol} with price data")
                    return structured_result
                elif isinstance(result, (list, tuple)) and len(result) >= 9:
                    # Handle legacy 9-element format
                    signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced = result[:9]
                    
                    def enhanced_parse_data(data):
                        """Enhanced parsing for MCP data that might be in string format."""
                        if isinstance(data, dict):
                            # Normalize signal keys if this is a signals dictionary
                            if any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in data.keys()):
                                normalized_data = {}
                                for key, value in data.items():
                                    # Convert signal keys to lowercase
                                    if key.upper() == 'RSI':
                                        normalized_data['rsi'] = value
                                    elif key.upper() == 'MACD':
                                        normalized_data['macd'] = value
                                    elif key.upper() == 'BOLLINGER':
                                        normalized_data['bollinger'] = value
                                    elif key.upper() == 'SMA':
                                        normalized_data['sma'] = value
                                    elif key.upper() == 'OVERALL':
                                        normalized_data['overall'] = value
                                    else:
                                        normalized_data[key.lower()] = value
                                return normalized_data
                            return data
                        elif isinstance(data, str):
                            try:
                                # First try to parse as JSON
                                import json
                                parsed = json.loads(data)
                                # If it's a signals dictionary, normalize the keys
                                if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                    normalized_data = {}
                                    for key, value in parsed.items():
                                        # Convert signal keys to lowercase
                                        if key.upper() == 'RSI':
                                            normalized_data['rsi'] = value
                                        elif key.upper() == 'MACD':
                                            normalized_data['macd'] = value
                                        elif key.upper() == 'BOLLINGER':
                                            normalized_data['bollinger'] = value
                                        elif key.upper() == 'SMA':
                                            normalized_data['sma'] = value
                                        elif key.upper() == 'OVERALL':
                                            normalized_data['overall'] = value
                                        else:
                                            normalized_data[key.lower()] = value
                                    return normalized_data
                                return parsed
                            except (json.JSONDecodeError, TypeError):
                                # Handle the specific MCP format: "root={...}"
                                if data.startswith("root="):
                                    try:
                                        # Extract the dictionary part after "root="
                                        dict_str = data[5:]  # Remove "root=" prefix
                                        # Convert single quotes to double quotes for JSON parsing
                                        dict_str = dict_str.replace("'", '"')
                                        # Handle boolean values
                                        dict_str = dict_str.replace('True', 'true').replace('False', 'false')
                                        # Handle None values
                                        dict_str = dict_str.replace('None', 'null')
                                        parsed = json.loads(dict_str)
                                        # If it's a signals dictionary, normalize the keys
                                        if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                            normalized_data = {}
                                            for key, value in parsed.items():
                                                # Convert signal keys to lowercase
                                                if key.upper() == 'RSI':
                                                    normalized_data['rsi'] = value
                                                elif key.upper() == 'MACD':
                                                    normalized_data['macd'] = value
                                                elif key.upper() == 'BOLLINGER':
                                                    normalized_data['bollinger'] = value
                                                elif key.upper() == 'SMA':
                                                    normalized_data['sma'] = value
                                                elif key.upper() == 'OVERALL':
                                                    normalized_data['overall'] = value
                                                else:
                                                    normalized_data[key.lower()] = value
                                            return normalized_data
                                        return parsed
                                    except (json.JSONDecodeError, TypeError) as e:
                                        print(f"[PARSE DEBUG] Failed to parse root= format: {e}")
                                        return {"raw_data": data, "parsed": False}
                                else:
                                    # Try to evaluate as Python literal (safer than eval)
                                    try:
                                        import ast
                                        parsed = ast.literal_eval(data)
                                        # If it's a signals dictionary, normalize the keys
                                        if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                            normalized_data = {}
                                            for key, value in parsed.items():
                                                # Convert signal keys to lowercase
                                                if key.upper() == 'RSI':
                                                    normalized_data['rsi'] = value
                                                elif key.upper() == 'MACD':
                                                    normalized_data['macd'] = value
                                                elif key.upper() == 'BOLLINGER':
                                                    normalized_data['bollinger'] = value
                                                elif key.upper() == 'SMA':
                                                    normalized_data['sma'] = value
                                                elif key.upper() == 'OVERALL':
                                                    normalized_data['overall'] = value
                                                else:
                                                    normalized_data[key.lower()] = value
                                            return normalized_data
                                        return parsed
                                    except (ValueError, SyntaxError):
                                        return {"raw_data": data, "parsed": False}
                        else:
                            return {"raw_data": str(data), "parsed": False}
                    
                    structured_result = {
                        "symbol": symbol,
                        "analysis": {
                            "signals": enhanced_parse_data(signals),
                            "metrics": enhanced_parse_data(metrics),
                            "risk": enhanced_parse_data(risk),
                            "sector": enhanced_parse_data(sector),
                            "regime": enhanced_parse_data(regime),
                            "stress": enhanced_parse_data(stress),
                            "ensemble": enhanced_parse_data(ensemble),
                            "advanced": enhanced_parse_data(advanced)
                        },
                        "plot": plot if plot else None,
                        "historical_data": {},
                        "predicted_data": {},
                        "price_data": {
                            "current_price": None,
                            "current_date": None,
                            "predicted_price": None,
                            "predicted_date": None,
                            "price_change": None,
                            "price_change_pct": None
                        },
                        "source": "mcp_server_legacy"
                    }
                    self.logger.info(f"Successfully structured MCP legacy result for {symbol}")
                elif isinstance(result, dict):
                    # Handle dictionary format (fallback)
                    structured_result = {
                        "symbol": symbol,
                        "analysis": {
                            "signals": result.get("signals", {}),
                            "metrics": result.get("metrics", {}),
                            "risk": result.get("risk", {}),
                            "sector": result.get("sector", {}),
                            "regime": result.get("regime", {}),
                            "stress": result.get("stress", {}),
                            "ensemble": result.get("ensemble", {}),
                            "advanced": result.get("advanced", {})
                        },
                        "plot": result.get("plot", None),
                        "historical_data": result.get("historical_data", {}),
                        "predicted_data": result.get("predicted_data", {}),
                        "price_data": result.get("price_data", {
                            "current_price": None,
                            "current_date": None,
                            "predicted_price": None,
                            "predicted_date": None,
                            "price_change": None,
                            "price_change_pct": None
                        }),
                        "source": "mcp_server"
                    }
                    self.logger.info(f"Successfully structured MCP dict result for {symbol}")
                else:
                    # Handle unexpected format
                    self.logger.warning(f"Unexpected result format for {symbol}: {type(result)}")
                    structured_result = {
                        "symbol": symbol,
                        "analysis": {
                            "signals": {},
                            "metrics": {},
                            "risk": {},
                            "sector": {},
                            "regime": {},
                            "stress": {},
                            "ensemble": {},
                            "advanced": {}
                        },
                        "plot": None,
                        "historical_data": {},
                        "predicted_data": {},
                        "price_data": {
                            "current_price": None,
                            "current_date": None,
                            "predicted_price": None,
                            "predicted_date": None,
                            "price_change": None,
                            "price_change_pct": None
                        },
                        "source": "mcp_server_fallback"
                    }
            except Exception as parse_error:
                self.logger.error(f"Error parsing MCP result for {symbol}: {parse_error}")
                # Create a safe fallback structure
                structured_result = {
                    "symbol": symbol,
                    "analysis": {
                        "signals": {"error": "Failed to parse MCP data", "raw_result": str(result)},
                        "metrics": {},
                        "risk": {},
                        "sector": {},
                        "regime": {},
                        "stress": {},
                        "ensemble": {},
                        "advanced": {}
                    },
                    "plot": None,
                    "historical_data": {},
                    "predicted_data": {},
                    "price_data": {
                        "current_price": None,
                        "current_date": None,
                        "predicted_price": None,
                        "predicted_date": None,
                        "price_change": None,
                        "price_change_pct": None
                    },
                    "source": "mcp_server_error"
                }
            
            # Enhance with LLM insights if available
            if enhanced_analysis:
                structured_result["analysis"]["llm_insights"] = enhanced_analysis.get('llm_insights', {})
            
            print(f"[MCP FINAL DEBUG] Final structured result for {symbol}:")
            print(f"[MCP FINAL DEBUG]   Source: {structured_result.get('source', 'unknown')}")
            print(f"[MCP FINAL DEBUG]   Analysis keys: {list(structured_result.get('analysis', {}).keys())}")
            print(f"[MCP FINAL DEBUG]   Signals: {structured_result.get('analysis', {}).get('signals', {})}")
            print(f"[MCP FINAL DEBUG]   Price data: {structured_result.get('price_data', {})}")
            
            return structured_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} with MCP client: {e}")
            return None
    
    def _analyze_with_http(self, symbol: str, horizon_days: int, risk_params: Dict[str, Any], enhanced_analysis: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Fallback HTTP analysis method."""
        try:
            # Debug logging
            self.logger.info(f"Attempting HTTP analysis for {symbol} with HF API key: {self.hf_api_key[:10] if self.hf_api_key else 'None'}...")
            
            # Use the correct MCP endpoint format
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.hf_api_key and self.hf_api_key != "your_huggingface_api_key_here":
                headers["Authorization"] = f"Bearer {self.hf_api_key}"
                self.logger.info("Added Authorization header with HF API key")
            else:
                self.logger.warning("No valid HF API key for HTTP request")
            
            # Try different MCP endpoints
            endpoints_to_try = [
                "https://tonic-stock-predictions.hf.space/gradio_api/mcp/sse",
                "https://tonic-stock-predictions.hf.space/mcp/",
                "https://tonic-stock-predictions.hf.space/api/predict"
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    self.logger.info(f"Trying endpoint: {endpoint}")
                    
                    # Use the correct MCP tool call format
                    if "sse" in endpoint:
                        # For SSE endpoint, use the MCP tool format with API parameter names
                        payload = {
                            "method": "tools/call",
                            "params": {
                                "name": "stock_predictions_daily_analysis",
                                "arguments": {
                                    "s": symbol,  # Stock Symbol
                                    "pd": horizon_days,  # Days to Predict
                                    "ld": 365,  # Historical Lookback (Days)
                                    "st": "chronos",  # Prediction Strategy
                                    "ue": True,  # Use Ensemble Methods
                                    "urd": True,  # Use Regime Detection
                                    "ust": True,  # Use Stress Testing
                                    "rfr": 0.02,  # Risk-Free Rate (Annual)
                                    "mi": "^GSPC",  # Market Index for Correlation
                                    "cw": 0.6,  # Chronos Weight
                                    "tw": 0.2,  # Technical Weight
                                    "sw": 0.2,  # Statistical Weight
                                    "rrp": 4,  # Random Real Points in Long-Horizon Context
                                    "usm": True,  # Use Smoothing
                                    "smt": "exponential",  # Smoothing Type
                                    "sww": 5,  # Smoothing Window Size
                                    "sa": 0.3,  # Smoothing Alpha
                                    "uc": True,  # Use Enhanced Covariate Data
                                    "us": True   # Use Sentiment Analysis
                                }
                            }
                        }
                    else:
                        # For other endpoints, use simpler format with positional arguments
                        payload = {
                            "data": [
                                symbol,  # s - Stock Symbol
                                horizon_days,  # pd - Days to Predict
                                365,  # ld - Historical Lookback (Days)
                                "chronos",  # st - Prediction Strategy
                                True,  # ue - Use Ensemble Methods
                                True,  # urd - Use Regime Detection
                                True,  # ust - Use Stress Testing
                                0.02,  # rfr - Risk-Free Rate (Annual)
                                "^GSPC",  # mi - Market Index for Correlation
                                0.6,  # cw - Chronos Weight
                                0.2,  # tw - Technical Weight
                                0.2,  # sw - Statistical Weight
                                4,  # rrp - Random Real Points in Long-Horizon Context
                                True,  # usm - Use Smoothing
                                "exponential",  # smt - Smoothing Type
                                5,  # sww - Smoothing Window Size
                                0.3,  # sa - Smoothing Alpha
                                True,  # uc - Use Enhanced Covariate Data
                                True   # us - Use Sentiment Analysis
                            ]
                        }
                    
                    response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"Success with endpoint: {endpoint}")
                        data = response.json()
                        
                        # Enhanced parsing function to handle the specific MCP string format
                        def enhanced_parse_data(data_item):
                            """Enhanced parsing for MCP data that might be in string format."""
                            if isinstance(data_item, dict):
                                # Normalize signal keys if this is a signals dictionary
                                if any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in data_item.keys()):
                                    normalized_data = {}
                                    for key, value in data_item.items():
                                        # Convert signal keys to lowercase
                                        if key.upper() == 'RSI':
                                            normalized_data['rsi'] = value
                                        elif key.upper() == 'MACD':
                                            normalized_data['macd'] = value
                                        elif key.upper() == 'BOLLINGER':
                                            normalized_data['bollinger'] = value
                                        elif key.upper() == 'SMA':
                                            normalized_data['sma'] = value
                                        elif key.upper() == 'OVERALL':
                                            normalized_data['overall'] = value
                                        else:
                                            normalized_data[key.lower()] = value
                                    return normalized_data
                                return data_item
                            elif isinstance(data_item, str):
                                try:
                                    # First try to parse as JSON
                                    import json
                                    parsed = json.loads(data_item)
                                    # If it's a signals dictionary, normalize the keys
                                    if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                        normalized_data = {}
                                        for key, value in parsed.items():
                                            # Convert signal keys to lowercase
                                            if key.upper() == 'RSI':
                                                normalized_data['rsi'] = value
                                            elif key.upper() == 'MACD':
                                                normalized_data['macd'] = value
                                            elif key.upper() == 'BOLLINGER':
                                                normalized_data['bollinger'] = value
                                            elif key.upper() == 'SMA':
                                                normalized_data['sma'] = value
                                            elif key.upper() == 'OVERALL':
                                                normalized_data['overall'] = value
                                            else:
                                                normalized_data[key.lower()] = value
                                        return normalized_data
                                    return parsed
                                except (json.JSONDecodeError, TypeError):
                                    # Handle the specific MCP format: "root={...}"
                                    if data_item.startswith("root="):
                                        try:
                                            # Extract the dictionary part after "root="
                                            dict_str = data_item[5:]  # Remove "root=" prefix
                                            # Convert single quotes to double quotes for JSON parsing
                                            dict_str = dict_str.replace("'", '"')
                                            # Handle boolean values
                                            dict_str = dict_str.replace('True', 'true').replace('False', 'false')
                                            # Handle None values
                                            dict_str = dict_str.replace('None', 'null')
                                            parsed = json.loads(dict_str)
                                            # If it's a signals dictionary, normalize the keys
                                            if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                                normalized_data = {}
                                                for key, value in parsed.items():
                                                    # Convert signal keys to lowercase
                                                    if key.upper() == 'RSI':
                                                        normalized_data['rsi'] = value
                                                    elif key.upper() == 'MACD':
                                                        normalized_data['macd'] = value
                                                    elif key.upper() == 'BOLLINGER':
                                                        normalized_data['bollinger'] = value
                                                    elif key.upper() == 'SMA':
                                                        normalized_data['sma'] = value
                                                    elif key.upper() == 'OVERALL':
                                                        normalized_data['overall'] = value
                                                    else:
                                                        normalized_data[key.lower()] = value
                                                return normalized_data
                                            return parsed
                                        except (json.JSONDecodeError, TypeError) as e:
                                            print(f"[PARSE DEBUG] Failed to parse root= format: {e}")
                                            return {"raw_data": data_item, "parsed": False}
                                    else:
                                        # Try to evaluate as Python literal (safer than eval)
                                        try:
                                            import ast
                                            parsed = ast.literal_eval(data_item)
                                            # If it's a signals dictionary, normalize the keys
                                            if isinstance(parsed, dict) and any(key.upper() in ['RSI', 'MACD', 'BOLLINGER', 'SMA', 'OVERALL'] for key in parsed.keys()):
                                                normalized_data = {}
                                                for key, value in parsed.items():
                                                    # Convert signal keys to lowercase
                                                    if key.upper() == 'RSI':
                                                        normalized_data['rsi'] = value
                                                    elif key.upper() == 'MACD':
                                                        normalized_data['macd'] = value
                                                    elif key.upper() == 'BOLLINGER':
                                                        normalized_data['bollinger'] = value
                                                    elif key.upper() == 'SMA':
                                                        normalized_data['sma'] = value
                                                    elif key.upper() == 'OVERALL':
                                                        normalized_data['overall'] = value
                                                    else:
                                                        normalized_data[key.lower()] = value
                                                return normalized_data
                                            return parsed
                                        except (ValueError, SyntaxError):
                                            return {"raw_data": data_item, "parsed": False}
                            else:
                                return {"raw_data": str(data_item), "parsed": False}
                        
                        # Parse all the data components
                        parsed_signals = enhanced_parse_data(data.get("signals", {}))
                        parsed_metrics = enhanced_parse_data(data.get("metrics", {}))
                        parsed_risk = enhanced_parse_data(data.get("risk", {}))
                        parsed_sector = enhanced_parse_data(data.get("sector", {}))
                        parsed_regime = enhanced_parse_data(data.get("regime", {}))
                        parsed_stress = enhanced_parse_data(data.get("stress", {}))
                        parsed_ensemble = enhanced_parse_data(data.get("ensemble", {}))
                        parsed_advanced = enhanced_parse_data(data.get("advanced", {}))
                        parsed_historical = enhanced_parse_data(data.get("historical_data", {}))
                        parsed_predicted = enhanced_parse_data(data.get("predicted_data", {}))
                        
                        # Extract price data for summarizer and product bundler
                        current_price = None
                        predicted_price = None
                        current_date = None
                        predicted_date = None
                        
                        # Extract current price from historical data
                        if isinstance(parsed_historical, dict):
                            prices = parsed_historical.get('prices', [])
                            dates = parsed_historical.get('dates', [])
                            if prices and dates and len(prices) > 0 and len(dates) > 0:
                                current_price = float(prices[-1])  # Last historical price
                                current_date = str(dates[-1])      # Last historical date
                                print(f"[PRICE DEBUG] HTTP: Extracted current price: {current_price} on {current_date}")
                        
                        # Extract predicted price from predicted data
                        if isinstance(parsed_predicted, dict):
                            pred_prices = parsed_predicted.get('prices', [])
                            pred_dates = parsed_predicted.get('dates', [])
                            if pred_prices and pred_dates and len(pred_prices) > 0 and len(pred_dates) > 0:
                                predicted_price = float(pred_prices[-1])  # Last predicted price
                                predicted_date = str(pred_dates[-1])      # Last predicted date
                                print(f"[PRICE DEBUG] HTTP: Extracted predicted price: {predicted_price} on {predicted_date}")
                        
                        # Calculate price change if both prices are available
                        price_change = None
                        price_change_pct = None
                        if current_price and predicted_price:
                            price_change = predicted_price - current_price
                            price_change_pct = (price_change / current_price) * 100
                            print(f"[PRICE DEBUG] HTTP: Price change: ${price_change:.2f} ({price_change_pct:+.2f}%)")
                        
                        structured_data = {
                            "symbol": symbol,
                            "analysis": {
                                "signals": parsed_signals,
                                "metrics": parsed_metrics,
                                "risk": parsed_risk,
                                "sector": parsed_sector,
                                "regime": parsed_regime,
                                "stress": parsed_stress,
                                "ensemble": parsed_ensemble,
                                "advanced": parsed_advanced
                            },
                            "plot": data.get("plot", None),
                            "historical_data": parsed_historical,
                            "predicted_data": parsed_predicted,
                            "price_data": {
                                "current_price": current_price,
                                "current_date": current_date,
                                "predicted_price": predicted_price,
                                "predicted_date": predicted_date,
                                "price_change": price_change,
                                "price_change_pct": price_change_pct
                            },
                            "source": "mcp_http"
                        }
                        
                        # Enhance with LLM insights if available
                        if enhanced_analysis:
                            structured_data["analysis"]["llm_insights"] = enhanced_analysis.get('llm_insights', {})
                        
                        return structured_data
                    else:
                        self.logger.warning(f"Endpoint {endpoint} returned status {response.status_code}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed with endpoint {endpoint}: {e}")
                    continue
            
            # If all endpoints fail, return simulated data
            self.logger.warning("All MCP endpoints failed, returning simulated data")
            return self._simulate_stock_analysis(symbol, horizon_days, risk_params, enhanced_analysis)
            
        except Exception as e:
            self.logger.error(f"Error in HTTP analysis for {symbol}: {e}")
            return self._simulate_stock_analysis(symbol, horizon_days, risk_params, enhanced_analysis)
    
    def _simulate_stock_analysis(self, symbol: str, horizon_days: int, risk_params: Dict[str, Any], enhanced_analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate stock analysis when MCP server is unavailable."""
        # Create simulated analysis data with proper structure
        current_price = 100.0 + (hash(symbol) % 200)  # Simulate current price
        predicted_price = current_price * (1.0 + (hash(symbol) % 20 - 10) / 100)  # Simulate predicted price
        
        simulated_data = {
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
                    "volatility": risk_params.get('volatility_threshold', 0.2),
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
            "historical_data": {
                "dates": [
                    "2024-01-09 00:00:00",
                    "2024-01-10 00:00:00",
                    "2024-01-11 00:00:00",
                    "2025-06-24 00:00:00"
                ],
                "prices": [
                    current_price * 0.95,
                    current_price * 0.97,
                    current_price * 0.99,
                    current_price
                ],
                "volume": [
                    42841800,
                    46792900,
                    49128400,
                    53697168
                ]
            },
            "predicted_data": {
                "dates": [
                    "2025-06-25 00:00:00-04:00",
                    "2025-06-26 00:00:00-04:00",
                    "2025-10-25 00:00:00-04:00",
                    "2025-10-26 00:00:00-04:00"
                ],
                "prices": [
                    predicted_price * 0.99,
                    predicted_price * 1.01,
                    predicted_price * 1.02,
                    predicted_price
                ],
                "uncertainty": [
                    0.0835189849742409,
                    0.09299770725363242,
                    0.10358541565849332,
                    0.08440839049366794
                ],
                "volume": [
                    29924716,
                    25486276.817427535,
                    39171941.60650043,
                    9.42765494181296e+22
                ]
            },
            "price_data": {
                "current_price": current_price,
                "current_date": "2025-06-24 00:00:00",
                "predicted_price": predicted_price,
                "predicted_date": "2025-10-26 00:00:00-04:00",
                "price_change": predicted_price - current_price,
                "price_change_pct": ((predicted_price - current_price) / current_price * 100)
            },
            "source": "simulated"
        }
        
        # Enhance with LLM insights if available
        if enhanced_analysis:
            simulated_data["analysis"]["llm_insights"] = enhanced_analysis.get('llm_insights', {})
        
        return simulated_data
    
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