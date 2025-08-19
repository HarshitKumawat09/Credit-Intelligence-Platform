# backend/services/scoring_engine.py

import pandas as pd
import numpy as np
import joblib
import os
import logging
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from xgboost import XGBClassifier
import shap

# --- CONSTANTS AND INITIALIZATIONS ---
MODEL_DIR = "backend/ml_models"
MODEL_PATH = os.path.join(MODEL_DIR, "xgb_credit_scorer.joblib")
os.makedirs(MODEL_DIR, exist_ok=True) 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    sia = SentimentIntensityAnalyzer()
except LookupError:
    import nltk
    logging.info("Downloading VADER lexicon...")
    nltk.download('vader_lexicon')
    sia = SentimentIntensityAnalyzer()

# --- FEATURE ENGINEERING ---

def get_sentiment(text: str):
    if not text or not isinstance(text, str):
        return 0.0
    return sia.polarity_scores(text)['compound']

def engineer_features(yf_data: dict, wb_data: list, news_data: list):
    """
    V2: Now includes fundamental metrics and news volume for a richer feature set.
    """
    if 'historical_data' not in yf_data or not yf_data['historical_data']:
        return pd.DataFrame()
        
    stock_df = pd.DataFrame.from_dict(yf_data['historical_data'], orient='index')
    stock_df.index = pd.to_datetime(stock_df.index, utc=True)
    
    # 1. Time-Series Features
    stock_df['price_change_pct_30d'] = stock_df['Close'].pct_change(periods=30).fillna(0) * 100
    stock_df['volatility_30d'] = stock_df['Close'].rolling(window=30).std().fillna(0)
    
    # 2. Macroeconomic Features
    gdp_growth = 0.0
    if wb_data:
        wb_df = pd.DataFrame(wb_data)
        indicator_col = 'NY.GDP.MKTP.KD.ZG'
        if not wb_df.empty and indicator_col in wb_df.columns:
            latest_gdp = wb_df.dropna(subset=[indicator_col]).sort_values('year', ascending=False)
            if not latest_gdp.empty:
                gdp_growth = latest_gdp[indicator_col].iloc[0]
    stock_df['gdp_growth_world'] = gdp_growth

    # 3. Sentiment & News Volume Features
    avg_sentiment = 0.0
    news_volume = 0
    if news_data:
        news_volume = len(news_data)
        sentiments = [get_sentiment(article.get('title')) for article in news_data if article.get('title')]
        if sentiments:
            avg_sentiment = np.mean(sentiments)
    stock_df['avg_news_sentiment_30d'] = avg_sentiment
    stock_df['news_volume_30d'] = news_volume # NEW FEATURE

    # 4. Fundamental Company Features (Static)
    info = yf_data.get('info', {})
    stock_df['trailingPE'] = info.get('trailingPE') or 25 # Use a default PE if none
    stock_df['dividendYield'] = (info.get('dividendYield') or 0) * 100 # as percentage
    
    # Final feature set
    feature_columns = [
        'price_change_pct_30d', 'volatility_30d', 'gdp_growth_world', 
        'avg_news_sentiment_30d', 'news_volume_30d', 'trailingPE', 'dividendYield'
    ]
    features = stock_df[feature_columns].copy()
    features.fillna(0, inplace=True) 
    
    return features

# --- The rest of the scoring_engine.py file remains exactly the same ---
# ... (train_model, get_score_and_explanation functions) ...

# NOTE: Since the rest of the file (train_model and get_score_and_explanation) is identical, 
# you only need to replace the `engineer_features` function.
# I'm providing the full file just in case.

def train_model(features: pd.DataFrame):
    # ... (code is identical to the previous version)
    logging.info("Training new credit scoring model...")
    target_col = 'target'
    features[target_col] = (features['price_change_pct_30d'].shift(-30) < -15).astype(int)
    features.dropna(inplace=True) 

    if len(features) < 50: 
        logging.warning("Not enough data to train model.")
        return None
        
    X = features.drop(target_col, axis=1)
    y = features[target_col]
    
    X.columns = [str(col) for col in X.columns]
    
    model = XGBClassifier(
        objective='binary:logistic', eval_metric='logloss', 
        use_label_encoder=False, n_estimators=100,
        learning_rate=0.1, max_depth=3
    )
    model.fit(X, y)
    
    joblib.dump(model, MODEL_PATH)
    logging.info(f"Model trained and saved to {MODEL_PATH}")
    return model

def get_score_and_explanation(ticker: str, yf_data: dict, wb_data: list, news_data: list):
    # ... (code is identical to the previous version)
    all_features = engineer_features(yf_data, wb_data, news_data)
    
    if all_features.empty:
        return {"error": "Could not engineer features. Source data might be missing."}
    
    latest_features = all_features.iloc[[-1]] 

    if not os.path.exists(MODEL_PATH):
        logging.warning(f"No pre-trained model found. Training new one for {ticker}.")
        model = train_model(all_features.copy())
        if model is None:
            return {"error": "Model training failed due to insufficient data."}
    else:
        model = joblib.load(MODEL_PATH)
    
    latest_features.columns = [str(col) for col in latest_features.columns]

    risk_probability = model.predict_proba(latest_features)[:, 1][0]
    credit_score = int((1 - risk_probability) * 100)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(latest_features)
    
    shap_values_for_class_1 = shap_values[1] if isinstance(shap_values, list) else shap_values
    shap_values_flat = shap_values_for_class_1[0]

    feature_names = latest_features.columns
    feature_values = latest_features.iloc[0].values

    explanation = [{
        "feature": name, "value": round(float(val), 2), "impact": round(float(shap), 2)
    } for name, val, shap in zip(feature_names, feature_values, shap_values_flat)]

    explanation.sort(key=lambda x: abs(x['impact']), reverse=True)
    
    return { "credit_score": credit_score, "explanation": explanation }