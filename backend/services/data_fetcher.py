# backend/services/data_fetcher.py

import yfinance as yf
import wbgapi as wb
from newsapi import NewsApiClient
from datetime import datetime
import logging
import time # <-- Import the time library for retries

# Initialize NewsAPI client (replace 'YOUR_API_KEY' with your actual API key)
newsapi = NewsApiClient(api_key='YOUR_API_KEY')

# --- DATA FETCHING FUNCTIONS ---
def get_yahoo_finance_data(ticker_symbol: str):
    # This function is working well, no changes needed.
    # ...
    logging.info(f"Fetching yfinance data for ticker: {ticker_symbol}")
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist_data = ticker.history(period="1y")
        if hist_data.empty:
            logging.warning(f"No historical data from yfinance for {ticker_symbol}.")
            return None
        hist_data.index = hist_data.index.map(lambda x: x.strftime('%Y-%m-%d'))
        info = ticker.info
        return { "historical_data": hist_data.to_dict(orient="index"), "info": { "longName": info.get("longName"), "sector": info.get("sector"), "industry": info.get("industry"), "country": info.get("country"), "marketCap": info.get("marketCap"), "trailingPE": info.get("trailingPE"), "dividendYield": info.get("dividendYield") } }
    except Exception as e:
        logging.error(f"yfinance error for {ticker_symbol}: {e}")
        return None

def get_world_bank_data(country_code: str = "WLD", indicator: str = "NY.GDP.MKTP.KD.ZG"):
    """
    V3: Adds retry logic and a more compatible time range for the World Bank API.
    """
    logging.info(f"Fetching World Bank data for indicator: {indicator}")
    
    # The API can be flaky, so we'll try up to 3 times.
    for attempt in range(3):
        try:
            # The API doesn't have data for the current or future year. Go up to last year.
            end_year = datetime.now().year - 1
            start_year = end_year - 20
            
            # The API expects a comma-separated string of years.
            time_range = ",".join(str(year) for year in range(start_year, end_year + 1))
            
            wb_data = wb.data.DataFrame(indicator, economy=country_code, time=time_range).reset_index()
            
            wb_data.rename(columns={'time': 'year', indicator: indicator}, inplace=True)
            wb_data['year'] = wb_data['year'].str.replace('YR', '').astype(str)
            
            latest_data = wb_data.dropna().sort_values('year', ascending=False)
            
            # If we succeed, return the data and exit the loop.
            return latest_data.to_dict(orient="records")
        
        except Exception as e:
            logging.error(f"World Bank API error (Attempt {attempt + 1}/3): {e}")
            # Wait for 1 second before trying again.
            time.sleep(1)
            
    # If all attempts fail, return None.
    logging.error("All attempts to fetch World Bank data failed.")
    return None

def get_news_data(query: str):
    # This function is working well, no changes needed.
    # ...
    if not newsapi:
        logging.error("NewsAPI client not initialized.")
        return None
    from datetime import timedelta
    logging.info(f"Fetching news from NewsAPI for query: '{query}'")
    try:
        from_date = (datetime.now() - timedelta(days=29)).strftime('%Y-%m-%d')
        all_articles = newsapi.get_everything(q=query, language='en', sort_by='relevancy', from_param=from_date, page_size=20)
        articles = [{"source": article["source"]["name"], "title": article["title"], "url": article["url"], "publishedAt": article["publishedAt"], "content": article.get("content", "")} for article in all_articles["articles"]]
        return articles
    except Exception as e:
        logging.error(f"NewsAPI error for query '{query}': {e}")
        return None