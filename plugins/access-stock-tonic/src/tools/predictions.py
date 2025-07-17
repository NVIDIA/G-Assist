import typing as t
from . import stockpredictions

# --- Entrypoint: Daily Prediction ---
def predict_daily(
    symbol: str,
    prediction_days: int = 30,
    lookback_days: int = 365,
    strategy: str = "chronos",
    use_ensemble: bool = True,
    use_regime_detection: bool = True,
    use_stress_testing: bool = True,
    risk_free_rate: float = 0.02,
    market_index: str = "^GSPC",
    chronos_weight: float = 0.6,
    technical_weight: float = 0.2,
    statistical_weight: float = 0.2,
    random_real_points: int = 4,
    use_smoothing: bool = True,
    smoothing_type: str = "exponential",
    smoothing_window: int = 5,
    smoothing_alpha: float = 0.3,
    use_covariates: bool = True,
    use_sentiment: bool = True
) -> dict:
    """
    Entrypoint for daily stock prediction. Returns a dictionary with prediction results and metrics.
    """
    ensemble_weights = {
        "chronos": chronos_weight,
        "technical": technical_weight,
        "statistical": statistical_weight
    }
    market_df = stockpredictions.get_market_data(market_index, lookback_days)
    market_returns = market_df['Returns'] if not market_df.empty else None
    signals, fig = stockpredictions.make_prediction_enhanced(
        symbol=symbol,
        timeframe="1d",
        prediction_days=prediction_days,
        strategy=strategy,
        use_ensemble=use_ensemble,
        use_regime_detection=use_regime_detection,
        use_stress_testing=use_stress_testing,
        risk_free_rate=risk_free_rate,
        ensemble_weights=ensemble_weights,
        market_index=market_index,
        use_covariates=use_covariates,
        use_sentiment=use_sentiment,
        random_real_points=random_real_points,
        use_smoothing=use_smoothing,
        smoothing_type=smoothing_type,
        smoothing_window=smoothing_window,
        smoothing_alpha=smoothing_alpha
    )
    df = stockpredictions.get_historical_data(symbol, "1d", lookback_days)
    fundamentals = stockpredictions.get_fundamental_data(symbol)
    product_metrics = {
        "Market_Cap": fundamentals.get("marketCap"),
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Dividend_Yield": fundamentals.get("dividendYield"),
        "Avg_Daily_Volume": fundamentals.get("averageDailyVolume"),
        "Volume_Volatility": df['Volume'].rolling(window=20, min_periods=1).std().iloc[-1] if 'Volume' in df.columns else None,
        "Enterprise_Value": fundamentals.get("enterpriseValue"),
        "P/E_Ratio": fundamentals.get("trailingPE"),
        "Forward_P/E": fundamentals.get("forwardPE"),
        "PEG_Ratio": fundamentals.get("pegRatio"),
        "Price_to_Book": fundamentals.get("priceToBook"),
        "Price_to_Sales": fundamentals.get("priceToSalesTrailing12Months"),
    }
    risk_metrics = stockpredictions.calculate_advanced_risk_metrics(df, market_returns, risk_free_rate)
    sector_metrics = {
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Market_Cap_Rank": "Large" if fundamentals.get("marketCap", 0) > 1e10 else "Mid" if fundamentals.get("marketCap", 0) > 1e9 else "Small",
        "Liquidity_Score": "High" if fundamentals.get("averageDailyVolume", 0) > 1e6 else "Medium" if fundamentals.get("averageDailyVolume", 0) > 1e5 else "Low",
        "Gross_Margin": fundamentals.get("grossMargins"),
        "Operating_Margin": fundamentals.get("operatingMargins"),
        "Net_Margin": fundamentals.get("netMargins"),
    }
    regime_metrics = signals.get("regime_info", {})
    stress_results = signals.get("stress_test_results", {})
    ensemble_metrics = {
        "ensemble_used": signals.get("ensemble_used", False),
        "ensemble_weights": ensemble_weights,
        "enhanced_features": {
            "covariate_data_used": signals.get("covariate_data_available", False),
            "sentiment_analysis_used": use_sentiment,
            "advanced_uncertainty_methods": list(signals.get("advanced_uncertainties", {}).keys()),
            "regime_aware_uncertainty": use_regime_detection,
            "enhanced_volume_prediction": signals.get("prediction", {}).get("volume") is not None
        }
    }
    basic_signals = {
        "RSI": signals.get("RSI", "Neutral"),
        "MACD": signals.get("MACD", "Hold"),
        "Bollinger": signals.get("Bollinger", "Hold"),
        "SMA": signals.get("SMA", "Hold"),
        "Overall": signals.get("Overall", "Hold"),
        "symbol": signals.get("symbol", symbol),
        "timeframe": signals.get("timeframe", "1d"),
        "strategy_used": signals.get("strategy_used", strategy)
    }
    advanced_signals = signals.get("advanced_signals", {})
    historical = signals.get('historical', {})
    predicted = signals.get('prediction', {})
    return {
        "signals": basic_signals,
        "plot": fig,
        "product_metrics": product_metrics,
        "risk_metrics": risk_metrics,
        "sector_metrics": sector_metrics,
        "regime_metrics": regime_metrics,
        "stress_results": stress_results,
        "ensemble_metrics": ensemble_metrics,
        "advanced_signals": advanced_signals,
        "historical": historical,
        "predicted": predicted
    }

