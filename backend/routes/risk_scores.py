from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/risk-scores",
    tags=["risk_scores"],
)


@router.get("/ticker/{ticker}", response_model=List[schemas.RiskScore])
def get_risk_scores_by_ticker(
    ticker: str,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    company = db.query(models.Company).filter(models.Company.ticker == ticker.upper()).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    scores = (
        db.query(models.RiskScore)
        .filter(models.RiskScore.company_id == company.id)
        .order_by(models.RiskScore.created_at.desc())
        .limit(limit)
        .all()
    )
    return scores
