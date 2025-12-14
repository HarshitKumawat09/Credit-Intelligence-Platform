from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# Company Schemas
class CompanyBase(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Financial Data Schemas
class FinancialDataBase(BaseModel):
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    roa: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    raw_data: Optional[Dict[str, Any]] = None

class FinancialDataCreate(FinancialDataBase):
    company_id: int
    date: datetime

class FinancialData(FinancialDataBase):
    id: int
    company_id: int
    date: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# Risk Score Schemas
class RiskScoreBase(BaseModel):
    score: float
    risk_level: str
    model_version: str
    feature_importance: Dict[str, Any]

class RiskScoreCreate(RiskScoreBase):
    company_id: int

class RiskScore(RiskScoreBase):
    id: int
    company_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Alert Schemas
class AlertBase(BaseModel):
    alert_type: str
    message: str
    is_active: bool = True

class AlertCreate(AlertBase):
    company_id: int

class Alert(AlertBase):
    id: int
    company_id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Watchlist Schemas
class WatchlistItemBase(BaseModel):
    ticker: str

class WatchlistItemCreate(WatchlistItemBase):
    pass

class WatchlistItem(WatchlistItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True