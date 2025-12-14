from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    name = Column(String)
    sector = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    financial_data = relationship("FinancialData", back_populates="company")
    risk_scores = relationship("RiskScore", back_populates="company")

class FinancialData(Base):
    __tablename__ = "financial_data"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    date = Column(DateTime)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    debt_to_equity = Column(Float)
    current_ratio = Column(Float)
    quick_ratio = Column(Float)
    roa = Column(Float)  # Return on Assets
    roe = Column(Float)  # Return on Equity
    revenue_growth = Column(Float)
    raw_data = Column(JSON)  # Store full API response
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    company = relationship("Company", back_populates="financial_data")

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    score = Column(Float)
    risk_level = Column(String)  # 'LOW', 'MEDIUM', 'HIGH'
    model_version = Column(String)
    feature_importance = Column(JSON)  # Store SHAP values
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    company = relationship("Company", back_populates="risk_scores")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    alert_type = Column(String)  # 'RISK_INCREASE', 'SCORE_THRESHOLD', etc.
    message = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)