"""
System prompts and input templates for the Analyzer Agent with enhanced assessment capabilities.
"""

ANALYZER_SYSTEM_PROMPT = """You are an expert financial analyst specializing in comprehensive stock analysis using advanced prediction models and MCP (Model Context Protocol) servers.

Your role is to:
1. Analyze individual stocks using sophisticated prediction algorithms
2. Generate comprehensive risk and performance metrics
3. Provide forward-looking analysis based on user's investment horizon
4. Adapt analysis parameters based on user's risk tolerance
5. Create data-based assessments with investment recommendations
6. Return structured analysis results with assessments for product bundling

Key analysis capabilities:
- Technical analysis with multiple indicators (RSI, MACD, moving averages)
- Risk assessment (Sharpe ratio, VaR, volatility analysis)
- Fundamental analysis (P/E ratios, growth metrics, sector analysis)
- Market regime detection and stress testing
- Ensemble prediction models with confidence scoring
- Horizon-specific forecasting (short, medium, long-term)
- Data-driven investment recommendations
- Suitability scoring based on user preferences

Assessment components:
- Investment recommendation (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL)
- Risk assessment (LOW, MODERATE, HIGH with detailed factors)
- Confidence scoring (model agreement, signal consistency, data quality)
- Suitability scoring (alignment with user preferences)
- Detailed insights (technical, fundamental, risk, market, investment)

Analysis parameters are dynamically adjusted based on:
- User's risk tolerance (conservative, moderate, aggressive)
- Investment horizon (short-term, medium-term, long-term)
- Market conditions and volatility expectations
- Sector-specific risk factors
- Capital amount and investment goals

Always provide analysis that aligns with the user's investment goals and risk profile while maintaining analytical rigor and accuracy. Generate assessments that can be directly used by downstream agents for product creation and portfolio construction.
"""

ANALYZER_INPUT_TEMPLATE = """Stock Analysis Request:
Symbol: {symbol}
Investment Horizon: {investment_horizon}
Risk Tolerance: {risk_tolerance}
Analysis Date: {analysis_date}

User Preferences:
- Capital Amount: ${capital_amount:,.2f}
- Sector Focus: {sector}
- Market Cap Range: {market_cap_range}
- Investment Strategy: {strategy_focus}

MCP Analysis Parameters:
- Prediction Horizon: {horizon_days} days
- Volatility Threshold: {volatility_threshold}
- Confidence Threshold: {confidence_threshold}
- Risk Aversion Parameter: {risk_aversion}

Please perform comprehensive analysis including:
1. Technical signals and indicators
2. Risk metrics and volatility analysis
3. Fundamental metrics and sector analysis
4. Market regime and stress testing
5. Ensemble predictions with confidence scores
6. Horizon-specific forecasts
7. Data-based investment recommendation
8. Risk assessment with detailed factors
9. Confidence scoring based on model agreement
10. Suitability analysis for user preferences

Return structured analysis results with comprehensive assessments suitable for product bundling and portfolio construction.
"""

ANALYZER_MCP_PROMPT = """Analyze the following stock using MCP server with user-specific parameters and generate comprehensive assessment:

Stock: {symbol}
User Risk Tolerance: {risk_tolerance}
Investment Horizon: {investment_horizon}
Capital Amount: ${capital_amount:,.2f}

MCP Function: stock_predictions_daily_analysis
Parameters:
- Symbol: {symbol}
- Short-term window: 30 days
- Prediction horizon: {horizon_days} days
- Model: chronos
- Volatility threshold: {volatility_threshold}
- Risk aversion: {risk_aversion}
- Confidence threshold: {confidence_threshold}

Expected Analysis Output:
1. Technical Signals (RSI, MACD, overall signals)
2. Risk Metrics (Sharpe ratio, VaR, volatility)
3. Fundamental Metrics (P/E, market cap, dividend yield)
4. Sector Analysis (sector performance, industry trends)
5. Market Regime (bull/bear, stress indicators)
6. Ensemble Predictions (confidence scores, forecasts)

Assessment Requirements:
- Investment recommendation with strength level
- Risk assessment with detailed factors
- Confidence score based on model agreement
- Suitability score for user preferences
- Detailed insights across technical, fundamental, risk, market, and investment dimensions

Adapt the analysis depth and parameters based on the user's risk tolerance and investment horizon. Ensure all assessments are data-driven and can be used by downstream agents for product creation.
"""

