# backend/main.py

from fastapi import FastAPI, HTTPException

# Use absolute imports for our service modules
from backend.services import data_fetcher
from backend.services import scoring_engine

app = FastAPI(
    title="CredTech AI API",
    description="API for the Explainable Credit Intelligence Platform.",
    version="0.1.0"
)

# --- PRIMARY API ENDPOINTS ---

@app.get("/")
def read_root():
    """A simple endpoint to check if the API is running."""
    return {"message": "Welcome to the CredTech AI Backend!"}


@app.get("/api/v1/score/{ticker}")
async def get_credit_score(ticker: str):
    """
    Orchestrates the entire process: fetches data, gets a score and explanation,
    and returns a complete payload for the enhanced frontend.
    """
    # STEP 1: Fetch data from all sources.
    yf_data = data_fetcher.get_yahoo_finance_data(ticker)
    if not yf_data:
        raise HTTPException(status_code=404, detail=f"Invalid ticker or no data found for {ticker} from Yahoo Finance.")
    
    company_name = yf_data["info"].get("longName", ticker)
    wb_data = data_fetcher.get_world_bank_data()
    news_data = data_fetcher.get_news_data(query=company_name)

    # STEP 2: Call the scoring engine.
    result = scoring_engine.get_score_and_explanation(
        ticker=ticker,
        yf_data=yf_data,
        wb_data=wb_data or [],
        news_data=news_data or []
    )
    
    if "error" in result:
         raise HTTPException(status_code=500, detail=result["error"])

    # STEP 3: Return the complete, corrected payload.
    # This now includes all the data our new frontend needs.
    return {
        "ticker": ticker,
        "company_name": company_name,
        "company_info": yf_data.get("info"),              # CORRECTLY ADDED
        "score_result": result,
        "stock_history": yf_data.get("historical_data"),  # CORRECTLY ADDED
        "recent_news_for_context": news_data[:5] if news_data else []
    }


# --- DEBUGGING ENDPOINTS ---

@app.get("/api/v1/fetch-all/{ticker}")
def fetch_all_raw_data(ticker: str):
    """
    A debugging endpoint to fetch and view all raw data for a given company ticker.
    This is now corrected to perform its original function.
    """
    yf_data = data_fetcher.get_yahoo_finance_data(ticker)
    if not yf_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for ticker {ticker}.")
    
    company_name = yf_data["info"].get("longName", ticker)
    wb_data = data_fetcher.get_world_bank_data()
    news_data = data_fetcher.get_news_data(query=company_name)

    # CORRECTED RETURN STATEMENT:
    # - Fixed indentation.
    # - Returns only the raw data fetched within this function.
    return {
        "message": "Raw data fetch successful. This is a debugging endpoint.",
        "ticker": ticker,
        "company_info": yf_data.get("info"),
        "stock_history": yf_data.get("historical_data"),
        "macro_economic_context": wb_data,
        "recent_news": news_data
    }