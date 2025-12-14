# backend/main.py

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from backend.services.data_fetcher import get_yahoo_finance_data, get_market_sentiment_data, get_news_data, get_fred_data
from backend.services.scoring_engine import get_score_and_explanation, train_technical_model, engineer_features
from backend.tasks.retrain_all import run_retraining_job
from backend.routes import companies, financial_data, risk_scores, alerts, watchlist

from backend import models
from backend.database import engine, get_db
from sqlalchemy.orm import Session
import logging
import pandas as pd
from datetime import datetime
from typing import Optional

# Create database tables
models.Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI(title="CredTech AI API", version="1.0.0")

# Include routers
app.include_router(companies.router, prefix="/api/v1")
app.include_router(financial_data.router, prefix="/api/v1")
app.include_router(risk_scores.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")

def _upsert_company(db: Session, ticker: str, name: Optional[str], sector: Optional[str]) -> models.Company:
    ticker_upper = ticker.upper()
    company = db.query(models.Company).filter(models.Company.ticker == ticker_upper).first()
    if company is None:
        company = models.Company(
            ticker=ticker_upper,
            name=name or ticker_upper,
            sector=sector,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    updated = False
    if name and company.name != name:
        company.name = name
        updated = True
    if sector and company.sector != sector:
        company.sector = sector
        updated = True

    if updated:
        company.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(company)
    return company

def _persist_risk_score(db: Session, company_id: int, score_result: dict):
    score = score_result.get("stability_score")
    if not isinstance(score, (int, float)):
        return

    previous = (
        db.query(models.RiskScore)
        .filter(models.RiskScore.company_id == company_id)
        .order_by(models.RiskScore.created_at.desc())
        .first()
    )

    score_float = float(score)
    risk_level = "LOW" if score_float >= 75 else "MEDIUM" if score_float >= 50 else "HIGH"
    db_score = models.RiskScore(
        company_id=company_id,
        score=score_float,
        risk_level=risk_level,
        model_version="1.0.0",
        feature_importance={"explanation": score_result.get("explanation", [])},
        created_at=datetime.utcnow(),
    )
    db.add(db_score)
    db.commit()

    try:
        # Basic alert rules
        threshold = 50.0
        drop_points = 15.0
        prev_score = float(previous.score) if previous is not None and previous.score is not None else None

        # Risk level alert (most visible in demo)
        existing_risk_level = (
            db.query(models.Alert)
            .filter(models.Alert.company_id == company_id)
            .filter(models.Alert.alert_type == "RISK_LEVEL")
            .filter(models.Alert.is_active == True)
            .first()
        )
        if risk_level in ("MEDIUM", "HIGH"):
            if existing_risk_level is None:
                db.add(models.Alert(
                    company_id=company_id,
                    alert_type="RISK_LEVEL",
                    message=f"Current risk level is {risk_level} (score: {score_float:.1f}).",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ))
        else:
            if existing_risk_level is not None:
                existing_risk_level.is_active = False
                existing_risk_level.resolved_at = datetime.utcnow()

        if score_float < threshold:
            existing = (
                db.query(models.Alert)
                .filter(models.Alert.company_id == company_id)
                .filter(models.Alert.alert_type == "SCORE_THRESHOLD")
                .filter(models.Alert.is_active == True)
                .first()
            )
            if existing is None:
                db.add(models.Alert(
                    company_id=company_id,
                    alert_type="SCORE_THRESHOLD",
                    message=f"Stability score is below {threshold:.0f} (current: {score_float:.1f}).",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ))

        if prev_score is not None and (prev_score - score_float) >= drop_points:
            existing = (
                db.query(models.Alert)
                .filter(models.Alert.company_id == company_id)
                .filter(models.Alert.alert_type == "SCORE_DROP")
                .filter(models.Alert.is_active == True)
                .first()
            )
            if existing is None:
                db.add(models.Alert(
                    company_id=company_id,
                    alert_type="SCORE_DROP",
                    message=f"Stability score dropped by {prev_score - score_float:.1f} points (from {prev_score:.1f} to {score_float:.1f}).",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ))

        db.commit()
    except Exception as e:
        logging.error(f"Failed to create alerts for company_id={company_id}: {e}")

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
        
        if not all_features.empty:
            train_technical_model(all_features, ticker)
            logging.info(f"[BACKGROUND] Retraining for {ticker} completed successfully.")
        else:
            logging.warning(f"[BACKGROUND] Not enough data to retrain model for {ticker}.")
    except Exception as e:
        logging.error(f"[BACKGROUND] An error occurred during retraining for {ticker}: {e}")

@app.get("/api/v1/score/{ticker}")
async def get_credit_score(ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logging.info(f"Received request for ticker: {ticker.upper()}")
    try:
        yf_data = get_yahoo_finance_data(ticker)
        if not yf_data: raise HTTPException(status_code=404, detail=f"Invalid ticker or no data for {ticker}.")
        company_name = yf_data["info"].get("longName", ticker)
        company_sector = yf_data["info"].get("sector")
        market_sentiment = get_market_sentiment_data()
        fred_data = get_fred_data()
        fred_data = fred_data if fred_data is not None else pd.Series(dtype='float64')
        news_data = get_news_data(query=company_name)
    except Exception as e:
        logging.error(f"Data fetching failed: {e}"); raise HTTPException(status_code=500, detail="Failed to fetch data.")

    try:
        company = _upsert_company(db, ticker=ticker, name=company_name, sector=company_sector)
    except Exception as e:
        logging.error(f"Failed to upsert company for {ticker.upper()}: {e}")
        company = None

    result = get_score_and_explanation(
        ticker=ticker, yf_data=yf_data,
        market_sentiment=market_sentiment,
        fred_data=fred_data,
        news_data=news_data or []
    )
    
    if "error" in result or result.get('assessment_type') == 'Heuristic':
        logging.warning(f"Returning known error or heuristic to frontend.")
        return {"ticker": ticker.upper(), "company_name": company_name, "company_info": yf_data.get("info"), "score_result": result, "stock_history": yf_data.get("historical_data"), "recent_news_for_context": news_data[:5] if news_data else []}

    try:
        if company is not None:
            _persist_risk_score(db, company_id=company.id, score_result=result)
    except Exception as e:
        logging.error(f"Failed to persist score for {ticker.upper()}: {e}")
    
    background_tasks.add_task(retrain_model_background, ticker)
    logging.info(f"Scheduled background retraining for {ticker}.")
    return {"ticker": ticker.upper(), "company_name": company_name, "company_info": yf_data.get("info"), "score_result": result, "stock_history": yf_data.get("historical_data"), "recent_news_for_context": news_data[:5] if news_data else []}

@app.post("/api/v1/trigger-retraining-job")
async def trigger_retraining(background_tasks: BackgroundTasks):
    """
    Manually trigger the full retraining job in the background.
    """
    logging.info("Manual retraining job triggered via API endpoint.")
    # Schedule the long-running retraining function as a background task
    background_tasks.add_task(run_retraining_job)
    return {"message": "Accepted. The model retraining job has been started in the background. Check server logs for progress."}

@app.get("/")
def read_root(): return {"message": "CredTech API is running."}