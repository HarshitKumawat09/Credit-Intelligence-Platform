from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
)


@router.get("/ticker/{ticker}", response_model=List[schemas.Alert])
def get_alerts_by_ticker(
    ticker: str,
    limit: int = 50,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    company = db.query(models.Company).filter(models.Company.ticker == ticker.upper()).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    query = db.query(models.Alert).filter(models.Alert.company_id == company.id)
    if active_only:
        query = query.filter(models.Alert.is_active == True)

    alerts = query.order_by(models.Alert.created_at.desc()).limit(limit).all()
    return alerts
