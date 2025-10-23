"""A small helper to run full retraining for core tickers.
This is a minimal safe placeholder so the API endpoint can call it. Adapt to your real retraining logic.
"""
import logging
from backend.services.data_fetcher import get_yahoo_finance_data
from backend.services.scoring_engine import engineer_features, train_technical_model
from backend.services.scoring_engine import get_score_and_explanation

# Example: list of core tickers to retrain (adapt as needed)
CORE_TICKERS = ["AAPL", "MSFT", "GOOGL"]

def run_retraining_job():
    logging.info("[RETRAIN_ALL] Starting full retraining job for core tickers...")
    for ticker in CORE_TICKERS:
        try:
            logging.info(f"[RETRAIN_ALL] Retraining for {ticker}...")
            yf_data = get_yahoo_finance_data(ticker)
            if not yf_data:
                logging.warning(f"[RETRAIN_ALL] No yfinance data for {ticker}, skipping.")
                continue
            # placeholder: create features and retrain
            features = engineer_features(yf_data, None, None, [])
            if features is None or (hasattr(features, 'empty') and features.empty):
                logging.warning(f"[RETRAIN_ALL] Not enough features for {ticker}, skipping.")
                continue
            train_technical_model(features, ticker)
            logging.info(f"[RETRAIN_ALL] Retraining completed for {ticker}.")
        except Exception as e:
            logging.error(f"[RETRAIN_ALL] Error retraining {ticker}: {e}")
    logging.info("[RETRAIN_ALL] Full retraining job complete.")
