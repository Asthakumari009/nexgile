"""In-memory abatement scenarios. These endpoints intentionally never persist actuals."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from engine import analytics

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


class ScenarioRequest(BaseModel):
    renewable_electricity_pct: float = Field(0, ge=0, le=100)
    recycled_material_pct: float = Field(0, ge=0, le=100)
    freight_mode_shift_pct: float = Field(0, ge=0, le=100)
    supplier_switch_pct: float = Field(0, ge=0, le=100)


@router.post("")
def model(req: ScenarioRequest, db: Session = Depends(get_db)) -> dict:
    totals = analytics.totals(db)
    scope = totals["by_scope"]
    reductions = {
        "renewable_electricity": scope.get("scope2", 0.0) * req.renewable_electricity_pct / 100 * 0.94,
        "recycled_material": scope.get("scope3", 0.0) * req.recycled_material_pct / 100 * 0.22,
        "freight_mode_shift": scope.get("scope3", 0.0) * req.freight_mode_shift_pct / 100 * 0.08,
        "supplier_switch": scope.get("scope3", 0.0) * req.supplier_switch_pct / 100 * 0.12,
    }
    baseline = totals["gross_tco2e"]
    avoided = min(sum(reductions.values()), baseline)
    result = baseline - avoided
    uncertainty = max(0.04 * result, 0.07 * avoided)
    return {"baseline_tco2e": round(baseline, 1), "result_tco2e": round(result, 1),
            "avoided_tco2e": round(avoided, 1), "reduction_pct": round(100 * avoided / baseline, 1) if baseline else 0.0,
            "reductions": [{"lever": name.replace("_", " "), "tco2e": round(value, 1)} for name, value in reductions.items()],
            "range": {"p5_tco2e": round(max(result - uncertainty, 0), 1), "p50_tco2e": round(result, 1), "p95_tco2e": round(result + uncertainty, 1)},
            "actuals_unchanged": True,
            "assumptions": ["Renewable electricity is modelled at a 94% location-based reduction.",
                            "Material, freight and supplier levers are screening estimates against current Scope 3.",
                            "Scenario output is in memory only. Approved corporate actuals are unchanged."]}