# --- Entrypoint: Hourly Prediction ---
def predict_hourly(
    symbol: str,
    prediction_days: int = 3,
    lookback_days: int = 14,
    strategy: str = "chronos",
    use_ensemble: bool = True,
    use_regime_detection: bool = True,
    use_stress_testing: bool = True,
    risk_free_rate: float = 0.02,
    market_index: str = "^GSPC",
    chronos_weight: float = 0.6,
    technical_weight: float = 0.2,
    statistical_weight: float = 0.2,
    random_real_points: int = 4,
    use_smoothing: bool = True,
    smoothing_type: str = "exponential",
    smoothing_window: int = 5,
    smoothing_alpha: float = 0.3,
    use_covariates: bool = True,
    use_sentiment: bool = True
) -> dict:
    """
    Entrypoint for hourly stock prediction. Returns a dictionary with prediction results and metrics.
    """
    ensemble_weights = {
        "chronos": chronos_weight,
        "technical": technical_weight,
        "statistical": statistical_weight
    }
    market_df = stockpredictions.get_market_data(market_index, lookback_days)
    market_returns = market_df['Returns'] if not market_df.empty else None
    signals, fig = stockpredictions.make_prediction_enhanced(
        symbol=symbol,
        timeframe="1h",
        prediction_days=prediction_days,
        strategy=strategy,
        use_ensemble=use_ensemble,
        use_regime_detection=use_regime_detection,
        use_stress_testing=use_stress_testing,
        risk_free_rate=risk_free_rate,
        ensemble_weights=ensemble_weights,
        market_index=market_index,
        use_covariates=use_covariates,
        use_sentiment=use_sentiment,
        random_real_points=random_real_points,
        use_smoothing=use_smoothing,
        smoothing_type=smoothing_type,
        smoothing_window=smoothing_window,
        smoothing_alpha=smoothing_alpha
    )
    df = stockpredictions.get_historical_data(symbol, "1h", lookback_days)
    fundamentals = stockpredictions.get_fundamental_data(symbol)
    product_metrics = {
        "Market_Cap": fundamentals.get("marketCap"),
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Dividend_Yield": fundamentals.get("dividendYield"),
        "Avg_Daily_Volume": fundamentals.get("averageDailyVolume"),
        "Volume_Volatility": df['Volume'].rolling(window=20, min_periods=1).std().iloc[-1] if 'Volume' in df.columns else None,
        "Enterprise_Value": fundamentals.get("enterpriseValue"),
        "P/E_Ratio": fundamentals.get("trailingPE"),
        "Forward_P/E": fundamentals.get("forwardPE"),
        "PEG_Ratio": fundamentals.get("pegRatio"),
        "Price_to_Book": fundamentals.get("priceToBook"),
        "Price_to_Sales": fundamentals.get("priceToSalesTrailing12Months"),
    }
    risk_metrics = stockpredictions.calculate_advanced_risk_metrics(df, market_returns, risk_free_rate)
    sector_metrics = {
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Market_Cap_Rank": "Large" if fundamentals.get("marketCap", 0) > 1e10 else "Mid" if fundamentals.get("marketCap", 0) > 1e9 else "Small",
        "Liquidity_Score": "High" if fundamentals.get("averageDailyVolume", 0) > 1e6 else "Medium" if fundamentals.get("averageDailyVolume", 0) > 1e5 else "Low",
        "Gross_Margin": fundamentals.get("grossMargins"),
        "Operating_Margin": fundamentals.get("operatingMargins"),
        "Net_Margin": fundamentals.get("netMargins"),
    }
    regime_metrics = signals.get("regime_info", {})
    stress_results = signals.get("stress_test_results", {})
    ensemble_metrics = {
        "ensemble_used": signals.get("ensemble_used", False),
        "ensemble_weights": ensemble_weights,
        "enhanced_features": {
            "covariate_data_used": signals.get("covariate_data_available", False),
            "sentiment_analysis_used": use_sentiment,
            "advanced_uncertainty_methods": list(signals.get("advanced_uncertainties", {}).keys()),
            "regime_aware_uncertainty": use_regime_detection,
            "enhanced_volume_prediction": signals.get("prediction", {}).get("volume") is not None
        }
    }
    basic_signals = {
        "RSI": signals.get("RSI", "Neutral"),
        "MACD": signals.get("MACD", "Hold"),
        "Bollinger": signals.get("Bollinger", "Hold"),
        "SMA": signals.get("SMA", "Hold"),
        "Overall": signals.get("Overall", "Hold"),
        "symbol": signals.get("symbol", symbol),
        "timeframe": signals.get("timeframe", "1h"),
        "strategy_used": signals.get("strategy_used", strategy)
    }
    advanced_signals = signals.get("advanced_signals", {})
    historical = signals.get('historical', {})
    predicted = signals.get('prediction', {})
    return {
        "signals": basic_signals,
        "plot": fig,
        "product_metrics": product_metrics,
        "risk_metrics": risk_metrics,
        "sector_metrics": sector_metrics,
        "regime_metrics": regime_metrics,
        "stress_results": stress_results,
        "ensemble_metrics": ensemble_metrics,
        "advanced_signals": advanced_signals,
        "historical": historical,
        "predicted": predicted
    }

