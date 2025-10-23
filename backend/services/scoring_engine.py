# backend/services/scoring_engine.py

import pandas as pd
import numpy as np
import joblib
import os
import logging
import optuna
from optuna.trial import Trial
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from xgboost import XGBClassifier
import shap
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

MODEL_DIR = "backend/ml_models"; os.makedirs(MODEL_DIR, exist_ok=True) 
optuna.logging.set_verbosity(optuna.logging.WARNING); logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
try: sia = SentimentIntensityAnalyzer()
except LookupError: import nltk; logging.info("Downloading VADER lexicon..."); nltk.download('vader_lexicon'); sia = SentimentIntensityAnalyzer()

def get_sentiment(text: str):
    if not text or not isinstance(text, str): return 0.0
    return sia.polarity_scores(text)['compound']

def engineer_features(yf_data: dict, market_sentiment: float, fred_data: pd.Series, news_data: list):
    if 'historical_data' not in yf_data or not yf_data['historical_data']: return pd.DataFrame()
    stock_df = pd.DataFrame.from_dict(yf_data['historical_data'], orient='index')
    stock_df.index = pd.to_datetime(stock_df.index)
    close_prices = pd.to_numeric(stock_df['Close'], errors='coerce')
    stock_df['Close_raw'] = close_prices
    if fred_data is not None:
        fred_df = pd.DataFrame(fred_data, columns=['treasury_rate_10y'])
        fred_df.index = pd.to_datetime(fred_df.index)
        stock_df = pd.merge(stock_df, fred_df, left_index=True, right_index=True, how='left')
        stock_df['treasury_rate_10y'].ffill(inplace=True)
        stock_df['treasury_rate_change_30d'] = stock_df['treasury_rate_10y'].diff(periods=30).fillna(0)
    else:
        stock_df['treasury_rate_change_30d'] = 0
    stock_df['price_change_pct_7d'] = close_prices.pct_change(periods=7).fillna(0) * 100; stock_df['price_change_pct_30d'] = close_prices.pct_change(periods=30).fillna(0) * 100; stock_df['price_change_pct_90d'] = close_prices.pct_change(periods=90).fillna(0) * 100
    stock_df['volatility_30d'] = close_prices.rolling(window=30).std().fillna(0); stock_df['volatility_90d'] = close_prices.rolling(window=90).std().fillna(0)
    delta = close_prices.diff(); gain = delta.clip(lower=0).fillna(0); loss = -delta.clip(upper=0).fillna(0); avg_gain = gain.rolling(window=14, min_periods=1).mean(); avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan); stock_df['rsi_14d'] = 100 - (100 / (1 + rs)); stock_df['rsi_14d'] = stock_df['rsi_14d'].fillna(50)
    stock_df['ma_90d'] = close_prices.rolling(window=90).mean(); stock_df['price_to_ma_ratio'] = close_prices / stock_df['ma_90d']
    stock_df['market_sentiment_90d'] = market_sentiment
    avg_sentiment, news_volume, negative_event_count = 0.0, 0, 0
    if news_data:
        news_volume = len(news_data); sentiments = [get_sentiment(article.get('title')) for article in news_data if article.get('title')]
        if sentiments: avg_sentiment = np.mean(sentiments)
        negative_keywords = ['downgrade', 'lawsuit', 'fraud', 'restructuring', 'crisis', 'investigation', 'scandal', 'debt']
        for article in news_data:
            title = article.get('title', '').lower()
            if any(keyword in title for keyword in negative_keywords): negative_event_count += 1
    stock_df['avg_news_sentiment_30d'] = avg_sentiment; stock_df['news_volume_30d'] = news_volume; stock_df['negative_event_count'] = negative_event_count
    info = yf_data.get('info', {}); stock_df['trailingPE'] = info.get('trailingPE'); stock_df['dividendYield'] = (info.get('dividendYield') or 0) * 100
    stock_df['debt_to_equity'] = info.get('debtToEquity'); stock_df['cash_per_share'] = info.get('totalCashPerShare')
    feature_columns = ['Close_raw', 'price_change_pct_7d', 'price_change_pct_30d', 'price_change_pct_90d', 'volatility_30d', 'volatility_90d', 'rsi_14d', 'price_to_ma_ratio', 'market_sentiment_90d', 'treasury_rate_change_30d', 'avg_news_sentiment_30d', 'news_volume_30d', 'negative_event_count', 'trailingPE', 'dividendYield', 'debt_to_equity', 'cash_per_share']
    features = stock_df[feature_columns].copy()
    features.replace([np.inf, -np.inf], 0, inplace=True); features.fillna({'price_to_ma_ratio': 1.0}, inplace=True); features.fillna(0, inplace=True) 
    return features

