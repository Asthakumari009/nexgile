"""Finance view derived from reporting actuals and seeded abatement levers."""
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from engine import analytics
from models import CarbonBudget, Entity, Offset, ReductionLever

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


@router.get("/summary")
def summary(carbon_price: float = Query(3500, ge=0), db: Session = Depends(get_db)) -> dict:
    rows = analytics._rows(db)
    latest_year = max((e.period_month[:4] for e, _ in rows), default="2025")
    actual = defaultdict(float)
    for emission, _ in rows:
        if emission.period_month.startswith(latest_year):
            actual[emission.entity_id] += emission.tco2e
    budgets = {b.entity_id: b for b in db.scalars(select(CarbonBudget).where(CarbonBudget.year == int(latest_year)))}
    entities = {e.id: e for e in db.scalars(select(Entity))}
    budget_rows = []
    for entity_id, actual_tco2e in actual.items():
        stored = budgets.get(entity_id)
        ratio = stored.budget_tco2e / stored.actual_tco2e if stored and stored.actual_tco2e else .94
        budget = actual_tco2e * ratio
        budget_rows.append({"entity": entities[entity_id].name, "actual_tco2e": round(actual_tco2e, 1), "budget_tco2e": round(budget, 1), "variance_tco2e": round(actual_tco2e - budget, 1)})
    levers = []
    for lever in db.scalars(select(ReductionLever).order_by(ReductionLever.potential_tco2e.desc())):
        cost = lever.capex / lever.potential_tco2e if lever.potential_tco2e else 0
        levers.append({"id": lever.id, "name": lever.name, "category": lever.category, "potential_tco2e": lever.potential_tco2e, "capex": lever.capex, "opex_delta": lever.opex_delta, "payback_years": lever.payback_years, "status": lever.status, "owner": lever.owner, "cost_per_tco2e": round(cost, 1)})
    levers.sort(key=lambda item: item["cost_per_tco2e"])
    offsets = [{"project_name": o.project_name, "registry": o.registry, "vintage": o.vintage, "tonnes": o.tonnes, "price_per_tonne": o.price_per_tonne, "status": o.status} for o in db.scalars(select(Offset))]
    total_actual = sum(actual.values())
    return {"year": int(latest_year), "carbon_price": carbon_price, "budget": budget_rows,
            "internal_price_exposure": round(total_actual * carbon_price, 0), "total_actual_tco2e": round(total_actual, 1), "levers": levers, "offsets": offsets,
            "note": "Budget values retain the seeded 6% reduction ratio while actuals use location-based Scope 2 without double counting."}