# --- Entrypoint: 15-Minute Prediction ---
def predict_min15(
    symbol: str,
    prediction_days: int = 1,
    lookback_days: int = 3,
    strategy: str = "chronos",
    use_ensemble: bool = True,
    use_regime_detection: bool = True,
    use_stress_testing: bool = True,
    risk_free_rate: float = 0.02,
    market_index: str = "^GSPC",
    chronos_weight: float = 0.6,
    technical_weight: float = 0.2,
    statistical_weight: float = 0.2,
    random_real_points: int = 4,
    use_smoothing: bool = True,
    smoothing_type: str = "exponential",
    smoothing_window: int = 5,
    smoothing_alpha: float = 0.3,
    use_covariates: bool = True,
    use_sentiment: bool = True
) -> dict:
    """
    Entrypoint for 15-minute stock prediction. Returns a dictionary with prediction results and metrics.
    """
    ensemble_weights = {
        "chronos": chronos_weight,
        "technical": technical_weight,
        "statistical": statistical_weight
    }
    market_df = stockpredictions.get_market_data(market_index, lookback_days)
    market_returns = market_df['Returns'] if not market_df.empty else None
    signals, fig = stockpredictions.make_prediction_enhanced(
        symbol=symbol,
        timeframe="15m",
        prediction_days=prediction_days,
        strategy=strategy,
        use_ensemble=use_ensemble,
        use_regime_detection=use_regime_detection,
        use_stress_testing=use_stress_testing,
        risk_free_rate=risk_free_rate,
        ensemble_weights=ensemble_weights,
        market_index=market_index,
        use_covariates=use_covariates,
        use_sentiment=use_sentiment,
        random_real_points=random_real_points,
        use_smoothing=use_smoothing,
        smoothing_type=smoothing_type,
        smoothing_window=smoothing_window,
        smoothing_alpha=smoothing_alpha
    )
    df = stockpredictions.get_historical_data(symbol, "15m", lookback_days)
    fundamentals = stockpredictions.get_fundamental_data(symbol)
    product_metrics = {
        "Market_Cap": fundamentals.get("marketCap"),
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Dividend_Yield": fundamentals.get("dividendYield"),
        "Avg_Daily_Volume": fundamentals.get("averageDailyVolume"),
        "Volume_Volatility": df['Volume'].rolling(window=20, min_periods=1).std().iloc[-1] if 'Volume' in df.columns else None,
        "Enterprise_Value": fundamentals.get("enterpriseValue"),
        "P/E_Ratio": fundamentals.get("trailingPE"),
        "Forward_P/E": fundamentals.get("forwardPE"),
        "PEG_Ratio": fundamentals.get("pegRatio"),
        "Price_to_Book": fundamentals.get("priceToBook"),
        "Price_to_Sales": fundamentals.get("priceToSalesTrailing12Months"),
    }
    risk_metrics = stockpredictions.calculate_advanced_risk_metrics(df, market_returns, risk_free_rate)
    sector_metrics = {
        "Sector": fundamentals.get("sector"),
        "Industry": fundamentals.get("industry"),
        "Market_Cap_Rank": "Large" if fundamentals.get("marketCap", 0) > 1e10 else "Mid" if fundamentals.get("marketCap", 0) > 1e9 else "Small",
        "Liquidity_Score": "High" if fundamentals.get("averageDailyVolume", 0) > 1e6 else "Medium" if fundamentals.get("averageDailyVolume", 0) > 1e5 else "Low",
        "Gross_Margin": fundamentals.get("grossMargins"),
        "Operating_Margin": fundamentals.get("operatingMargins"),
        "Net_Margin": fundamentals.get("netMargins"),
    }
    regime_metrics = signals.get("regime_info", {})
    stress_results = signals.get("stress_test_results", {})
    ensemble_metrics = {
        "ensemble_used": signals.get("ensemble_used", False),
        "ensemble_weights": ensemble_weights,
        "enhanced_features": {
            "covariate_data_used": signals.get("covariate_data_available", False),
            "sentiment_analysis_used": use_sentiment,
            "advanced_uncertainty_methods": list(signals.get("advanced_uncertainties", {}).keys()),
            "regime_aware_uncertainty": use_regime_detection,
            "enhanced_volume_prediction": signals.get("prediction", {}).get("volume") is not None
        }
    }
    basic_signals = {
        "RSI": signals.get("RSI", "Neutral"),
        "MACD": signals.get("MACD", "Hold"),
        "Bollinger": signals.get("Bollinger", "Hold"),
        "SMA": signals.get("SMA", "Hold"),
        "Overall": signals.get("Overall", "Hold"),
        "symbol": signals.get("symbol", symbol),
        "timeframe": signals.get("timeframe", "15m"),
        "strategy_used": signals.get("strategy_used", strategy)
    }
    advanced_signals = signals.get("advanced_signals", {})
    historical = signals.get('historical', {})
    predicted = signals.get('prediction', {})
    return {
        "signals": basic_signals,
        "plot": fig,
        "product_metrics": product_metrics,
        "risk_metrics": risk_metrics,
        "sector_metrics": sector_metrics,
        "regime_metrics": regime_metrics,
        "stress_results": stress_results,
        "ensemble_metrics": ensemble_metrics,
        "advanced_signals": advanced_signals,
        "historical": historical,
        "predicted": predicted
    } 