def get_fundamental_score(yf_data: dict):
    info = yf_data.get('info', {}); score = 100; explanation = []
    dte = info.get('debtToEquity')
    if dte is None:
        score -= 25; explanation.append({'feature': 'Debt-to-Equity', 'value': 'N/A', 'impact': 2.0})
    elif dte > 150:
        score -= 50; explanation.append({'feature': 'Debt-to-Equity', 'value': round(dte, 2), 'impact': 4.0})
    elif dte > 80:
        score -= 25; explanation.append({'feature': 'Debt-to-Equity', 'value': round(dte, 2), 'impact': 2.0})
    pe = info.get('trailingPE')
    if pe is None or pe < 0:
        score -= 30; explanation.append({'feature': 'Profitability (P/E)', 'value': pe or 'N/A', 'impact': 3.0})
    cash_ps = info.get('totalCashPerShare')
    if cash_ps is None:
        score -= 15; explanation.append({'feature': 'Cash per Share', 'value': 'N/A', 'impact': 1.5})
    elif cash_ps < 1:
        score -= 10; explanation.append({'feature': 'Cash per Share', 'value': cash_ps, 'impact': 1.0})
    logging.info(f"Fundamental Score calculated: {score}"); return max(0, score), explanation

def get_heuristic_assessment(features: pd.DataFrame, yf_data: dict) -> dict:
    logging.info("ML model training failed. Generating heuristic assessment.")
    score, explanation = get_fundamental_score(yf_data)
    latest_sentiment = features['avg_news_sentiment_30d'].iloc[-1]
    return {"stability_score": "N/A", "explanation": explanation, "assessment_type": "Heuristic", "latest_sentiment": latest_sentiment, "all_features": features.to_dict(orient='index')}

