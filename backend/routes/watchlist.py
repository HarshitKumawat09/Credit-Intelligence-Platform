from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/watchlist",
    tags=["watchlist"],
)


@router.get("/", response_model=List[schemas.WatchlistItem])
def list_watchlist(db: Session = Depends(get_db)):
    items = db.query(models.WatchlistItem).order_by(models.WatchlistItem.created_at.desc()).all()
    return items


@router.post("/", response_model=schemas.WatchlistItem)
def add_to_watchlist(payload: schemas.WatchlistItemCreate, db: Session = Depends(get_db)):
    ticker = payload.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    existing = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == ticker).first()
    if existing is not None:
        return existing

    item = models.WatchlistItem(ticker=ticker)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    ticker_upper = ticker.upper().strip()
    item = db.query(models.WatchlistItem).filter(models.WatchlistItem.ticker == ticker_upper).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Ticker not found in watchlist")

    db.delete(item)
    db.commit()
    return {"message": "Removed from watchlist"}
