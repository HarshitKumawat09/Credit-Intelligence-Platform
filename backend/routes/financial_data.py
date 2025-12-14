from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from datetime import datetime

router = APIRouter(
    prefix="/financial-data",
    tags=["financial_data"]
)

@router.post("/", response_model=schemas.FinancialData)
def create_financial_data(data: schemas.FinancialDataCreate, db: Session = Depends(get_db)):
    """Create new financial data entry"""
    # Verify company exists
    company = db.query(models.Company).filter(models.Company.id == data.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    db_financial_data = models.FinancialData(**data.model_dump())
    db.add(db_financial_data)
    db.commit()
    db.refresh(db_financial_data)
    return db_financial_data

@router.get("/company/{company_id}", response_model=List[schemas.FinancialData])
def get_company_financial_data(
    company_id: int, 
    start_date: datetime = None, 
    end_date: datetime = None,
    db: Session = Depends(get_db)
):
    """Get financial data for a specific company"""
    query = db.query(models.FinancialData).filter(models.FinancialData.company_id == company_id)
    
    if start_date:
        query = query.filter(models.FinancialData.date >= start_date)
    if end_date:
        query = query.filter(models.FinancialData.date <= end_date)
    
    return query.order_by(models.FinancialData.date.desc()).all()

@router.get("/{data_id}", response_model=schemas.FinancialData)
def get_financial_data(data_id: int, db: Session = Depends(get_db)):
    """Get specific financial data entry"""
    financial_data = db.query(models.FinancialData).filter(models.FinancialData.id == data_id).first()
    if financial_data is None:
        raise HTTPException(status_code=404, detail="Financial data not found")
    return financial_data

@router.put("/{data_id}", response_model=schemas.FinancialData)
def update_financial_data(data_id: int, data_update: schemas.FinancialDataCreate, db: Session = Depends(get_db)):
    """Update financial data entry"""
    db_financial_data = db.query(models.FinancialData).filter(models.FinancialData.id == data_id).first()
    if db_financial_data is None:
        raise HTTPException(status_code=404, detail="Financial data not found")
    
    for key, value in data_update.model_dump().items():
        setattr(db_financial_data, key, value)
    
    db.commit()
    db.refresh(db_financial_data)
    return db_financial_data

@router.delete("/{data_id}")
def delete_financial_data(data_id: int, db: Session = Depends(get_db)):
    """Delete financial data entry"""
    db_financial_data = db.query(models.FinancialData).filter(models.FinancialData.id == data_id).first()
    if db_financial_data is None:
        raise HTTPException(status_code=404, detail="Financial data not found")
    
    db.delete(db_financial_data)
    db.commit()
    return {"message": "Financial data deleted successfully"}