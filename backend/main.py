# backend/main.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from backend.services.data_fetcher import get_yahoo_finance_data, get_market_sentiment_data, get_news_data, get_fred_data
from backend.services.scoring_engine import get_score_and_explanation, train_technical_model, engineer_features
import logging
import pandas as pd # <-- IMPORT MOVED TO TOP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI(title="CredTech AI API", version="1.0.0")

def retrain_model_background(ticker: str):
    logging.info(f"[BACKGROUND] Starting retraining process for {ticker}...")
    try:
        yf_data = get_yahoo_finance_data(ticker)
        if not yf_data:
            logging.error(f"[BACKGROUND] Failed to fetch yfinance data for {ticker}. Aborting."); return
        
        company_name = yf_data["info"].get("longName", ticker)
        market_sentiment = get_market_sentiment_data()
        fred_data = get_fred_data()
        fred_data = fred_data if fred_data is not None else pd.Series(dtype='float64')
        news_data = get_news_data(query=company_name)
        
        all_features = engineer_features(yf_data, market_sentiment, fred_data, news_data or [])
        
        # --- TYPO CORRECTED ---
        if not all_features.empty:
            train_technical_model(all_features, ticker)
            logging.info(f"[BACKGROUND] Retraining for {ticker} completed successfully.")
        else:
            logging.warning(f"[BACKGROUND] Not enough data to retrain model for {ticker}.")
    except Exception as e:
        logging.error(f"[BACKGROUND] An error occurred during retraining for {ticker}: {e}")

@app.get("/api/v1/score/{ticker}")
async def get_credit_score(ticker: str, background_tasks: BackgroundTasks):
    logging.info(f"Received request for ticker: {ticker.upper()}")
    try:
        yf_data = get_yahoo_finance_data(ticker)
        if not yf_data: raise HTTPException(status_code=404, detail=f"Invalid ticker or no data for {ticker}.")
        company_name = yf_data["info"].get("longName", ticker)
        market_sentiment = get_market_sentiment_data()
        fred_data = get_fred_data()
        fred_data = fred_data if fred_data is not None else pd.Series(dtype='float64')
        news_data = get_news_data(query=company_name)
    except Exception as e:
        logging.error(f"Data fetching failed: {e}"); raise HTTPException(status_code=500, detail="Failed to fetch data.")

    result = get_score_and_explanation(
        ticker=ticker, yf_data=yf_data,
        market_sentiment=market_sentiment,
        fred_data=fred_data,
        news_data=news_data or []
    )
    
    if "error" in result or result.get('assessment_type') == 'Heuristic':
        logging.warning(f"Returning known error or heuristic to frontend.")
        return {"ticker": ticker.upper(), "company_name": company_name, "company_info": yf_data.get("info"), "score_result": result, "stock_history": yf_data.get("historical_data"), "recent_news_for_context": news_data[:5] if news_data else []}
    
    background_tasks.add_task(retrain_model_background, ticker)
    logging.info(f"Scheduled background retraining for {ticker}.")
    return {"ticker": ticker.upper(), "company_name": company_name, "company_info": yf_data.get("info"), "score_result": result, "stock_history": yf_data.get("historical_data"), "recent_news_for_context": news_data[:5] if news_data else []}

@app.get("/")
def read_root(): return {"message": "CredTech API is running."}