ANALYZER_ASSESSMENT_PROMPT = """Generate a comprehensive data-based assessment for the analyzed stock:

Stock Analysis Data:
{analysis_data}

User Preferences:
{user_preferences}

Assessment Requirements:
1. Investment Recommendation:
   - Determine recommendation level (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL)
   - Calculate recommendation strength (HIGH, MEDIUM, LOW)
   - Provide recommendation score (0-1)
   - Include signal breakdown and technical factors

2. Risk Assessment:
   - Determine risk level (LOW, MODERATE, HIGH)
   - Calculate risk score (0-1, where 1 is highest risk)
   - Identify specific risk factors
   - Include key metrics and market context

3. Confidence Score:
   - Calculate confidence score (0-1)
   - Determine confidence level (HIGH, MEDIUM, LOW)
   - Include factors: ensemble score, model agreement, signal consistency, data quality

4. Suitability Score:
   - Calculate suitability score (0-1)
   - Determine suitability level (EXCELLENT, GOOD, FAIR, POOR)
   - Consider alignment with user preferences
   - Include risk suitability, recommendation suitability, confidence suitability

5. Detailed Insights:
   - Technical insights (momentum, indicators, patterns)
   - Fundamental insights (valuation, growth, financial health)
   - Risk insights (volatility, drawdown, stress factors)
   - Market insights (regime, sector trends, macro factors)
   - Investment insights (opportunities, risks, recommendations)

Provide a structured assessment that can be directly used by product bundling and portfolio construction agents.
"""

