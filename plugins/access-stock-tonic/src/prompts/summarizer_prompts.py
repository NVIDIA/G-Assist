"""
Prompt templates for the Summarizer Agent using LangChain.
"""

# Stock-level summary prompt
STOCK_SUMMARY_PROMPT = """
You are a professional financial analyst. Generate a comprehensive, professional summary for the stock {symbol} based on the following assessment data:

## Assessment Data:
- **Investment Recommendation**: {recommendation} (Strength: {recommendation_strength}, Score: {recommendation_score:.1%})
- **Risk Assessment**: {risk_level} (Score: {risk_score:.1%})
- **Confidence Level**: {confidence_level} (Score: {confidence_score:.1%})
- **Suitability**: {suitability_level} (Score: {suitability_score:.1%})

## Price Data:
{price_analysis_section}

## Original Text Assessment:
{text_assessment}

## Key Insights:
{insights}

## Instructions:
1. Create a professional, concise summary (2-3 paragraphs)
2. Focus on the investment recommendation and rationale
3. Highlight key risk factors and opportunities
4. Include confidence level and suitability assessment
5. Incorporate price analysis and expected price movement (if available)
6. Use clear, professional language suitable for investment professionals
7. Maintain objectivity and balance
8. Include specific metrics and data points where relevant

## Output Format:
Provide a well-structured summary that includes:
- Executive summary of the investment opportunity
- Price analysis and expected movement (if data available)
- Key investment thesis and rationale
- Risk assessment and considerations
- Confidence and suitability assessment
- Investment recommendation and next steps

Please generate a professional summary that would be suitable for inclusion in an investment report or portfolio analysis.
"""

# Portfolio-level summary prompt
PORTFOLIO_SUMMARY_PROMPT = """
You are a senior portfolio manager and investment advisor. Generate a comprehensive portfolio summary based on the following data:

## Portfolio Overview:
- **Total Stocks**: {total_stocks}
- **Product Type**: {product_type}
- **Investment Amount**: ${notional_amount:,.2f}
- **User Preferences**: {user_preferences}

## Assessment Summary:
- **Average Confidence**: {avg_confidence:.1%}
- **Average Suitability**: {avg_suitability:.1%}
- **Average Recommendation Score**: {avg_recommendation:.1%}

## Risk Distribution:
{risk_distribution}

## Recommendation Distribution:
{recommendation_distribution}

## Original Product Summary:
{product_summary}

## Individual Stock Assessments:
{individual_assessments}

## Instructions:
1. Create a comprehensive portfolio summary (3-4 paragraphs)
2. Analyze the overall portfolio characteristics and risk profile
3. Evaluate the alignment with user preferences
4. Assess the quality and diversity of recommendations
5. Provide portfolio-level insights and observations
6. Include specific metrics and data points
7. Use professional investment language

## Output Format:
Provide a structured summary that includes:
- Portfolio overview and characteristics
- Risk and return profile analysis
- Alignment with investment objectives
- Quality assessment of individual components
- Overall portfolio recommendation
- Key strengths and considerations

Please generate a professional portfolio summary suitable for investment decision-making and client communication.
"""

# Executive summary prompt
EXECUTIVE_SUMMARY_PROMPT = """
You are a Chief Investment Officer. Generate an executive summary for this investment portfolio:

## Portfolio Metrics:
- **Product Type**: {product_type}
- **Total Components**: {total_components}
- **Investment Amount**: ${capital_amount:,.2f}
- **Target Investor**: {risk_tolerance} risk tolerance, {investment_horizon}-term horizon

## Key Performance Indicators:
- **Portfolio Confidence**: {avg_confidence:.1%}
- **Investor Suitability**: {avg_suitability:.1%}
- **Investment Recommendation**: {avg_recommendation:.1%}

## Risk Profile:
{risk_distribution}

## Investment Recommendations:
{recommendation_distribution}

## Instructions:
1. Create a concise executive summary (1-2 paragraphs)
2. Focus on high-level investment thesis and key metrics
3. Highlight portfolio strengths and risk management
4. Provide clear investment recommendation
5. Use executive-level language and insights
6. Emphasize strategic value and alignment with objectives

## Output Format:
Provide an executive summary that includes:
- Investment opportunity overview
- Key performance metrics
- Risk-reward assessment
- Strategic recommendation
- Next steps or considerations

Please generate an executive summary suitable for senior management and investment committee review.
"""

# Risk summary prompt
RISK_SUMMARY_PROMPT = """
You are a risk management specialist. Generate a comprehensive risk analysis for this investment portfolio:

## Portfolio Risk Profile:
- **Total Stocks**: {total_stocks}
- **Risk Tolerance**: {risk_tolerance}
- **Risk Distribution**: {risk_distribution}

## Individual Stock Risk Assessments:
{individual_assessments}

## Instructions:
1. Create a detailed risk analysis (2-3 paragraphs)
2. Assess portfolio-level risk characteristics
3. Evaluate risk alignment with investor profile
4. Identify key risk factors and concentrations
5. Provide risk management recommendations
6. Use professional risk management language
7. Include specific risk metrics and observations

## Output Format:
Provide a risk analysis that includes:
- Overall risk profile assessment
- Risk distribution analysis
- Concentration and diversification analysis
- Risk tolerance alignment
- Risk management recommendations
- Key risk factors and considerations

Please generate a professional risk analysis suitable for risk management and compliance review.
"""

# Recommendation summary prompt
RECOMMENDATION_SUMMARY_PROMPT = """
You are an investment strategist. Generate a comprehensive recommendation analysis for this investment portfolio:

## Portfolio Recommendations:
- **Total Stocks**: {total_stocks}
- **Average Recommendation Score**: {avg_recommendation:.1%}
- **Recommendation Distribution**: {recommendation_distribution}
- **Target Investor**: {risk_tolerance} risk tolerance, {investment_horizon}-term horizon

## Individual Stock Recommendations:
{individual_assessments}

## Instructions:
1. Create a detailed recommendation analysis (2-3 paragraphs)
2. Assess the quality and consistency of recommendations
3. Evaluate alignment with investment objectives
4. Analyze recommendation strength and conviction
5. Provide strategic investment insights
6. Use professional investment language
7. Include specific recommendation metrics

## Output Format:
Provide a recommendation analysis that includes:
- Overall recommendation quality assessment
- Recommendation distribution analysis
- Investment thesis evaluation
- Strategic positioning analysis
- Investment recommendation
- Key considerations and next steps

Please generate a professional recommendation analysis suitable for investment strategy and portfolio construction.
""" 