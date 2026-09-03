"""Organization hierarchy: org > entities > facilities > departments."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Organization

router = APIRouter(prefix="/api/v1/org", tags=["org"])


@router.get("/tree")
def tree(db: Session = Depends(get_db)) -> dict:
    org = db.scalars(select(Organization)).first()
    if org is None:
        raise HTTPException(404, "No organization seeded")
    return {
        "id": org.id,
        "name": org.name,
        "base_currency": org.base_currency,
        "baseline_year": org.baseline_year,
        "target_year": org.target_year,
        "target_reduction_pct": org.target_reduction_pct,
        # One consolidation approach governs the whole inventory - GHG Protocol.
        "consolidation_method": org.consolidation_method,
        "entities": [
            {
                "id": e.id,
                "name": e.name,
                "country": e.country,
                "ownership_pct": e.ownership_pct,
                "facilities": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "city": f.city,
                        "country": f.country,
                        "lat": f.lat,
                        "lon": f.lon,
                        "facility_type": f.facility_type,
                        "floor_area_m2": f.floor_area_m2,
                        "departments": [
                            {"id": d.id, "name": d.name, "cost_center": d.cost_center}
                            for d in f.departments
                        ],
                    }
                    for f in e.facilities
                ],
            }
            for e in org.entities
        ],
    }
