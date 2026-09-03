"""Emissions router. Lineage first - everything else hangs off it."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from engine import analytics, lineage
from models import Emission
from schemas import LineageResponse

router = APIRouter(prefix="/api/v1/emissions", tags=["emissions"])

GROUP_BY = ("scope", "facility", "entity", "category", "month", "activity_type")


@router.get("/summary")
def summary(
    group_by: str = Query("scope"),
    approved_only: bool = False,
    basis: str = Query("location_based", pattern="^(location_based|market_based)$"),
    db: Session = Depends(get_db),
) -> dict:
    """Totals for one grouping dimension. `basis` selects the Scope 2 methodology; the
    emissions table holds both, so summing it unfiltered would double-count Scope 2."""
    if group_by not in GROUP_BY:
        raise HTTPException(400, f"group_by must be one of {', '.join(GROUP_BY)}")
    return {
        "group_by": group_by,
        "basis": basis,
        "approved_only": approved_only,
        "rows": analytics.summary(db, group_by, approved_only=approved_only, basis=basis),
    }


@router.get("/totals")
def totals(approved_only: bool = False, db: Session = Depends(get_db)) -> dict:
    """Headline KPI figures for the dashboard top row."""
    return analytics.totals(db, approved_only=approved_only)


@router.get("/scope2")
def scope2(approved_only: bool = False, db: Session = Depends(get_db)) -> dict:
    """Scope 2 location-based vs market-based, side by side."""
    return analytics.scope2_dual(db, approved_only=approved_only)


@router.get("")
def list_emissions(
    scope: int | None = None,
    facility_id: int | None = None,
    period: str | None = Query(None, description="YYYY-MM"),
    basis: str = Query("location_based", pattern="^(location_based|market_based)$"),
    approved_only: bool = False,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    stmt = analytics.reported(approved_only=approved_only, basis=basis)
    if scope is not None:
        stmt = stmt.where(Emission.scope == scope)
    if facility_id is not None:
        stmt = stmt.where(Emission.facility_id == facility_id)
    if period:
        stmt = stmt.where(Emission.period_month == period)
    rows = db.execute(stmt.order_by(Emission.tco2e.desc()).limit(limit)).all()
    return {
        "count": len(rows),
        "rows": [
            {
                "id": e.id,
                "scope": e.scope,
                "period_month": e.period_month,
                "facility": c.activity.facility.name,
                "activity_type": c.activity.activity_type.replace("_", " "),
                "tco2e": round(e.tco2e, 2),
                "methodology": c.methodology,
                "data_quality": e.data_quality,
                "confidence": e.confidence,
                "status": c.status,
                "calculation_id": c.id,
            }
            for e, c in rows
        ],
    }


@router.get("/{emission_id}/lineage", response_model=LineageResponse)
def get_lineage(emission_id: int, db: Session = Depends(get_db)) -> LineageResponse:
    """Full audit trail for one reported emission: source document -> activity data ->
    unit conversion -> emission factor + version -> formula -> result -> approval."""
    emission = db.get(Emission, emission_id)
    if emission is None:
        raise HTTPException(status_code=404, detail=f"No emission with id {emission_id}")
    return LineageResponse(**lineage.build(db, emission))
