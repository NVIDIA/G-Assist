"""
Query Processor Agent - Processes natural language user queries and structures them for the stock picker agent.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_community.chat_models import ChatHuggingFace
    from langchain.prompts import ChatPromptTemplate
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

from ..prompts.query_processor_prompts import (
    QUERY_PROCESSOR_SYSTEM_PROMPT, 
    QUERY_PROCESSOR_INPUT_TEMPLATE,
    QUERY_PROCESSOR_EXAMPLES
)

@dataclass
class ProcessedQuery:
    """Structured representation of a processed user query."""
    original_query: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    country: Optional[str] = None
    market_cap_range: Optional[str] = None  # "small", "mid", "large"
    risk_tolerance: Optional[str] = None  # "conservative", "moderate", "aggressive"
    investment_horizon: Optional[str] = None  # "short", "medium", "long"
    capital_amount: Optional[float] = None
    esg_focus: bool = False
    dividend_focus: bool = False
    growth_focus: bool = False
    value_focus: bool = False
    limit: int = 10

class QueryProcessorAgent:
    """
    Query Processor Agent that takes natural language user queries and structures them
    optimally for the stock picker agent.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, use_llm: bool = False, llm_provider: str = "openai", 
                 anthropic_api_key: Optional[str] = None, hf_api_key: Optional[str] = None,
                 openai_model: str = "gpt-4", anthropic_model: str = "claude-3-opus-20240229", 
                 hf_model: str = "HuggingFaceH4/zephyr-7b-beta"):
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
                        self.logger.warning("Anthropic client version issue detected, falling back to rule-based processing")
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
            
            if self.use_llm:
                self.prompt_template = ChatPromptTemplate.from_messages([
                    ("system", QUERY_PROCESSOR_SYSTEM_PROMPT),
                    ("human", QUERY_PROCESSOR_INPUT_TEMPLATE)
                ])
        
        # Fallback to rule-based extraction
        self.sector_keywords = self._load_sector_keywords()
        self.industry_keywords = self._load_industry_keywords()
        self.market_keywords = self._load_market_keywords()
        self.country_keywords = self._load_country_keywords()
    
    def process_query(self, user_query: str) -> ProcessedQuery:
        """
        Process a natural language user query and return a structured representation.
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            ProcessedQuery object with structured information
        """
        if self.use_llm:
            return self._process_query_with_llm(user_query)
        else:
            return self._process_query_rule_based(user_query)
    
    def _process_query_with_llm(self, user_query: str) -> ProcessedQuery:
        """Process query using LLM for better extraction."""
        try:
            # Create prompt with examples
            examples_text = "\n".join([
                f"Example {i+1}:\nQuery: {ex['user_query']}\nExtracted: {json.dumps(ex['extracted_data'], indent=2)}"
                for i, ex in enumerate(QUERY_PROCESSOR_EXAMPLES)
            ])
            
            prompt = f"""
{QUERY_PROCESSOR_SYSTEM_PROMPT}

Examples:
{examples_text}

{QUERY_PROCESSOR_INPUT_TEMPLATE.format(user_query=user_query)}

Please extract the structured data and return it as a JSON object with the following fields:
- capital_amount (float or null)
- limit (int, default 10)
- risk_tolerance (string: conservative/moderate/aggressive or null)
- market_cap_range (string: small/mid/large or null)
- sector (string or null)
- industry (string or null)
- country (string or null)
- market (string or null)
- investment_horizon (string: short/medium/long or null)
- esg_focus (boolean)
- dividend_focus (boolean)
- growth_focus (boolean)
- value_focus (boolean)
"""
            
            response = self.llm.invoke(prompt)
            content = response.content
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group())
                
                return ProcessedQuery(
                    original_query=user_query,
                    sector=extracted_data.get('sector'),
                    industry=extracted_data.get('industry'),
                    market=extracted_data.get('market'),
                    country=extracted_data.get('country'),
                    market_cap_range=extracted_data.get('market_cap_range'),
                    risk_tolerance=extracted_data.get('risk_tolerance'),
                    investment_horizon=extracted_data.get('investment_horizon'),
                    capital_amount=extracted_data.get('capital_amount'),
                    esg_focus=extracted_data.get('esg_focus', False),
                    dividend_focus=extracted_data.get('dividend_focus', False),
                    growth_focus=extracted_data.get('growth_focus', False),
                    value_focus=extracted_data.get('value_focus', False),
                    limit=extracted_data.get('limit', 10)
                )
            else:
                self.logger.warning("Could not extract JSON from LLM response, falling back to rule-based")
                return self._process_query_rule_based(user_query)
                
        except Exception as e:
            self.logger.error(f"Error in LLM processing: {e}, falling back to rule-based")
            return self._process_query_rule_based(user_query)
    
    def _process_query_rule_based(self, user_query: str) -> ProcessedQuery:
        """Process query using rule-based extraction (original method)."""
        query = user_query.lower().strip()
        
        return ProcessedQuery(
            original_query=user_query,
            sector=self._extract_sector(query),
            industry=self._extract_industry(query),
            market=self._extract_market(query),
            country=self._extract_country(query),
            market_cap_range=self._extract_market_cap_range(query),
            risk_tolerance=self._extract_risk_tolerance(query),
            investment_horizon=self._extract_investment_horizon(query),
            capital_amount=self._extract_capital_amount(query),
            esg_focus=self._extract_esg_focus(query),
            dividend_focus=self._extract_dividend_focus(query),
            growth_focus=self._extract_growth_focus(query),
            value_focus=self._extract_value_focus(query),
            limit=self._extract_limit(query)
        )
    
    def to_stock_picker_query(self, processed_query: ProcessedQuery) -> str:
        """
        Convert a processed query back to a string optimized for the stock picker agent.
        
        Args:
            processed_query: ProcessedQuery object
            
        Returns:
            String query optimized for stock picker
        """
        parts = []
        
        # Add sector
        if processed_query.sector:
            parts.append(processed_query.sector)
        
        # Add market cap
        if processed_query.market_cap_range:
            parts.append(f"{processed_query.market_cap_range} cap")
        
        # Add market/exchange
        if processed_query.market:
            parts.append(processed_query.market)
        
        # Add country
        if processed_query.country:
            parts.append(processed_query.country)
        
        # Add focus areas
        if processed_query.esg_focus:
            parts.append("esg sustainable")
        if processed_query.dividend_focus:
            parts.append("dividend income")
        if processed_query.growth_focus:
            parts.append("growth potential")
        if processed_query.value_focus:
            parts.append("value low pe")
        
        # Add risk tolerance
        if processed_query.risk_tolerance:
            parts.append(processed_query.risk_tolerance)
        
        # Add investment horizon
        if processed_query.investment_horizon:
            parts.append(f"{processed_query.investment_horizon} term")
        
        # If no specific criteria found, add some defaults
        if not parts:
            parts.append("diversified stocks")
        
        return " ".join(parts)
    
    def _load_sector_keywords(self) -> Dict[str, List[str]]:
        """Load sector keywords and their variations."""
        return {
            "technology": ["tech", "technology", "software", "hardware", "ai", "artificial intelligence", "cloud", "cybersecurity"],
            "healthcare": ["health", "healthcare", "medical", "pharmaceutical", "biotech", "biotechnology", "drugs"],
            "finance": ["financial", "finance", "banking", "insurance", "investment", "credit", "lending"],
            "consumer": ["consumer", "retail", "consumer goods", "consumer discretionary", "consumer staples"],
            "energy": ["energy", "oil", "gas", "renewable", "solar", "wind", "fossil fuels"],
            "industrial": ["industrial", "manufacturing", "aerospace", "defense", "machinery"],
            "materials": ["materials", "chemicals", "mining", "metals", "construction materials"],
            "real_estate": ["real estate", "reit", "property", "realty", "commercial real estate"],
            "utilities": ["utilities", "electric", "water", "gas utilities", "power"],
            "communication": ["communication", "telecom", "media", "entertainment", "internet"]
        }
    
    def _load_industry_keywords(self) -> Dict[str, List[str]]:
        """Load industry keywords and their variations."""
        return {
            "semiconductors": ["semiconductor", "chips", "microprocessors", "integrated circuits"],
            "automotive": ["automotive", "cars", "vehicles", "electric vehicles", "ev"],
            "aerospace": ["aerospace", "aviation", "aircraft", "defense"],
            "biotechnology": ["biotech", "biotechnology", "genetics", "genomics"],
            "pharmaceuticals": ["pharma", "pharmaceutical", "drugs", "medicines"],
            "banking": ["bank", "banking", "commercial bank", "investment bank"],
            "insurance": ["insurance", "life insurance", "property insurance"],
            "retail": ["retail", "e-commerce", "online retail", "brick and mortar"],
            "oil_gas": ["oil", "gas", "petroleum", "exploration", "drilling"],
            "renewable_energy": ["renewable", "solar", "wind", "clean energy", "green energy"]
        }
    
    def _load_market_keywords(self) -> Dict[str, List[str]]:
        """Load market/exchange keywords."""
        return {
            "NASDAQ": ["nasdaq", "tech exchange"],
            "NYSE": ["nyse", "new york stock exchange"],
            "US": ["us", "united states", "american", "domestic"],
            "international": ["international", "global", "foreign", "overseas"]
        }
    
    def _load_country_keywords(self) -> Dict[str, List[str]]:
        """Load country keywords."""
        return {
            "US": ["us", "united states", "america", "american"],
            "Canada": ["canada", "canadian"],
            "UK": ["uk", "united kingdom", "britain", "british"],
            "Germany": ["germany", "german"],
            "Japan": ["japan", "japanese"],
            "China": ["china", "chinese"],
            "India": ["india", "indian"]
        }
    
    def _extract_sector(self, query: str) -> Optional[str]:
        """Extract sector from query."""
        for sector, keywords in self.sector_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    return sector
        return None
    
    def _extract_industry(self, query: str) -> Optional[str]:
        """Extract industry from query."""
        for industry, keywords in self.industry_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    return industry
        return None
    
    def _extract_market(self, query: str) -> Optional[str]:
        """Extract market/exchange from query."""
        for market, keywords in self.market_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    return market
        return None
    
    def _extract_country(self, query: str) -> Optional[str]:
        """Extract country from query."""
        for country, keywords in self.country_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    return country
        return None
    
    def _extract_market_cap_range(self, query: str) -> Optional[str]:
        """Extract market cap range from query."""
        if any(word in query for word in ["large cap", "large-cap", "largecap", "mega cap"]):
            return "large"
        elif any(word in query for word in ["mid cap", "mid-cap", "midcap", "medium cap"]):
            return "mid"
        elif any(word in query for word in ["small cap", "small-cap", "smallcap"]):
            return "small"
        return None
    
    def _extract_risk_tolerance(self, query: str) -> Optional[str]:
        """Extract risk tolerance from query."""
        if any(word in query for word in ["conservative", "low risk", "safe", "stable"]):
            return "conservative"
        elif any(word in query for word in ["moderate", "medium risk", "balanced"]):
            return "moderate"
        elif any(word in query for word in ["aggressive", "high risk", "risky", "volatile"]):
            return "aggressive"
        return None
    
    def _extract_investment_horizon(self, query: str) -> Optional[str]:
        """Extract investment horizon from query."""
        if any(word in query for word in ["short term", "short-term", "short", "immediate"]):
            return "short"
        elif any(word in query for word in ["medium term", "medium-term", "medium"]):
            return "medium"
        elif any(word in query for word in ["long term", "long-term", "long", "retirement"]):
            return "long"
        return None
    
    def _extract_capital_amount(self, query: str) -> Optional[float]:
        """Extract capital amount from query."""
        # Look for dollar amounts
        dollar_pattern = r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|thousand|m|million|b|billion)?'
        matches = re.findall(dollar_pattern, query)
        
        if matches:
            amount_str = matches[0].replace(',', '')
            amount = float(amount_str)
            
            # Handle multipliers
            if any(word in query for word in ["k", "thousand"]):
                amount *= 1000
            elif any(word in query for word in ["m", "million"]):
                amount *= 1000000
            elif any(word in query for word in ["b", "billion"]):
                amount *= 1000000000
            
            return amount
        return None
    
    def _extract_esg_focus(self, query: str) -> bool:
        """Extract ESG focus from query."""
        esg_keywords = ["esg", "environmental", "social", "governance", "sustainable", "green", "ethical", "responsible"]
        return any(keyword in query for keyword in esg_keywords)
    
    def _extract_dividend_focus(self, query: str) -> bool:
        """Extract dividend focus from query."""
        dividend_keywords = ["dividend", "income", "yield", "payout", "income generating"]
        return any(keyword in query for keyword in dividend_keywords)
    
    def _extract_growth_focus(self, query: str) -> bool:
        """Extract growth focus from query."""
        growth_keywords = ["growth", "high growth", "fast growing", "expansion", "scaling"]
        return any(keyword in query for keyword in growth_keywords)
    
    def _extract_value_focus(self, query: str) -> bool:
        """Extract value focus from query."""
        value_keywords = ["value", "undervalued", "cheap", "low pe", "low price", "bargain"]
        return any(keyword in query for keyword in value_keywords)
    
    def _extract_limit(self, query: str) -> int:
        """Extract number of stocks to return from query."""
        # Look for numbers that might indicate quantity
        number_pattern = r'\b(\d+)\s*(?:stocks?|companies?|tickers?|shares?)?\b'
        matches = re.findall(number_pattern, query)
        
        if matches:
            limit = int(matches[0])
            # Reasonable limits
            if 1 <= limit <= 50:
                return limit
        
        return 10  # Default limit 