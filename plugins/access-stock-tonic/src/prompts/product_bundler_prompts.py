"""
System prompts and input templates for the Product Bundler Agent.
"""

PRODUCT_BUNDLER_SYSTEM_PROMPT = """You are an expert financial product architect specializing in creating structured equity products based on FINOS CDM (Common Domain Model) standards.

Your role is to:
1. Create FINOS CDM-compliant structured equity products
2. Bundle analyzed stocks into investment products
3. Generate comprehensive risk profiles and performance metrics
4. Ensure regulatory compliance and documentation
5. Tailor products to user's specific investment requirements

Key product creation capabilities:
- Equity basket products with dynamic weighting
- Risk-adjusted portfolio construction
- Performance optimization based on user preferences
- Regulatory compliance (RETAIL, INSTITUTIONAL)
- Tax-efficient product structures
- Comprehensive documentation and disclosures

Product parameters are dynamically set based on:
- User's capital amount and investment horizon
- Risk tolerance and investment strategy
- Sector and market cap preferences
- ESG and sustainability requirements
- Dividend vs growth focus

Always create products that align with the user's investment goals while maintaining FINOS CDM compliance and regulatory standards.
"""

PRODUCT_BUNDLER_INPUT_TEMPLATE = """Product Creation Request:
Analysis Results: {analysis_results_count} stocks analyzed
User Capital: ${capital_amount:,.2f}
Investment Horizon: {investment_horizon}
Risk Tolerance: {risk_tolerance}

User Preferences:
- Sector Focus: {sector}
- Market Cap Range: {market_cap_range}
- Geographic Focus: {country}
- Investment Strategy: {strategy_focus}

Product Requirements:
- Target Component Count: {target_count}
- Minimum Component Count: {min_count}
- Notional Amount: ${notional_amount:,.2f}
- Maturity Period: {maturity_days} days
- Currency: {currency}

Please create a FINOS CDM-compliant structured equity product including:
1. Product structure and components
2. Risk profile and performance metrics
3. Regulatory classification and compliance
4. Documentation and disclosures
5. Component weighting and selection rationale

Ensure the product meets the user's investment objectives and regulatory requirements.
"""

PRODUCT_BUNDLER_CDM_PROMPT = """Create a FINOS CDM-compliant structured equity product:

Product Specifications:
- Product Type: EQUITY_BASKET
- Notional Amount: ${notional_amount:,.2f}
- Currency: {currency}
- Maturity Date: {maturity_date}
- Regulatory Classification: {regulatory_class}

User Profile:
- Risk Tolerance: {risk_tolerance}
- Investment Horizon: {investment_horizon}
- Capital Amount: ${capital_amount:,.2f}
- Investment Strategy: {strategy_focus}

Available Components:
{component_list}

CDM Requirements:
1. Product Structure (CDMProductStructure)
   - Product ID, type, name, issuer
   - Issue date, maturity date, currency
   - Notional amount, components list

2. Component Details (CDMComponent)
   - Component ID, asset type, underlying asset
   - Weight, quantity, price, market value

3. Risk Profile
   - Portfolio-level risk metrics
   - Sector concentration analysis
   - Volatility and correlation measures

4. Performance Metrics
   - Expected returns and Sharpe ratios
   - Sector and factor exposures
   - Stress testing results

5. Regulatory Compliance
   - FINOS CDM 6.0.0 compliance
   - Legal agreements and documentation
   - Tax status and reporting requirements

Create a comprehensive, compliant product structure that optimizes for the user's investment objectives.
"""

PRODUCT_BUNDLER_EXAMPLES = [
    {
        "user_preferences": {
            "risk_tolerance": "conservative",
            "capital_amount": 50000.0,
            "investment_horizon": "long",
            "sector": "technology",
            "dividend_focus": True
        },
        "product_structure": {
            "product_id": "EQ_BASKET_20241201_143022",
            "product_type": "CONSERVATIVE_EQUITY_BASKET",
            "product_name": "Conservative Technology Dividend Basket",
            "issuer": "STRUCTURED_EQUITIES_PLATFORM",
            "notional_amount": 50000.0,
            "maturity_date": "2025-12-01T14:30:22",
            "currency": "USD",
            "components": [
                {
                    "component_id": "COMP_AAPL_0",
                    "asset_type": "EQUITY",
                    "underlying_asset": "AAPL",
                    "weight": 0.25,
                    "retention_reason": "Large-cap tech with consistent dividend growth"
                },
                {
                    "component_id": "COMP_MSFT_1",
                    "asset_type": "EQUITY",
                    "underlying_asset": "MSFT",
                    "weight": 0.20,
                    "retention_reason": "Stable large-cap with strong fundamentals"
                }
            ],
            "risk_profile": {
                "portfolio_volatility": 0.15,
                "sharpe_ratio": 1.2,
                "max_drawdown": 0.12,
                "sector_concentration": 0.45
            },
            "performance_metrics": {
                "expected_return": 0.10,
                "dividend_yield": 0.018,
                "beta": 0.95
            }
        }
    },
    {
        "user_preferences": {
            "risk_tolerance": "aggressive",
            "capital_amount": 25000.0,
            "investment_horizon": "short",
            "sector": "healthcare",
            "growth_focus": True
        },
        "product_structure": {
            "product_id": "EQ_BASKET_20241201_143045",
            "product_type": "AGGRESSIVE_EQUITY_BASKET",
            "product_name": "Aggressive Healthcare Growth Basket",
            "issuer": "STRUCTURED_EQUITIES_PLATFORM",
            "notional_amount": 25000.0,
            "maturity_date": "2024-06-01T14:30:45",
            "currency": "USD",
            "components": [
                {
                    "component_id": "COMP_CRSP_0",
                    "asset_type": "EQUITY",
                    "underlying_asset": "CRSP",
                    "weight": 0.15,
                    "retention_reason": "High-growth biotech with innovative technology"
                }
            ],
            "risk_profile": {
                "portfolio_volatility": 0.35,
                "sharpe_ratio": 0.8,
                "max_drawdown": 0.25,
                "sector_concentration": 0.60
            },
            "performance_metrics": {
                "expected_return": 0.20,
                "growth_rate": 0.25,
                "beta": 1.4
            }
        }
    }
] 