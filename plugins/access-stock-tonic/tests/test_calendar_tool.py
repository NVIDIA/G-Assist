import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import json
import pytest
from unittest.mock import patch, MagicMock
from tools.calendar_tool import CalendarTool, TickerEvent, TickerCalendar

TEST_TRACKED_FILE = os.path.join(os.path.dirname(__file__), 'calendar_tracked_test.json')

@pytest.fixture(autouse=True)
def cleanup_tracked_file():
    # Remove the test tracked file before and after each test
    if os.path.exists(TEST_TRACKED_FILE):
        os.remove(TEST_TRACKED_FILE)
    yield
    if os.path.exists(TEST_TRACKED_FILE):
        os.remove(TEST_TRACKED_FILE)

@pytest.fixture
def tool():
    tool = CalendarTool()
    tool.tracked_file = TEST_TRACKED_FILE  # Use test file for isolation
    tool.tracked_tickers = []
    tool._save_tracked_tickers()
    return tool

@patch('tools.calendar_tool.yf.Ticker')
def test_add_and_remove_ticker(mock_ticker, tool):
    assert tool.add_ticker('AAPL') is True
    assert tool.add_ticker('AAPL') is False  # Already added
    assert 'AAPL' in tool.tracked_tickers
    assert tool.remove_ticker('AAPL') is True
    assert tool.remove_ticker('AAPL') is False  # Already removed
    assert 'AAPL' not in tool.tracked_tickers

@patch('tools.calendar_tool.yf.Ticker')
def test_persistence(mock_ticker, tool):
    tool.add_ticker('AAPL')
    tool2 = CalendarTool()
    tool2.tracked_file = TEST_TRACKED_FILE
    assert 'AAPL' in tool2._load_tracked_tickers()

@patch('tools.calendar_tool.yf.Ticker')
def test_fetch_ticker_events(mock_ticker):
    # Mock yfinance Ticker
    mock_instance = MagicMock()
    # Mock earnings_dates DataFrame
    import pandas as pd
    earnings_df = pd.DataFrame({
        'Earnings Date': [pd.Timestamp('2025-07-20')],
        'EPS Estimate': [2.5]
    })
    mock_instance.get_earnings_dates.return_value = earnings_df
    # Mock calendar DataFrame
    calendar_df = pd.DataFrame({'exDividendDate': [pd.Timestamp('2025-07-21')]})
    mock_instance.calendar = calendar_df
    mock_ticker.return_value = mock_instance
    tool = CalendarTool()
    tool.tracked_file = TEST_TRACKED_FILE
    cal = tool.fetch_ticker_events('AAPL')
    assert cal.symbol == 'AAPL'
    event_types = [e.event_type for e in cal.events]
    assert 'earnings' in event_types
    assert 'exDividendDate' in event_types

@patch('tools.calendar_tool.yf.Ticker')
def test_update_all_calendars(mock_ticker, tool):
    tool.add_ticker('AAPL')
    mock_instance = MagicMock()
    import pandas as pd
    earnings_df = pd.DataFrame({'Earnings Date': [pd.Timestamp('2025-07-20')]})
    mock_instance.get_earnings_dates.return_value = earnings_df
    calendar_df = pd.DataFrame({'exDividendDate': [pd.Timestamp('2025-07-21')]})
    mock_instance.calendar = calendar_df
    mock_ticker.return_value = mock_instance
    result = tool.update_all_calendars()
    assert 'AAPL' in result
    assert any(e['event_type'] == 'earnings' for e in result['AAPL'])
    assert any(e['event_type'] == 'exDividendDate' for e in result['AAPL'])

@patch('tools.calendar_tool.yf.Ticker')
def test_get_todays_events(mock_ticker, tool):
    tool.add_ticker('AAPL')
    mock_instance = MagicMock()
    import pandas as pd
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    earnings_df = pd.DataFrame({'Earnings Date': [pd.Timestamp(today)]})
    mock_instance.get_earnings_dates.return_value = earnings_df
    calendar_df = pd.DataFrame({'exDividendDate': [pd.Timestamp('2025-07-21')]})
    mock_instance.calendar = calendar_df
    mock_ticker.return_value = mock_instance
    events_today = tool.get_todays_events()
    assert any(e['event_type'] == 'earnings' for e in events_today)
    assert all(e['symbol'] == 'AAPL' for e in events_today)

@patch('tools.calendar_tool.yf.Ticker')
def test_run_interface(mock_ticker, tool):
    # Add
    result = tool._run('add', 'AAPL')
    assert result['success'] is True
    # Remove
    result = tool._run('remove', 'AAPL')
    assert result['success'] is True
    # Invalid
    result = tool._run('add', None)
    assert 'error' in result or result['success'] is False
    # Update (mocked)
    tool.add_ticker('AAPL')
    mock_instance = MagicMock()
    import pandas as pd
    earnings_df = pd.DataFrame({'Earnings Date': [pd.Timestamp('2025-07-20')]})
    mock_instance.get_earnings_dates.return_value = earnings_df
    calendar_df = pd.DataFrame({'exDividendDate': [pd.Timestamp('2025-07-21')]})
    mock_instance.calendar = calendar_df
    mock_ticker.return_value = mock_instance
    result = tool._run('update')
    assert 'AAPL' in result
    # Today
    result = tool._run('today')
    assert isinstance(result, list)
    # Get events
    result = tool._run('get_events', 'AAPL')
    assert isinstance(result, list) 