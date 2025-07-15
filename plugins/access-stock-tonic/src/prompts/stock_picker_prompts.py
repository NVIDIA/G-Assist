"""
System prompts and input templates for the Stock Picker Agent.
"""

STOCK_PICKER_SYSTEM_PROMPT = """You are an expert stock discovery agent specializing in finding stocks that match specific investment criteria using comprehensive market data.

Your role is to:
1. Use structured investment criteria to discover relevant stocks
2. Leverage yfinance data for comprehensive market screening
3. Apply user preferences for sector, market cap, geography, and other filters
4. Return a curated list of stocks that match the user's requirements
5. Ensure diversity and quality in the selected stocks

Key discovery capabilities:
- Sector and industry-based filtering
- Market capitalization screening (small, mid, large cap)
- Geographic and exchange-based filtering
- ESG and sustainability screening
- Dividend yield and growth metrics
- Risk-adjusted return considerations
- Market liquidity and trading volume
- Fundamental analysis metrics

Always prioritize stocks that best match the user's stated preferences while maintaining portfolio diversification and risk management principles.
"""

STOCK_PICKER_INPUT_TEMPLATE = """Investment Criteria:
{processed_query_data}

Discovery Parameters:
- Target Number of Stocks: {limit}
- Sector Focus: {sector}
- Market Cap Range: {market_cap_range}
- Geographic Focus: {country}
- Market/Exchange: {market}
- Risk Tolerance: {risk_tolerance}
- Investment Strategy: {strategy_focus}

Additional Filters:
- ESG Focus: {esg_focus}
- Dividend Focus: {dividend_focus}
- Growth Focus: {growth_focus}
- Value Focus: {value_focus}

Please discover stocks that match these criteria using yfinance data and return:
1. Stock symbols and company names
2. Sector and industry classification
3. Market capitalization
4. Key metrics relevant to the user's preferences
5. Brief rationale for selection

Ensure the discovered stocks align with the user's investment goals and risk profile.
"""

STOCK_PICKER_DISCOVERY_PROMPT = """Based on the following investment criteria, discover and return relevant stocks:

User Preferences:
- Risk Tolerance: {risk_tolerance}
- Investment Horizon: {investment_horizon}
- Capital Amount: ${capital_amount:,.2f}
- Number of Stocks: {limit}
- Sector: {sector}
- Market Cap: {market_cap_range}
- Geographic Focus: {country}
- Market: {market}

Investment Focus:
- ESG: {esg_focus}
- Dividend: {dividend_focus}
- Growth: {growth_focus}
- Value: {value_focus}

Please use yfinance to discover stocks that match these criteria and return a structured list with:
- Symbol and company name
- Sector and industry
- Market capitalization
- Key metrics (P/E, dividend yield, etc.)
- Selection rationale

Focus on quality stocks that align with the user's investment strategy and risk profile.
"""

STOCK_PICKER_EXAMPLES = [
    {
        "criteria": {
            "risk_tolerance": "conservative",
            "limit": 8,
            "sector": "technology",
            "market_cap_range": "large",
            "dividend_focus": True
        },
        "discovered_stocks": [
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "market_cap": 2500000000000,
                "dividend_yield": 0.02,
                "selection_reason": "Large-cap tech with consistent dividend growth"
            },
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corporation",
                "sector": "Technology",
                "market_cap": 2200000000000,
                "dividend_yield": 0.015,
                "selection_reason": "Stable large-cap with strong fundamentals"
            }
        ]
    },
    {
        "criteria": {
            "risk_tolerance": "aggressive",
            "limit": 15,
            "sector": "healthcare",
            "market_cap_range": "small",
            "growth_focus": True
        },
        "discovered_stocks": [
            {
                "symbol": "CRSP",
                "company_name": "CRISPR Therapeutics AG",
                "sector": "Healthcare",
                "market_cap": 5000000000,
                "selection_reason": "High-growth biotech with innovative gene editing technology"
            }
        ]
    }
] 