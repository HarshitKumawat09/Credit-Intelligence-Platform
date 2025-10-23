# backend/services/data_fetcher.py

import yfinance as yf
from newsapi import NewsApiClient
from fredapi import Fred
import pandas as pd
from datetime import datetime
import logging
from .config import NEWS_API_KEY, FRED_API_KEY

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
fred = Fred(api_key=FRED_API_KEY)

def get_yahoo_finance_data(ticker_symbol: str):
    logging.info(f"Fetching yfinance data for ticker: {ticker_symbol}")
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist_data = ticker.history(period="1y")
        if hist_data.empty: return None
        hist_data.index = hist_data.index.map(lambda x: x.strftime('%Y-%m-%d'))
        info = ticker.info
        return {"historical_data": hist_data.to_dict(orient="index"), "info": {"longName": info.get("longName"), "sector": info.get("sector"), "marketCap": info.get("marketCap"), "trailingPE": info.get("trailingPE"), "dividendYield": info.get("dividendYield"), "debtToEquity": info.get("debtToEquity"), "totalCashPerShare": info.get("totalCashPerShare")}}
    except Exception as e:
        logging.error(f"yfinance error for {ticker_symbol}: {e}"); return None

def get_fred_data(series_id='DGS10'):
    try:
        logging.info(f"Fetching FRED data for series: {series_id}")
        end_date = datetime.now()
        start_date = end_date - pd.DateOffset(years=1)
        series_data = fred.get_series(series_id, start_date=start_date, end_date=end_date)
        return series_data
    except Exception as e:
        logging.error(f"Could not fetch FRED data for {series_id}: {e}"); return None

def get_market_sentiment_data():
    try:
        logging.info("Fetching S&P 500 data for market sentiment.")
        sp500 = yf.Ticker("^GSPC"); hist = sp500.history(period="4mo")
        if hist.empty or len(hist) < 2:
            logging.warning("Not enough S&P 500 data."); return 0.0
        price_now = hist['Close'].iloc[-1]; price_ago = hist['Close'].iloc[0]
        return ((price_now - price_ago) / price_ago) * 100
    except Exception as e:
        logging.error(f"Could not fetch market sentiment data: {e}"); return 0.0

def get_news_data(query: str):
    if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_API_KEY":
        logging.warning("NewsAPI key not configured."); return None
    from datetime import timedelta
    logging.info(f"Fetching news from NewsAPI for query: '{query}'")
    try:
        from_date = (datetime.now() - timedelta(days=29)).strftime('%Y-%m-%d')
        all_articles = newsapi.get_everything(q=query, language='en', sort_by='relevancy', from_param=from_date, page_size=20)
        return [{"source": article["source"]["name"], "title": article["title"], "url": article["url"], "publishedAt": article["publishedAt"], "content": article.get("content", "")} for article in all_articles["articles"]]
    except Exception as e:
        logging.error(f"NewsAPI error for query '{query}': {e}"); return None