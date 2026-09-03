"""Organization hierarchy: org > entities > facilities > departments."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Entity, Facility, Organization
from schemas import CompanySetupRequest, FacilityCreateRequest

router = APIRouter(prefix="/api/v1/org", tags=["org"])


@router.post("")
def create_company(req: CompanySetupRequest, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Organization)) is not None:
        raise HTTPException(409, "A company already exists; use its entity to add facilities")
    org = Organization(name=req.company_name, base_currency="INR", baseline_year=2025,
        target_year=2030, target_reduction_pct=42.0, consolidation_method="operational_control")
    db.add(org); db.flush()
    entity = Entity(org_id=org.id, name=req.entity_name, country=req.country.upper(), ownership_pct=100.0)
    db.add(entity); db.commit()
    return {"organization_id": org.id, "entity_id": entity.id}


@router.post("/facilities")
def create_facility(req: FacilityCreateRequest, db: Session = Depends(get_db)) -> dict:
    if db.get(Entity, req.entity_id) is None:
        raise HTTPException(404, f"No entity with id {req.entity_id}")
    facility = Facility(entity_id=req.entity_id, name=req.name, city=req.city,
        country=req.country.upper(), lat=0.0, lon=0.0, facility_type=req.facility_type, floor_area_m2=0.0)
    db.add(facility); db.commit()
    return {"id": facility.id, "name": facility.name}


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
