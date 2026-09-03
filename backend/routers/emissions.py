"""Emissions router. Lineage first - everything else hangs off it."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from engine import lineage
from models import Emission
from schemas import LineageResponse

router = APIRouter(prefix="/api/v1/emissions", tags=["emissions"])


@router.get("/{emission_id}/lineage", response_model=LineageResponse)
def get_lineage(emission_id: int, db: Session = Depends(get_db)) -> LineageResponse:
    """Full audit trail for one reported emission: source document -> activity data ->
    unit conversion -> emission factor + version -> formula -> result -> approval."""
    emission = db.get(Emission, emission_id)
    if emission is None:
        raise HTTPException(status_code=404, detail=f"No emission with id {emission_id}")
    return LineageResponse(**lineage.build(db, emission))
