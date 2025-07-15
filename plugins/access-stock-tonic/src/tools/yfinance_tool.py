"""
YFinance Stock Discovery Tool - A comprehensive LangChain tool for discovering stocks using yfinance.
"""

import logging
from typing import Dict, Any, List, Optional, Union
import yfinance as yf
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import pandas as pd
from datetime import datetime, timedelta
import requests
import json

class StockDiscoveryInput(BaseModel):
    """Input schema for stock discovery."""
    sector: Optional[str] = Field(default=None, description="Sector to filter (e.g., Technology, Healthcare)")
    industry: Optional[str] = Field(default=None, description="Industry to filter")
    market: Optional[str] = Field(default=None, description="Market/Exchange (e.g., US, NASDAQ, NYSE)")
    market_cap_min: Optional[float] = Field(default=None, description="Minimum market cap in billions")
    market_cap_max: Optional[float] = Field(default=None, description="Maximum market cap in billions")
    pe_ratio_max: Optional[float] = Field(default=None, description="Maximum P/E ratio")
    dividend_yield_min: Optional[float] = Field(default=None, description="Minimum dividend yield")
    country: Optional[str] = Field(default=None, description="Country filter")
    limit: Optional[int] = Field(default=20, description="Maximum number of stocks to return")

class YFinanceStockDiscoveryTool(BaseTool):
    """YFinance tool focused on discovering stocks based on various criteria."""
    
    name: str = "yfinance_stock_discovery"
    description: str = """
    A tool for discovering stock tickers using Yahoo Finance data.
    Can discover stocks based on sector, industry, market, market cap, P/E ratio, dividend yield, country, and other criteria.
    Returns actual stock tickers that match the specified criteria.
    """
    logger: Optional[Any] = None
    known_stocks_cache: Optional[Dict[str, Any]] = None
    sector_mappings: Optional[Dict[str, List[str]]] = None
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.known_stocks_cache = {}
        self.sector_mappings = self._load_sector_mappings()
    
    def _load_sector_mappings(self) -> Dict[str, List[str]]:
        """Load comprehensive sector to ticker mappings."""
        return {
            "technology": [
                "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "ADBE", "CRM",
                "ORCL", "INTC", "AMD", "QCOM", "AVGO", "TXN", "MU", "AMAT", "KLAC", "LRCX",
                "SNPS", "CDNS", "ADSK", "ANSS", "CTSH", "WDAY", "ZM", "TEAM", "SPLK", "OKTA",
                "CRWD", "ZS", "NET", "DDOG", "MDB", "PLTR", "SNOW", "RBLX", "UBER", "LYFT"
            ],
            "healthcare": [
                "JNJ", "PFE", "UNH", "ABBV", "TMO", "DHR", "LLY", "ABT", "BMY", "AMGN",
                "GILD", "CVS", "ANTM", "CI", "HUM", "CNC", "WBA", "ISRG", "REGN", "VRTX",
                "BIIB", "ALXN", "ILMN", "DXCM", "IDXX", "WST", "RMD", "COO", "HOLX", "XRAY",
                "BAX", "BDX", "ZBH", "EW", "ALGN", "MTD", "IQV", "LH", "DGX", "A", "BRKR"
            ],
            "finance": [
                "JPM", "BAC", "WFC", "GS", "MS", "BLK", "BRK-B", "C", "USB", "PNC",
                "TFC", "COF", "AXP", "SCHW", "CME", "ICE", "SPGI", "MCO", "FIS", "FISV",
                "GPN", "V", "MA", "PYPL", "SQ", "ADP", "EFX", "TRV", "ALL", "PGR",
                "MET", "PRU", "AIG", "HIG", "PFG", "AFL", "CB", "WRB", "AJG", "MMC"
            ],
            "consumer": [
                "PG", "KO", "PEP", "WMT", "HD", "MCD", "DIS", "NKE", "SBUX", "TGT",
                "COST", "LOW", "TJX", "ROST", "ULTA", "TSCO", "DG", "DLTR", "BURL", "GPS",
                "M", "KSS", "JWN", "NORD", "URBN", "ANF", "GES", "LB", "VSCO", "AEO",
                "AMZN", "EBAY", "ETSY", "BABA", "JD", "PDD", "SE", "MELI", "SHOP", "WISH"
            ],
            "energy": [
                "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "HAL", "BKR",
                "KMI", "WMB", "OKE", "ENB", "TRP", "PAA", "EPD", "ET", "D", "DUK",
                "SO", "NEE", "D", "AEP", "XEL", "SRE", "EIX", "PCG", "DTE", "CMS",
                "CNP", "AEE", "WEC", "ATO", "LNT", "NI", "PNW", "BKH", "IDA", "HE"
            ],
            "industrial": [
                "BA", "CAT", "DE", "GE", "HON", "MMM", "UPS", "FDX", "RTX", "LMT",
                "NOC", "GD", "LHX", "TDG", "TXT", "EMR", "ETN", "ROK", "DOV", "XYL",
                "AME", "FTV", "ITW", "PH", "DHR", "RHI", "ROL", "SNA", "SWK", "TTC",
                "WAB", "WM", "RSG", "WCN", "AWK", "AWR", "CWT", "SJW", "YORW", "ARTNA"
            ],
            "materials": [
                "LIN", "APD", "FCX", "NEM", "NUE", "AA", "BLL", "CCK", "SEE", "WRK",
                "IP", "PKG", "AMCR", "OI", "BMS", "CBT", "CE", "DD", "EMN", "FMC",
                "IFF", "LYB", "MOS", "NTR", "NUE", "SHW", "VMC", "X", "ALB", "LTHM",
                "SQM", "LAC", "PLL", "MP", "REGI", "CLNE", "PLUG", "FCEL", "BLDP", "BE"
            ],
            "real_estate": [
                "AMT", "CCI", "DLR", "EQIX", "PLD", "PSA", "SPG", "VICI", "WELL", "WY",
                "AVB", "EQR", "ESS", "MAA", "UDR", "CPT", "AIV", "BXP", "KIM", "O",
                "REG", "SLG", "VNO", "ARE", "CBRE", "CUBE", "EXR", "PSA", "PLD", "AMT"
            ],
            "utilities": [
                "NEE", "DUK", "SO", "D", "AEP", "XEL", "SRE", "EIX", "PCG", "DTE",
                "CMS", "CNP", "AEE", "WEC", "ATO", "LNT", "NI", "PNW", "BKH", "IDA",
                "HE", "AES", "NRG", "VST", "CEG", "ETR", "FE", "PEG", "AEE", "ED"
            ],
            "communication": [
                "T", "VZ", "CMCSA", "CHTR", "TMUS", "DISH", "PARA", "FOX", "NWSA", "NWS",
                "META", "GOOGL", "NFLX", "DIS", "CMCSA", "PARA", "FOX", "NWSA", "NWS", "SNAP",
                "TWTR", "PINS", "SPOT", "MTCH", "ZG", "TRIP", "EXPE", "BKNG", "ABNB", "UBER"
            ]
        }
    
    def _run(self, query: str) -> str:
        """Main entry point for the tool."""
        try:
            # Parse the query to determine what action to take
            if "discover" in query.lower() or "find" in query.lower() or "screen" in query.lower():
                return self._handle_discovery_query(query)
            elif "sector" in query.lower():
                return self._handle_sector_query(query)
            elif "market" in query.lower() or "exchange" in query.lower():
                return self._handle_market_query(query)
            elif "country" in query.lower() or "geography" in query.lower():
                return self._handle_country_query(query)
            elif "esg" in query.lower() or "sustainability" in query.lower():
                return self._handle_esg_query(query)
            else:
                return self._handle_general_discovery_query(query)
        except Exception as e:
            self.logger.error(f"Error in YFinance discovery tool: {e}")
            return f"Error: {str(e)}"
    
    def _handle_discovery_query(self, query: str) -> str:
        """Handle stock discovery requests."""
        try:
            # Extract criteria from query
            criteria = self._extract_criteria_from_query(query)
            
            # Discover stocks based on criteria
            stocks = self._discover_stocks(criteria)
            
            if not stocks:
                return "No stocks found matching the specified criteria."
            
            # Format the response
            result = f"**Discovered {len(stocks)} stocks:**\n\n"
            
            for i, stock in enumerate(stocks[:10], 1):  # Limit to 10 for readability
                result += f"{i}. **{stock['symbol']}** - {stock['company_name']}\n"
                result += f"   Sector: {stock['sector']}\n"
                result += f"   Market Cap: ${stock['market_cap']:,.0f}\n"
                result += f"   Price: ${stock['current_price']:.2f}\n"
                result += f"   Country: {stock['country']}\n\n"
            
            if len(stocks) > 10:
                result += f"... and {len(stocks) - 10} more stocks found.\n"
            
            return result
            
        except Exception as e:
            return f"Error in stock discovery: {str(e)}"
    
    def _handle_sector_query(self, query: str) -> str:
        """Handle sector-specific stock discovery."""
        try:
            # Extract sector from query
            sector = self._extract_sector_from_query(query)
            
            if not sector:
                return "Please specify a sector (technology, healthcare, finance, consumer, energy, industrial, materials, real_estate, utilities, communication)."
            
            # Get stocks for the sector
            stocks = self._get_stocks_by_sector(sector)
            
            if not stocks:
                return f"No stocks found for sector: {sector}"
            
            result = f"**{sector.title()} Sector Stocks ({len(stocks)} found):**\n\n"
            
            for i, stock in enumerate(stocks[:15], 1):
                result += f"{i}. **{stock['symbol']}** - {stock['company_name']}\n"
                result += f"   Market Cap: ${stock['market_cap']:,.0f}\n"
                result += f"   Price: ${stock['current_price']:.2f}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error in sector query: {str(e)}"
    
    def _handle_market_query(self, query: str) -> str:
        """Handle market/exchange-specific stock discovery."""
        try:
            # Extract market from query
            market = self._extract_market_from_query(query)
            
            if not market:
                return "Please specify a market (NASDAQ, NYSE, US, etc.)."
            
            # Get stocks for the market
            stocks = self._get_stocks_by_market(market)
            
            if not stocks:
                return f"No stocks found for market: {market}"
            
            result = f"**{market.upper()} Market Stocks ({len(stocks)} found):**\n\n"
            
            for i, stock in enumerate(stocks[:15], 1):
                result += f"{i}. **{stock['symbol']}** - {stock['company_name']}\n"
                result += f"   Sector: {stock['sector']}\n"
                result += f"   Market Cap: ${stock['market_cap']:,.0f}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error in market query: {str(e)}"
    
    def _handle_country_query(self, query: str) -> str:
        """Handle country-specific stock discovery."""
        try:
            # Extract country from query
            country = self._extract_country_from_query(query)
            
            if not country:
                return "Please specify a country (US, Canada, UK, etc.)."
            
            # Get stocks for the country
            stocks = self._get_stocks_by_country(country)
            
            if not stocks:
                return f"No stocks found for country: {country}"
            
            result = f"**{country.upper()} Stocks ({len(stocks)} found):**\n\n"
            
            for i, stock in enumerate(stocks[:15], 1):
                result += f"{i}. **{stock['symbol']}** - {stock['company_name']}\n"
                result += f"   Sector: {stock['sector']}\n"
                result += f"   Market Cap: ${stock['market_cap']:,.0f}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error in country query: {str(e)}"
    
    def _handle_esg_query(self, query: str) -> str:
        """Handle ESG/sustainability stock discovery."""
        try:
            # Get ESG-focused stocks
            stocks = self._get_esg_stocks()
            
            if not stocks:
                return "No ESG-focused stocks found."
            
            result = f"**ESG/Sustainability Stocks ({len(stocks)} found):**\n\n"
            
            for i, stock in enumerate(stocks[:15], 1):
                result += f"{i}. **{stock['symbol']}** - {stock['company_name']}\n"
                result += f"   Sector: {stock['sector']}\n"
                result += f"   ESG Focus: {stock.get('esg_focus', 'Sustainability')}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error in ESG query: {str(e)}"
    
    def _handle_general_discovery_query(self, query: str) -> str:
        """Handle general discovery queries."""
        try:
            # Try to extract any stock symbols from the query
            words = query.split()
            symbols = []
            for word in words:
                if len(word) <= 5 and word.isupper() and word.isalpha():
                    symbols.append(word)
            
            if symbols:
                result = "**Stock Information:**\n"
                for symbol in symbols[:5]:  # Limit to 5 symbols
                    try:
                        ticker = yf.Ticker(symbol)
                        info = ticker.info
                        if info and info.get('longName'):
                            price = info.get('currentPrice', 'N/A')
                            name = info.get('longName', symbol)
                            sector = info.get('sector', 'N/A')
                            result += f"- **{symbol}** ({name}) - {sector}\n"
                            result += f"  Price: ${price}\n"
                        else:
                            result += f"- **{symbol}**: No data available\n"
                    except:
                        result += f"- **{symbol}**: Error retrieving data\n"
                return result
            else:
                return "Please specify discovery criteria (sector, market, country, ESG) or provide stock symbols."
                
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    def _extract_criteria_from_query(self, query: str) -> Dict[str, Any]:
        """Extract discovery criteria from query."""
        criteria = {}
        query_lower = query.lower()
        
        # Extract sector
        sectors = list(self.sector_mappings.keys())
        for sector in sectors:
            if sector in query_lower:
                criteria['sector'] = sector
                break
        
        # Extract market cap
        if "large cap" in query_lower or "large-cap" in query_lower:
            criteria['market_cap_min'] = 10.0  # $10B+
        elif "mid cap" in query_lower or "mid-cap" in query_lower:
            criteria['market_cap_min'] = 2.0
            criteria['market_cap_max'] = 10.0
        elif "small cap" in query_lower or "small-cap" in query_lower:
            criteria['market_cap_max'] = 2.0
        
        # Extract market/exchange
        if "nasdaq" in query_lower:
            criteria['market'] = "NASDAQ"
        elif "nyse" in query_lower:
            criteria['market'] = "NYSE"
        elif "us" in query_lower or "united states" in query_lower:
            criteria['country'] = "US"
        
        # Extract P/E ratio
        if "low pe" in query_lower or "value" in query_lower:
            criteria['pe_ratio_max'] = 15.0
        
        # Extract dividend yield
        if "dividend" in query_lower or "income" in query_lower:
            criteria['dividend_yield_min'] = 2.0
        
        return criteria
    
    def _extract_sector_from_query(self, query: str) -> Optional[str]:
        """Extract sector from query."""
        query_lower = query.lower()
        sectors = list(self.sector_mappings.keys())
        
        for sector in sectors:
            if sector in query_lower:
                return sector
        
        return None
    
    def _extract_market_from_query(self, query: str) -> Optional[str]:
        """Extract market from query."""
        query_lower = query.lower()
        
        if "nasdaq" in query_lower:
            return "NASDAQ"
        elif "nyse" in query_lower:
            return "NYSE"
        elif "us" in query_lower:
            return "US"
        
        return None
    
    def _extract_country_from_query(self, query: str) -> Optional[str]:
        """Extract country from query."""
        query_lower = query.lower()
        
        if "us" in query_lower or "united states" in query_lower or "america" in query_lower:
            return "US"
        elif "canada" in query_lower or "canadian" in query_lower:
            return "Canada"
        elif "uk" in query_lower or "britain" in query_lower or "england" in query_lower:
            return "UK"
        
        return None
    
    def _discover_stocks(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover stocks based on criteria."""
        try:
            stocks = []
            
            # Get base stock list
            if 'sector' in criteria:
                base_stocks = self._get_stocks_by_sector(criteria['sector'])
            elif 'market' in criteria:
                base_stocks = self._get_stocks_by_market(criteria['market'])
            elif 'country' in criteria:
                base_stocks = self._get_stocks_by_country(criteria['country'])
            else:
                # Default to technology sector if no specific criteria
                base_stocks = self._get_stocks_by_sector('technology')
            
            # Apply filters
            for stock in base_stocks:
                if self._matches_criteria(stock, criteria):
                    stocks.append(stock)
            
            # Sort by market cap (largest first)
            stocks.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
            
            # Apply limit
            limit = criteria.get('limit', 20)
            return stocks[:limit]
            
        except Exception as e:
            self.logger.error(f"Error discovering stocks: {e}")
            return []
    
    def _get_stocks_by_sector(self, sector: str) -> List[Dict[str, Any]]:
        """Get stocks for a specific sector."""
        try:
            symbols = self.sector_mappings.get(sector.lower(), [])
            stocks = []
            
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    if info and info.get('longName'):
                        stock_data = {
                            'symbol': symbol,
                            'company_name': info.get('longName', 'N/A'),
                            'sector': info.get('sector', 'N/A'),
                            'industry': info.get('industry', 'N/A'),
                            'market_cap': info.get('marketCap', 0),
                            'current_price': info.get('currentPrice', 0),
                            'pe_ratio': info.get('trailingPE', 'N/A'),
                            'dividend_yield': info.get('dividendYield', 0),
                            'country': info.get('country', 'N/A'),
                            'exchange': info.get('exchange', 'N/A'),
                            'volume': info.get('volume', 0)
                        }
                        stocks.append(stock_data)
                except Exception as e:
                    self.logger.warning(f"Error getting info for {symbol}: {e}")
                    continue
            
            return stocks
            
        except Exception as e:
            self.logger.error(f"Error getting stocks by sector: {e}")
            return []
    
    def _get_stocks_by_market(self, market: str) -> List[Dict[str, Any]]:
        """Get stocks for a specific market/exchange."""
        try:
            # For now, use a subset of known stocks for different markets
            market_stocks = {
                "NASDAQ": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "ADBE", "CRM"],
                "NYSE": ["JPM", "BAC", "WFC", "JNJ", "PFE", "UNH", "PG", "KO", "WMT", "HD"],
                "US": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "JPM", "JNJ", "PG", "WMT", "HD"]
            }
            
            symbols = market_stocks.get(market.upper(), [])
            stocks = []
            
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    if info and info.get('longName'):
                        stock_data = {
                            'symbol': symbol,
                            'company_name': info.get('longName', 'N/A'),
                            'sector': info.get('sector', 'N/A'),
                            'industry': info.get('industry', 'N/A'),
                            'market_cap': info.get('marketCap', 0),
                            'current_price': info.get('currentPrice', 0),
                            'pe_ratio': info.get('trailingPE', 'N/A'),
                            'dividend_yield': info.get('dividendYield', 0),
                            'country': info.get('country', 'N/A'),
                            'exchange': info.get('exchange', 'N/A'),
                            'volume': info.get('volume', 0)
                        }
                        stocks.append(stock_data)
                except Exception as e:
                    self.logger.warning(f"Error getting info for {symbol}: {e}")
                    continue
            
            return stocks
            
        except Exception as e:
            self.logger.error(f"Error getting stocks by market: {e}")
            return []
    
    def _get_stocks_by_country(self, country: str) -> List[Dict[str, Any]]:
        """Get stocks for a specific country."""
        try:
            # For now, use US stocks as default
            # In a real implementation, you'd query by country
            return self._get_stocks_by_market("US")
            
        except Exception as e:
            self.logger.error(f"Error getting stocks by country: {e}")
            return []
    
    def _get_esg_stocks(self) -> List[Dict[str, Any]]:
        """Get ESG-focused stocks."""
        try:
            # ESG-focused companies
            esg_symbols = [
                "TSLA", "NEE", "ENPH", "SEDG", "FSLR", "RUN", "SPWR", "VSLR", "PLUG", "FCEL",
                "BLDP", "BE", "NIO", "XPEV", "LI", "LCID", "RIVN", "NKLA", "HYZN", "WKHS"
            ]
            
            stocks = []
            
            for symbol in esg_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    if info and info.get('longName'):
                        stock_data = {
                            'symbol': symbol,
                            'company_name': info.get('longName', 'N/A'),
                            'sector': info.get('sector', 'N/A'),
                            'industry': info.get('industry', 'N/A'),
                            'market_cap': info.get('marketCap', 0),
                            'current_price': info.get('currentPrice', 0),
                            'pe_ratio': info.get('trailingPE', 'N/A'),
                            'dividend_yield': info.get('dividendYield', 0),
                            'country': info.get('country', 'N/A'),
                            'exchange': info.get('exchange', 'N/A'),
                            'volume': info.get('volume', 0),
                            'esg_focus': 'Renewable Energy' if 'energy' in info.get('sector', '').lower() else 'Sustainability'
                        }
                        stocks.append(stock_data)
                except Exception as e:
                    self.logger.warning(f"Error getting info for {symbol}: {e}")
                    continue
            
            return stocks
            
        except Exception as e:
            self.logger.error(f"Error getting ESG stocks: {e}")
            return []
    
    def _matches_criteria(self, stock: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if stock matches the given criteria."""
        try:
            # Market cap filter
            if 'market_cap_min' in criteria:
                if stock.get('market_cap', 0) < criteria['market_cap_min'] * 1e9:  # Convert to billions
                    return False
            
            if 'market_cap_max' in criteria:
                if stock.get('market_cap', 0) > criteria['market_cap_max'] * 1e9:
                    return False
            
            # P/E ratio filter
            if 'pe_ratio_max' in criteria:
                pe_ratio = stock.get('pe_ratio')
                if isinstance(pe_ratio, (int, float)) and pe_ratio > criteria['pe_ratio_max']:
                    return False
            
            # Dividend yield filter
            if 'dividend_yield_min' in criteria:
                dividend_yield = stock.get('dividend_yield', 0)
                if dividend_yield < criteria['dividend_yield_min'] / 100:  # Convert percentage to decimal
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error matching criteria: {e}")
            return False

class YFinanceWrapper:
    """Wrapper class to provide high-level yfinance functionality for stock discovery."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.discovery_tool = YFinanceStockDiscoveryTool()
    
    def discover_stocks(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover stocks based on criteria."""
        try:
            return self.discovery_tool._discover_stocks(criteria)
        except Exception as e:
            self.logger.error(f"Error discovering stocks: {e}")
            return []
    
    def get_stocks_by_sector(self, sector: str) -> List[Dict[str, Any]]:
        """Get stocks for a specific sector."""
        try:
            return self.discovery_tool._get_stocks_by_sector(sector)
        except Exception as e:
            self.logger.error(f"Error getting stocks by sector: {e}")
            return []
    
    def get_stocks_by_market(self, market: str) -> List[Dict[str, Any]]:
        """Get stocks for a specific market."""
        try:
            return self.discovery_tool._get_stocks_by_market(market)
        except Exception as e:
            self.logger.error(f"Error getting stocks by market: {e}")
            return []
    
    def get_esg_stocks(self) -> List[Dict[str, Any]]:
        """Get ESG-focused stocks."""
        try:
            return self.discovery_tool._get_esg_stocks()
        except Exception as e:
            self.logger.error(f"Error getting ESG stocks: {e}")
            return []
    
    def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive ticker information."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                "success": True,
                "data": {
                    "symbol": symbol,
                    "company_name": info.get('longName', 'N/A'),
                    "sector": info.get('sector', 'N/A'),
                    "industry": info.get('industry', 'N/A'),
                    "market_cap": info.get('marketCap', 0),
                    "current_price": info.get('currentPrice', 0),
                    "pe_ratio": info.get('trailingPE', 'N/A'),
                    "dividend_yield": info.get('dividendYield', 0),
                    "country": info.get('country', 'N/A'),
                    "exchange": info.get('exchange', 'N/A'),
                    "volume": info.get('volume', 0),
                    "fifty_two_week_high": info.get('fiftyTwoWeekHigh', 'N/A'),
                    "fifty_two_week_low": info.get('fiftyTwoWeekLow', 'N/A')
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting ticker info for {symbol}: {e}")
            return {"success": False, "error": str(e)} 