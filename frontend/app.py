# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="CredTech Intelligence", page_icon="🤖", layout="wide")

# --- BACKEND API ---
BACKEND_URL = "http://127.0.0.1:8000/api/v1/score"

# --- HELPER FUNCTIONS ---
def get_api_data(ticker: str):
    # ... (this function is unchanged)
    try:
        response = requests.get(f"{BACKEND_URL}/{ticker}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the backend API: {e}")
        return None

def format_market_cap(mc):
    # Helper to format large numbers
    if mc is None: return "N/A"
    if mc > 1e12: return f"${mc/1e12:.2f} T"
    if mc > 1e9: return f"${mc/1e9:.2f} B"
    if mc > 1e6: return f"${mc/1e6:.2f} M"
    return str(mc)

# --- HEADER ---
st.title("Explainable Credit Intelligence Platform")
st.caption("Organized by The Programming Club, IITK | Powered by Deep Root Investments")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("Analysis Options")
ticker_input = st.sidebar.text_input("Enter Company Ticker", value="NVDA").upper()
analyze_button = st.sidebar.button("Analyze Creditworthiness", type="primary")
st.sidebar.info("Enter a stock ticker (e.g., AAPL, MSFT, NVDA) to get its real-time, explainable credit score.")

# --- MAIN DASHBOARD ---
if analyze_button:
    if not ticker_input:
        st.warning("Please enter a company ticker.")
    else:
        with st.spinner(f"Analyzing {ticker_input}... This is the first run, so it includes model training and may take up to a minute."):
            api_data = get_api_data(ticker_input)

        if api_data:
            st.header(f"Analysis for {api_data.get('company_name', ticker_input)}")
            
            # --- ROW 1: SCORE & KEY METRICS ---
            col1, col2, col3, col4 = st.columns(4)
            score = api_data['score_result']['credit_score']
            col1.metric("Credit Score", score, f"{'High' if score > 75 else 'Medium' if score > 50 else 'Low'} Risk", help="Score out of 100. Higher is better.")
            
            info = api_data.get('company_info', {})
            col2.metric("Market Cap", format_market_cap(info.get('marketCap')))
            col3.metric("P/E Ratio", f"{info.get('trailingPE'):.2f}" if info.get('trailingPE') else "N/A")
            col4.metric("Dividend Yield", f"{info.get('dividendYield')*100:.2f}%" if info.get('dividendYield') else "N/A")

            st.markdown("---")
            
            # --- ROW 2: EXPLANATION & STOCK CHART ---
            col1, col2 = st.columns((1, 1))

            with col1:
                st.subheader("Why this score? (Key Drivers)")
                explanation_df = pd.DataFrame(api_data['score_result']['explanation'])
                explanation_df['impact_description'] = explanation_df['impact'].apply(lambda x: "Increases Risk" if x > 0 else "Decreases Risk")
                explanation_df['impact_abs'] = explanation_df['impact'].abs()
                
                fig = px.bar(explanation_df, x='impact_abs', y='feature', color='impact_description',
                             color_discrete_map={'Increases Risk': '#FF4B4B', 'Decreases Risk': '#2ECC71'},
                             orientation='h', labels={'impact_abs': 'Magnitude of Impact', 'feature': 'Feature'})
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, title="Feature Impact on Risk Score", height=400)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("Historical Stock Performance (1 Year)")
                stock_df = pd.DataFrame.from_dict(api_data['stock_history'], orient='index')
                stock_df.index = pd.to_datetime(stock_df.index)
                fig_stock = px.line(stock_df, y='Close', title=f"{ticker_input} Closing Price")
                fig_stock.update_layout(height=400)
                st.plotly_chart(fig_stock, use_container_width=True)

            st.markdown("---")

            # --- ROW 3: NEWS ---
            news = api_data.get('recent_news_for_context')
            if news:
                st.subheader("Recent News Headlines")
                for article in news:
                    st.markdown(f"**[{article['title']}]({article['url']})**  \n*Source: {article['source']} | Published: {pd.to_datetime(article['publishedAt']).strftime('%Y-%m-%d')}*")

else:
    st.info("Enter a ticker in the sidebar and click 'Analyze' to begin.")