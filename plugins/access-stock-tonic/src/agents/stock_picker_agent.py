"""
Stock Picker Agent - Discovers stocks using yfinance and returns a list of tickers and company names.
"""

import logging
from typing import List, Dict, Any, Optional
from ..tools.yfinance_tool import YFinanceWrapper
from langchain.prompts import ChatPromptTemplate


from ..prompts.stock_picker_prompts import (
    STOCK_PICKER_SYSTEM_PROMPT,
    STOCK_PICKER_DISCOVERY_PROMPT,
    STOCK_PICKER_EXAMPLES
)

from .gassist_llm import GAssistLLM

class StockPickerAgent:
    """
    Stock Picker Agent that discovers stocks using yfinance and returns a list of tickers and company names.
    """
    def __init__(self, llm=None, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.yf = YFinanceWrapper()
        self.llm = llm or GAssistLLM()
        # Remove all cloud LLM logic and API key handling
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", STOCK_PICKER_SYSTEM_PROMPT),
            ("human", STOCK_PICKER_DISCOVERY_PROMPT)
        ])

    def pick_stocks(self, user_query: str, limit: Optional[int] = None, 
                   processed_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Discover stocks based on user query and return a list of tickers and company names.
        Args:
            user_query: User's input string describing desired stocks (sector, market, esg, etc.)
            limit: Maximum number of stocks to return (from processed_query if not provided)
            processed_query: Structured query data from query processor
        Returns:
            List of dicts: [{ 'symbol': str, 'company_name': str, ... }]
        """
        # Use processed query data if available, otherwise extract from string
        if processed_query:
            criteria = self._extract_criteria_from_processed_query(processed_query)
        else:
            criteria = self._extract_criteria_from_query(user_query)
        
        # Use limit from processed query if available
        if limit is None and processed_query:
            limit = processed_query.get('limit', 10)
        elif limit is None:
            limit = 10
            
        criteria['limit'] = limit
        
        # Use LLM for enhanced discovery if available
        if processed_query:
            enhanced_criteria = self._enhance_criteria_with_llm(criteria, processed_query)
            criteria.update(enhanced_criteria)
        
        # Let the yfinance tool handle all discovery logic
        stocks = self.yf.discover_stocks(criteria)
        
        # Return only essential information for downstream processing
        return [
            {
                'symbol': s['symbol'],
                'company_name': s['company_name'],
                'sector': s.get('sector', ''),
                'market_cap': s.get('market_cap', 0)
            }
            for s in stocks
        ]

    def _enhance_criteria_with_llm(self, criteria: Dict[str, Any], processed_query: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance discovery criteria using LLM insights."""
        try:
            # Create prompt with user preferences
            prompt = STOCK_PICKER_DISCOVERY_PROMPT.format(
                risk_tolerance=processed_query.get('risk_tolerance', 'moderate'),
                investment_horizon=processed_query.get('investment_horizon', 'long'),
                capital_amount=processed_query.get('capital_amount', 100000.0),
                limit=processed_query.get('limit', 10),
                sector=processed_query.get('sector', ''),
                market_cap_range=processed_query.get('market_cap_range', ''),
                country=processed_query.get('country', ''),
                market=processed_query.get('market', ''),
                esg_focus=processed_query.get('esg_focus', False),
                dividend_focus=processed_query.get('dividend_focus', False),
                growth_focus=processed_query.get('growth_focus', False),
                value_focus=processed_query.get('value_focus', False)
            )
            
            response = self.llm.invoke(prompt)
            
            # Extract additional criteria from LLM response
            # This could include specific metrics, ratios, or screening criteria
            enhanced_criteria = {}
            
            # Parse LLM response for additional criteria
            content = response.content.lower()
            
            # Extract P/E ratio preferences
            if 'low pe' in content or 'value' in content:
                enhanced_criteria['pe_ratio_max'] = 15.0
            elif 'high pe' in content or 'growth' in content:
                enhanced_criteria['pe_ratio_min'] = 20.0
            
            # Extract dividend yield preferences
            if 'dividend' in content and 'high' in content:
                enhanced_criteria['dividend_yield_min'] = 3.0
            elif 'dividend' in content and 'low' in content:
                enhanced_criteria['dividend_yield_max'] = 1.0
            
            # Extract volatility preferences
            if 'low volatility' in content or 'stable' in content:
                enhanced_criteria['volatility_max'] = 0.20
            elif 'high volatility' in content or 'aggressive' in content:
                enhanced_criteria['volatility_min'] = 0.30
            
            return enhanced_criteria
            
        except Exception as e:
            self.logger.error(f"Error enhancing criteria with LLM: {e}")
            return {}

    def _extract_criteria_from_processed_query(self, processed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract discovery criteria from processed query data.
        Uses structured data from query processor instead of parsing strings.
        """
        criteria = {}
        
        # Extract sector
        if processed_query.get('sector'):
            criteria['sector'] = processed_query['sector']
        
        # Extract industry
        if processed_query.get('industry'):
            criteria['industry'] = processed_query['industry']
        
        # Extract market cap preferences
        market_cap_range = processed_query.get('market_cap_range')
        if market_cap_range:
            if market_cap_range == 'large':
                criteria['market_cap_min'] = 10.0
            elif market_cap_range == 'mid':
                criteria['market_cap_min'] = 2.0
                criteria['market_cap_max'] = 10.0
            elif market_cap_range == 'small':
                criteria['market_cap_max'] = 2.0
        
        # Extract market/exchange preferences
        if processed_query.get('market'):
            criteria['market'] = processed_query['market']
        
        # Extract country
        if processed_query.get('country'):
            criteria['country'] = processed_query['country']
        
        # Extract focus areas
        if processed_query.get('value_focus'):
            criteria['pe_ratio_max'] = 15.0
        
        if processed_query.get('dividend_focus'):
            criteria['dividend_yield_min'] = 2.0
        
        if processed_query.get('esg_focus'):
            criteria['esg'] = True
        
        if processed_query.get('growth_focus'):
            criteria['growth_focus'] = True
            
        return criteria

    def _extract_criteria_from_query(self, query: str) -> Dict[str, Any]:
        """
        Extract discovery criteria from user query string (fallback method).
        Returns criteria dict that will be passed to yfinance tool for dynamic discovery.
        """
        criteria = {}
        q = query.lower()
        
        # Extract sector if mentioned
        sectors = [
            "technology", "healthcare", "finance", "consumer", "energy", 
            "industrial", "materials", "real_estate", "utilities", "communication"
        ]
        for sector in sectors:
            if sector in q:
                criteria['sector'] = sector
                break
        
        # Extract market cap preferences
        if "large cap" in q or "large-cap" in q:
            criteria['market_cap_min'] = 10.0
        elif "mid cap" in q or "mid-cap" in q:
            criteria['market_cap_min'] = 2.0
            criteria['market_cap_max'] = 10.0
        elif "small cap" in q or "small-cap" in q:
            criteria['market_cap_max'] = 2.0
        
        # Extract market/exchange preferences
        if "nasdaq" in q:
            criteria['market'] = "NASDAQ"
        elif "nyse" in q:
            criteria['market'] = "NYSE"
        elif "us" in q or "united states" in q:
            criteria['country'] = "US"
        
        # Extract P/E ratio preferences
        if "low pe" in q or "value" in q:
            criteria['pe_ratio_max'] = 15.0
        
        # Extract dividend yield preferences
        if "dividend" in q or "income" in q:
            criteria['dividend_yield_min'] = 2.0
        
        # Extract ESG preferences
        if "esg" in q or "sustainab" in q or "green" in q:
            criteria['esg'] = True
            
        return criteria 