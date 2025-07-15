"""
System prompts and input templates for the Query Processor Agent.
"""

QUERY_PROCESSOR_SYSTEM_PROMPT = """You are an expert financial query processor specializing in extracting structured investment criteria from natural language user queries.

Your role is to:
1. Parse natural language investment requests
2. Extract specific investment parameters and preferences
3. Structure the data for downstream financial analysis agents
4. Ensure all user preferences are captured accurately

Key extraction areas:
- Investment amount and capital allocation
- Risk tolerance (conservative, moderate, aggressive)
- Investment horizon (short-term, medium-term, long-term)
- Sector and industry preferences
- Market cap preferences (small, mid, large)
- Geographic and market preferences
- ESG and sustainability focus
- Dividend vs growth focus
- Number of stocks desired
- Specific investment themes or strategies

Always maintain the user's original intent while providing structured, actionable data for the stock selection and analysis pipeline.
"""

QUERY_PROCESSOR_INPUT_TEMPLATE = """User Query: {user_query}

Please extract and structure the following information:

1. Investment Parameters:
   - Capital Amount: [extract dollar amount or investment size]
   - Number of Stocks: [extract desired number of stocks, default 10]
   - Investment Horizon: [short/medium/long term]

2. Risk Profile:
   - Risk Tolerance: [conservative/moderate/aggressive]
   - Market Cap Preference: [small/mid/large cap]

3. Investment Focus:
   - Sector: [technology, healthcare, finance, etc.]
   - Industry: [specific industry if mentioned]
   - Geographic Focus: [US, international, specific countries]
   - Market: [NASDAQ, NYSE, specific exchanges]

4. Investment Strategy:
   - ESG Focus: [true/false]
   - Dividend Focus: [true/false]
   - Growth Focus: [true/false]
   - Value Focus: [true/false]

5. Additional Preferences:
   - Specific themes or strategies mentioned
   - Any constraints or exclusions
   - Special requirements or preferences

Return the structured data in a format that can be directly used by downstream agents for stock discovery and analysis.
"""

QUERY_PROCESSOR_EXAMPLES = [
    {
        "user_query": "I want a conservative portfolio of 8 large-cap technology stocks with dividend focus for retirement planning with $50,000 investment over 6 months",
        "extracted_data": {
            "capital_amount": 50000.0,
            "limit": 8,
            "risk_tolerance": "conservative",
            "market_cap_range": "large",
            "sector": "technology",
            "dividend_focus": True,
            "investment_horizon": "medium",
            "esg_focus": False,
            "growth_focus": False,
            "value_focus": False
        }
    },
    {
        "user_query": "I need 15 aggressive growth stocks in healthcare and biotech for short-term trading with $25,000",
        "extracted_data": {
            "capital_amount": 25000.0,
            "limit": 15,
            "risk_tolerance": "aggressive",
            "market_cap_range": None,
            "sector": "healthcare",
            "industry": "biotech",
            "dividend_focus": False,
            "investment_horizon": "short",
            "esg_focus": False,
            "growth_focus": True,
            "value_focus": False
        }
    },
    {
        "user_query": "Show me 10 ESG-friendly mid-cap stocks from Europe for long-term sustainable investing with $75,000",
        "extracted_data": {
            "capital_amount": 75000.0,
            "limit": 10,
            "risk_tolerance": "moderate",
            "market_cap_range": "mid",
            "sector": None,
            "country": "Europe",
            "dividend_focus": False,
            "investment_horizon": "long",
            "esg_focus": True,
            "growth_focus": False,
            "value_focus": False
        }
    }
] 