"""Analytics router. Thin - the work lives in engine/analytics.py."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from engine import analytics as A

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/hotspots")
def hotspots(limit: int = Query(12, le=100), approved_only: bool = False,
             db: Session = Depends(get_db)) -> dict:
    """Pareto ranking of facility x activity contributors, with cumulative share."""
    return A.hotspots(db, limit=limit, approved_only=approved_only)


@router.get("/anomalies")
def anomalies(threshold: float = A.ANOMALY_Z, limit: int = Query(20, le=200),
              approved_only: bool = False, db: Session = Depends(get_db)) -> dict:
    """Monthly values more than `threshold` standard deviations from their own series."""
    found = A.anomalies(db, threshold=threshold, approved_only=approved_only)
    return {"threshold": threshold, "count": len(found), "rows": found[:limit]}


@router.get("/forecast")
def forecast(approved_only: bool = False, db: Session = Depends(get_db)) -> dict:
    """Linear trend on the monthly series against the target pathway, plus the gap."""
    return A.forecast(db, approved_only=approved_only)


@router.get("/data-quality")
def data_quality(db: Session = Depends(get_db)) -> dict:
    """Completeness by facility and scope, and the specific missing month-series pairs."""
    return A.data_quality(db)