def train_technical_model(features: pd.DataFrame, ticker: str):
    model_path = os.path.join(MODEL_DIR, f"xgb_scorer_{ticker}.joblib")
    logging.info(f"Starting final training for {ticker} with composite risk target...")
    features['future_volatility_30d'] = features['Close_raw'].rolling(window=30).std().shift(-30); features['future_return_30d'] = (features['Close_raw'].shift(-30) / features['Close_raw']) - 1
    stock_volatility_avg = features['volatility_30d'].mean()
    is_negative_return = features['future_return_30d'] < -0.05
    is_high_volatility = features['future_volatility_30d'] > stock_volatility_avg
    features['target'] = (is_negative_return & is_high_volatility).astype(int)
    features.dropna(inplace=True) 
    if len(features) < 100 or features['target'].nunique() < 2:
        logging.warning("Not enough data or only one class present for robust tuning."); return None
    technical_feature_cols = ['price_change_pct_7d', 'price_change_pct_30d', 'price_change_pct_90d', 'volatility_30d', 'volatility_90d', 'rsi_14d', 'price_to_ma_ratio', 'market_sentiment_90d', 'treasury_rate_change_30d', 'avg_news_sentiment_30d', 'news_volume_30d', 'negative_event_count']
    X = features[technical_feature_cols]; y = features['target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum() if (y_train == 1).sum() > 0 else 1
    def objective(trial: Trial) -> float:
        X_train_part, X_val, y_train_part, y_val = train_test_split(X_train, y_train, test_size=0.25, stratify=y_train, random_state=42)
        params = {'objective': 'binary:logistic', 'eval_metric': 'logloss', 'use_label_encoder': False, 'n_estimators': trial.suggest_int('n_estimators', 100, 300, step=50), 'max_depth': trial.suggest_int('max_depth', 3, 7), 'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2), 'subsample': trial.suggest_float('subsample', 0.6, 1.0), 'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0), 'scale_pos_weight': scale_pos_weight}
        model = XGBClassifier(**params); model.fit(X_train_part, y_train_part, verbose=False)
        y_pred_proba = model.predict_proba(X_val)[:, 1]; return float(roc_auc_score(y_val, y_pred_proba))
    study = optuna.create_study(direction="maximize"); study.optimize(objective, n_trials=25)
    best_params = study.best_params; logging.info(f"Best Parameters Found by Optuna: {best_params}")
    final_model = XGBClassifier(objective='binary:logistic', eval_metric='logloss', use_label_encoder=False, scale_pos_weight=scale_pos_weight, **best_params)
    final_model.fit(X_train, y_train)
    if not X_test.empty and y_test.nunique() > 1:
        auc = roc_auc_score(y_test, final_model.predict_proba(X_test)[:, 1])
        logging.info(f"--- MODEL VALIDATION METRICS (FINAL) ---"); logging.info(f"Final Test Set AUC Score for {ticker}: {auc:.4f}"); logging.info(f"-------------------------------------------")
    logging.info(f"Training final model for {ticker} on all data..."); final_model.fit(X, y)
    joblib.dump(final_model, model_path); logging.info(f"Model for {ticker} trained and saved to {model_path}"); return final_model

def get_score_and_explanation(ticker: str, yf_data: dict, market_sentiment: float, fred_data: pd.Series, news_data: list):
    all_features = engineer_features(yf_data, market_sentiment, fred_data, news_data)
    if all_features.empty: return {"error": "Could not engineer features."}

    latest_sentiment = all_features['avg_news_sentiment_30d'].iloc[-1]
    fundamental_score, fund_explanation = get_fundamental_score(yf_data)
    model_path = os.path.join(MODEL_DIR, f"xgb_scorer_{ticker}.joblib")
    model = None
    if not os.path.exists(model_path):
        model = train_technical_model(all_features.copy(), ticker=ticker)
    else:
        model = joblib.load(model_path)
    
    if model is None:
        return get_heuristic_assessment(all_features, yf_data)

    technical_feature_cols = model.get_booster().feature_names
    latest_tech_features = all_features[technical_feature_cols].iloc[-1:]
    
    risk_probability = model.predict_proba(latest_tech_features)[:, 1][0]
    technical_penalty = int(risk_probability * 50)
    logging.info(f"Technical model risk probability: {risk_probability:.2f}, resulting in penalty of: {technical_penalty}")

    final_score = fundamental_score - technical_penalty
    final_score = max(0, final_score)

    explainer = shap.TreeExplainer(model); shap_values = explainer.shap_values(latest_tech_features)
    shap_values_for_class_1 = shap_values[0] if len(np.array(shap_values).shape) == 3 else shap_values
    shap_values_flat = shap_values_for_class_1[0]

    feature_names = latest_tech_features.columns; feature_values = latest_tech_features.iloc[0].values
    explanation = [{"feature": name, "value": round(float(val), 2), "impact": round(float(shap), 2)} for name, val, shap in zip(feature_names, feature_values, shap_values_flat)]
    
    for item in fund_explanation: explanation.append(item)
    explanation.sort(key=lambda x: abs(x['impact']), reverse=True)
    
    return {"stability_score": final_score, "technical_score": int((1-risk_probability)*100), "fundamental_score": fundamental_score, "explanation": explanation, "assessment_type": "ML_Model", "latest_sentiment": latest_sentiment, "all_features": all_features.to_dict(orient='index')}