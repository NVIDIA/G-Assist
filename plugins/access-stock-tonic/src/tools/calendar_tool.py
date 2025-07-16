import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field as dc_field
import yfinance as yf
import pandas as pd
from langchain_core.tools import BaseTool
from datetime import datetime

# Data object for a single event
@dataclass
class TickerEvent:
    event_type: str  # e.g., "earnings", "dividend", "split", "other"
    date: str        # ISO format
    time: str        # If available, else empty
    details: Dict[str, Any] = dc_field(default_factory=dict)

# Data object for a ticker's calendar
@dataclass
class TickerCalendar:
    symbol: str
    events: List[TickerEvent] = dc_field(default_factory=list)

class CalendarTool(BaseTool):
    """
    Tool for managing and retrieving important calendar dates for user-specified tickers.
    Supports adding/removing tickers, updating events, and fetching today's events.
    """
    name: str = "calendar_tool"
    description: str = "Manages tracked tickers and retrieves their important calendar events (earnings, dividends, etc.) using yfinance."
    tracked_file: str = os.path.join(os.path.dirname(__file__), "calendar_tracked.json")
    tracked_tickers: list = dc_field(default_factory=list)  # <-- Fix for Pydantic
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Only set tracked_tickers if not already set by Pydantic
        if not hasattr(self, 'tracked_tickers') or self.tracked_tickers is None:
            self.tracked_tickers = self._load_tracked_tickers()
        else:
            # If already set (e.g., by test), don't overwrite
            pass

    def _load_tracked_tickers(self) -> List[str]:
        if os.path.exists(self.tracked_file):
            try:
                with open(self.tracked_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_tracked_tickers(self):
        with open(self.tracked_file, "w") as f:
            json.dump(self.tracked_tickers, f)

    def add_ticker(self, symbol: str) -> bool:
        symbol = symbol.upper()
        if symbol not in self.tracked_tickers:
            self.tracked_tickers.append(symbol)
            self._save_tracked_tickers()
            return True
        return False

    def remove_ticker(self, symbol: str) -> bool:
        symbol = symbol.upper()
        if symbol in self.tracked_tickers:
            self.tracked_tickers.remove(symbol)
            self._save_tracked_tickers()
            return True
        return False

    def fetch_ticker_events(self, symbol: str) -> TickerCalendar:
        symbol = symbol.upper()
        events: List[TickerEvent] = []
        ticker = yf.Ticker(symbol)
        # Earnings dates
        try:
            earnings_df = ticker.get_earnings_dates(limit=8)
            if isinstance(earnings_df, pd.DataFrame):
                for idx, row in earnings_df.iterrows():
                    date_val = row.get("Earnings Date")
                    if pd.notnull(date_val):
                        date_str = date_val.strftime("%Y-%m-%d")
                        events.append(TickerEvent(
                            event_type="earnings",
                            date=date_str,
                            time="",
                            details=row.to_dict()
                        ))
        except Exception:
            pass
        # Calendar events
        try:
            cal = ticker.calendar
            if isinstance(cal, pd.DataFrame):
                for col in cal.columns:
                    date_val = cal.at[0, col]
                    if isinstance(date_val, pd.Timestamp):
                        events.append(TickerEvent(
                            event_type=col,
                            date=date_val.strftime("%Y-%m-%d"),
                            time="",
                            details={}
                        ))
        except Exception:
            pass
        return TickerCalendar(symbol=symbol, events=events)

    def update_all_calendars(self) -> Dict[str, Any]:
        """Fetch and return all events for all tracked tickers."""
        result = {}
        for symbol in self.tracked_tickers:
            cal = self.fetch_ticker_events(symbol)
            result[symbol] = [event.__dict__ for event in cal.events]
        return result

    def get_todays_events(self) -> List[Dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%d")
        events_today = []
        for symbol in self.tracked_tickers:
            cal = self.fetch_ticker_events(symbol)
            for event in cal.events:
                if event.date == today:
                    events_today.append({
                        "symbol": symbol,
                        "event_type": event.event_type,
                        "date": event.date,
                        "details": event.details
                    })
        return events_today

    def _run(self, action: str, symbol: Optional[str] = None) -> Any:
        """
        Main entry point for LangChain tool interface.
        action: 'add', 'remove', 'update', 'today', 'get_events'
        symbol: ticker symbol (if needed)
        """
        if action == "add" and symbol:
            return {"success": self.add_ticker(symbol)}
        elif action == "remove" and symbol:
            return {"success": self.remove_ticker(symbol)}
        elif action == "update":
            return self.update_all_calendars()
        elif action == "today":
            return self.get_todays_events()
        elif action == "get_events" and symbol:
            cal = self.fetch_ticker_events(symbol)
            return [event.__dict__ for event in cal.events]
        else:
            return {"error": "Invalid action or missing symbol."} 