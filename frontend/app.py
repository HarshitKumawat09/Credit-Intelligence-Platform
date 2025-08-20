# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="CredTech Intelligence", page_icon="🤖", layout="wide")

AGENCY_RATINGS = {
    "AAPL": "AA+", "MSFT": "AAA", "GOOGL": "AA+",
    "NVDA": "A-", "JPM": "A-", "TSLA": "BB+"
}

BACKEND_URL = "http://127.0.0.1:8000/api/v1/score"

def get_api_data(ticker: str):
    try:
        response = requests.get(f"{BACKEND_URL}/{ticker}")
        if response.status_code == 500: st.error("An unexpected error occurred in the backend."); return None
        if response.status_code == 404: st.error(f"Could not find data for ticker '{ticker}'."); return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the backend API. Is the backend server running?"); return None

def format_market_cap(mc):
    if mc is None: return "N/A"
    if mc > 1e12: return f"${mc/1e12:.2f} T"
    if mc > 1e9: return f"${mc/1e9:.2f} B"
    if mc > 1e6: return f"${mc/1e6:.2f} M"
    return str(mc)

st.title("Explainable Credit Intelligence Platform")
st.caption("Organized by The Programming Club, IITK | Powered by Deep Root Investments")
st.markdown("---")

st.sidebar.header("Analysis Options")
ticker_input = st.sidebar.text_input("Enter Company Ticker", value="SMCI").upper()
analyze_button = st.sidebar.button("Analyze Creditworthiness", type="primary")
st.sidebar.info("Enter a stock ticker (e.g., AAPL, SMCI, BA) to get its real-time, explainable stability score.")

if analyze_button:
    if not ticker_input:
        st.warning("Please enter a company ticker.")
    else:
        with st.spinner(f"Analyzing {ticker_input}..."):
            api_data = get_api_data(ticker_input)

        if api_data:
            st.header(f"Analysis for {api_data.get('company_name', ticker_input)}")
            
            score_result = api_data['score_result']
            info = api_data.get('company_info', {})

            if score_result.get('assessment_type') == 'Heuristic':
                # --- Heuristic Display ---
                col1, col2, col3, col4, col5 = st.columns(5)
                # --- THIS IS A FIX ---
                col1.metric("Stability Score", score_result['stability_score'], "Heuristic")
                # ------------------
                sentiment = score_result.get('latest_sentiment', 0.0)
                sentiment_text = "Positive" if sentiment > 0.05 else "Negative" if sentiment < -0.05 else "Neutral"
                col2.metric("News Sentiment", f"{sentiment:.2f}", sentiment_text)
                col3.metric("Market Cap", format_market_cap(info.get('marketCap')))
                col4.metric("P/E Ratio", f"{info.get('trailingPE'):.2f}" if info.get('trailingPE') else "N/A")
                col5.metric("S&P Rating", AGENCY_RATINGS.get(ticker_input, "N/A"))

                st.markdown("---")
                st.warning("The ML model could not be trained due to insufficient historical data. A qualitative assessment is provided instead.")

                col1, col2 = st.columns((1, 1))
                with col1:
                    st.subheader("Qualitative Observations")
                    for obs in score_result['explanation']:
                        st.markdown(f"- **{obs['feature']}:** {obs['value']}")
                with col2:
                    st.subheader("Historical Stock Performance (1 Year)")
                    stock_df = pd.DataFrame.from_dict(api_data['stock_history'], orient='index')
                    stock_df.index = pd.to_datetime(stock_df.index)
                    fig_stock = px.line(stock_df, y='Close', title=f"{ticker_input} Closing Price")
                    fig_stock.update_layout(height=400)
                    st.plotly_chart(fig_stock, use_container_width=True)
            else:
                # --- ML Model Display ---
                col1, col2, col3, col4, col5 = st.columns(5)
                # --- THIS IS A FIX ---
                score = score_result['stability_score']
                # ------------------
                col1.metric("Stability Score", score, f"{'Stable' if score > 75 else 'Neutral' if score > 50 else 'Volatile'} Outlook")
                sentiment = score_result.get('latest_sentiment', 0.0)
                sentiment_text = "Positive" if sentiment > 0.05 else "Negative" if sentiment < -0.05 else "Neutral"
                col2.metric("News Sentiment", f"{sentiment:.2f}", sentiment_text)
                col3.metric("Market Cap", format_market_cap(info.get('marketCap')))
                col4.metric("P/E Ratio", f"{info.get('trailingPE'):.2f}" if info.get('trailingPE') else "N/A")
                col5.metric("S&P Rating", AGENCY_RATINGS.get(ticker_input, "N/A"))

                st.markdown("---")
                col1, col2 = st.columns((1, 1))
                with col1:
                    st.subheader("Why this score? (Key Drivers)")
                    explanation_df = pd.DataFrame(score_result['explanation'])
                    explanation_df = explanation_df[explanation_df['impact'].abs() > 0.001]
                    explanation_df['impact_description'] = explanation_df['impact'].apply(lambda x: "Increases Risk" if x > 0 else "Decreases Risk")
                    explanation_df['impact_abs'] = explanation_df['impact'].abs()
                    fig = px.bar(explanation_df, x='impact_abs', y='feature', color='impact_description',
                                 color_discrete_map={'Increases Risk': '#FF4B4B', 'Decreases Risk': '#2ECC71'},
                                 orientation='h', labels={'impact_abs': 'Magnitude of Impact', 'feature': 'Feature'})
                    fig.update_layout(yaxis={'categoryorder':'total ascending'}, title="Feature Impact on Downside Risk", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    st.subheader("Historical Stock Performance (1 Year)")
                    stock_df = pd.DataFrame.from_dict(api_data['stock_history'], orient='index')
                    stock_df.index = pd.to_datetime(stock_df.index)
                    fig_stock = px.line(stock_df, y='Close', title=f"{ticker_input} Closing Price")
                    fig_stock.update_layout(height=400)
                    st.plotly_chart(fig_stock, use_container_width=True)

            st.markdown("---")
            news = api_data.get('recent_news_for_context')
            if news:
                st.subheader("Recent News Headlines")
                for article in news:
                    st.markdown(f"**[{article['title']}]({article['url']})**  \n*Source: {article['source']} | Published: {pd.to_datetime(article['publishedAt']).strftime('%Y-%m-%d')}*")
else:
    st.info("Enter a ticker in the sidebar and click 'Analyze' to begin.")
