import pytest
from src.tools import predictions

# Use a common, liquid stock for basic tests
TEST_SYMBOL = 'AAPL'

def test_predict_daily_basic():
    result = predictions.predict_daily(symbol=TEST_SYMBOL, prediction_days=2, lookback_days=30)
    assert isinstance(result, dict)
    for key in [
        'signals', 'product_metrics', 'risk_metrics', 'sector_metrics',
        'regime_metrics', 'stress_results', 'ensemble_metrics',
        'advanced_signals', 'historical', 'predicted'
    ]:
        assert key in result
    assert 'RSI' in result['signals']

def test_predict_hourly_basic():
    result = predictions.predict_hourly(symbol=TEST_SYMBOL, prediction_days=1, lookback_days=7)
    assert isinstance(result, dict)
    for key in [
        'signals', 'product_metrics', 'risk_metrics', 'sector_metrics',
        'regime_metrics', 'stress_results', 'ensemble_metrics',
        'advanced_signals', 'historical', 'predicted'
    ]:
        assert key in result
    assert 'RSI' in result['signals']

def test_predict_min15_basic():
    result = predictions.predict_min15(symbol=TEST_SYMBOL, prediction_days=1, lookback_days=3)
    assert isinstance(result, dict)
    for key in [
        'signals', 'product_metrics', 'risk_metrics', 'sector_metrics',
        'regime_metrics', 'stress_results', 'ensemble_metrics',
        'advanced_signals', 'historical', 'predicted'
    ]:
        assert key in result
    assert 'RSI' in result['signals'] 