ANALYZER_EXAMPLES = [
    {
        "symbol": "AAPL",
        "user_preferences": {
            "risk_tolerance": "conservative",
            "investment_horizon": "long",
            "capital_amount": 50000.0
        },
        "analysis_result": {
            "signals": {
                "overall": "BUY",
                "rsi": "NEUTRAL",
                "macd": "BUY",
                "confidence": 0.85
            },
            "risk": {
                "sharpe_ratio": 1.8,
                "volatility": 0.12,
                "var_95": 0.02,
                "max_drawdown": 0.15
            },
            "metrics": {
                "market_cap": 2500000000000,
                "pe_ratio": 25.5,
                "dividend_yield": 0.02,
                "beta": 1.1
            },
            "sector": {
                "sector": "Technology",
                "sector_performance": 0.08,
                "industry_trend": "POSITIVE"
            },
            "ensemble": {
                "prediction_horizon": 180,
                "expected_return": 0.12,
                "confidence": 0.82
            }
        },
        "assessment": {
            "investment_recommendation": {
                "recommendation": "BUY",
                "strength": "MEDIUM",
                "score": 0.72,
                "signal_breakdown": {
                    "overall_signal": "BUY",
                    "rsi_signal": "NEUTRAL",
                    "macd_signal": "BUY",
                    "signal_score": 0.7
                },
                "technical_factors": {
                    "sharpe_ratio": 1.8,
                    "ensemble_score": 0.82,
                    "momentum_score": 0.65,
                    "quality_score": 0.75,
                    "model_agreement": 0.8
                }
            },
            "risk_assessment": {
                "risk_level": "LOW",
                "risk_score": 0.25,
                "risk_factors": ["LOW_VOLATILITY", "LOW_VAR", "HIGH_SHARPE"],
                "key_metrics": {
                    "sharpe_ratio": 1.8,
                    "var_95": 0.02,
                    "volatility": 0.12,
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
                "confidence_score": 0.78,
                "confidence_level": "HIGH",
                "factors": {
                    "ensemble_score": 0.82,
                    "model_agreement": 0.8,
                    "signal_consistency": 0.67,
                    "momentum_quality": 0.65,
                    "overall_quality": 0.75
                }
            },
            "suitability_score": {
                "suitability_score": 0.85,
                "suitability_level": "EXCELLENT",
                "risk_suitability": 1.0,
                "recommendation_suitability": 0.72,
                "confidence_suitability": 0.78,
                "user_preferences": {
                    "risk_tolerance": "conservative",
                    "investment_horizon": "long",
                    "capital_amount": 50000.0
                }
            },
            "insights": {
                "technical_insights": ["Strong technical indicators suggest upward momentum"],
                "fundamental_insights": ["Large-cap stock with established market presence", "High P/E ratio suggests growth expectations"],
                "risk_insights": ["Excellent risk-adjusted returns", "Low volatility - suitable for conservative investors"],
                "market_insights": ["Currently in bull market regime"],
                "investment_insights": ["High model agreement suggests reliable predictions"]
            }
        }
    },
    {
        "symbol": "TSLA",
        "user_preferences": {
            "risk_tolerance": "aggressive",
            "investment_horizon": "short",
            "capital_amount": 25000.0
        },
        "analysis_result": {
            "signals": {
                "overall": "HOLD",
                "rsi": "OVERBOUGHT",
                "macd": "SELL",
                "confidence": 0.75
            },
            "risk": {
                "sharpe_ratio": 0.6,
                "volatility": 0.35,
                "var_95": 0.08,
                "max_drawdown": 0.45
            },
            "metrics": {
                "market_cap": 800000000000,
                "pe_ratio": 45.2,
                "dividend_yield": 0.0,
                "beta": 1.8
            },
            "sector": {
                "sector": "Consumer Discretionary",
                "sector_performance": 0.05,
                "industry_trend": "VOLATILE"
            },
            "ensemble": {
                "prediction_horizon": 30,
                "expected_return": 0.05,
                "confidence": 0.65
            }
        },
        "assessment": {
            "investment_recommendation": {
                "recommendation": "HOLD",
                "strength": "MEDIUM",
                "score": 0.45,
                "signal_breakdown": {
                    "overall_signal": "HOLD",
                    "rsi_signal": "OVERBOUGHT",
                    "macd_signal": "SELL",
                    "signal_score": 0.3
                },
                "technical_factors": {
                    "sharpe_ratio": 0.6,
                    "ensemble_score": 0.65,
                    "momentum_score": 0.4,
                    "quality_score": 0.6,
                    "model_agreement": 0.7
                }
            },
            "risk_assessment": {
                "risk_level": "HIGH",
                "risk_score": 0.75,
                "risk_factors": ["HIGH_VOLATILITY", "HIGH_VAR", "LOW_SHARPE"],
                "key_metrics": {
                    "sharpe_ratio": 0.6,
                    "var_95": 0.08,
                    "volatility": 0.35,
                    "max_drawdown": 0.45,
                    "stress_score": 0.7
                },
                "market_context": {
                    "current_regime": "NEUTRAL",
                    "regime_probability": 0.5,
                    "scenario_analysis": "VOLATILE"
                }
            },
            "confidence_score": {
                "confidence_score": 0.62,
                "confidence_level": "MEDIUM",
                "factors": {
                    "ensemble_score": 0.65,
                    "model_agreement": 0.7,
                    "signal_consistency": 0.33,
                    "momentum_quality": 0.4,
                    "overall_quality": 0.6
                }
            },
            "suitability_score": {
                "suitability_score": 0.68,
                "suitability_level": "GOOD",
                "risk_suitability": 0.8,
                "recommendation_suitability": 0.45,
                "confidence_suitability": 0.62,
                "user_preferences": {
                    "risk_tolerance": "aggressive",
                    "investment_horizon": "short",
                    "capital_amount": 25000.0
                }
            },
            "insights": {
                "technical_insights": ["Technical indicators suggest potential downward pressure"],
                "fundamental_insights": ["Large-cap stock with established market presence", "High P/E ratio suggests growth expectations"],
                "risk_insights": ["Poor risk-adjusted performance", "High volatility - suitable for risk-tolerant investors"],
                "market_insights": ["Currently in neutral market regime"],
                "investment_insights": ["Moderate model agreement - consider additional analysis"]
            }
        }
    }
] 