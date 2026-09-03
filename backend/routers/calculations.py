"""Calculations: run, approve, recalculate. Approved rows are never mutated."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from engine import calculator
from models import ActivityData, Calculation, Emission, EmissionFactor

router = APIRouter(prefix="/api/v1/calculations", tags=["calculations"])

VALID_METHODOLOGIES = ("location_based", "market_based", "spend_based",
                       "activity_based", "supplier_specific", "distance_based")


class CalculateRequest(BaseModel):
    activity_id: int
    methodology: str = "activity_based"
    actor: str = "api.user"


class RecalculateRequest(BaseModel):
    factor_id: int | None = None
    calculation_ids: list[int] | None = None
    actor: str = "api.user"


def _out(c: Calculation, emission_id: int | None = None) -> dict:
    return {
        "id": c.id,
        "activity_id": c.activity_id,
        "factor_id": c.factor_id,
        "factor_code": c.factor.code,
        "factor_version": c.factor.version,
        "methodology": c.methodology,
        "methodology_version": c.methodology_version,
        "input_quantity": c.input_quantity,
        "input_unit": c.input_unit,
        "conversion_multiplier": c.conversion_multiplier,
        "converted_quantity": c.converted_quantity,
        "converted_unit": c.converted_unit,
        "factor_value": c.factor_value,
        "formula_text": c.formula_text,
        "tco2e": round(c.result_kgco2e / 1000.0, 3),
        "uncertainty_pct": c.uncertainty_pct,
        "allocation_basis": c.allocation_basis,
        "allocation_pct": c.allocation_pct,
        "calc_version": c.calc_version,
        "status": c.status,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "approved_by": c.approved_by,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "superseded_by_id": c.superseded_by_id,
        "emission_id": emission_id,
    }


def _emission_id(db: Session, calc_id: int) -> int | None:
    e = db.scalar(select(Emission).where(Emission.calculation_id == calc_id))
    return e.id if e else None


@router.get("")
def list_calculations(status: str | None = None, activity_id: int | None = None,
                      limit: int = Query(100, le=1000), db: Session = Depends(get_db)) -> dict:
    stmt = select(Calculation)
    if status:
        stmt = stmt.where(Calculation.status == status)
    if activity_id is not None:
        stmt = stmt.where(Calculation.activity_id == activity_id)
    rows = list(db.scalars(stmt.order_by(Calculation.id.desc()).limit(limit)))
    emissions = {
        e.calculation_id: e.id
        for e in db.scalars(
            select(Emission).where(Emission.calculation_id.in_([c.id for c in rows]))
        )
    } if rows else {}
    return {"count": len(rows), "rows": [_out(c, emissions.get(c.id)) for c in rows]}


@router.post("")
def create(req: CalculateRequest, db: Session = Depends(get_db)) -> dict:
    if req.methodology not in VALID_METHODOLOGIES:
        raise HTTPException(400, f"methodology must be one of {', '.join(VALID_METHODOLOGIES)}")
    activity = db.get(ActivityData, req.activity_id)
    if activity is None:
        raise HTTPException(404, f"No activity with id {req.activity_id}")
    calc = calculator.calculate(db, activity, req.methodology, req.actor)
    db.commit()
    return _out(calc, _emission_id(db, calc.id))


@router.post("/{calc_id}/approve")
def approve(calc_id: int, actor: str = Query("s.mehta"), db: Session = Depends(get_db)) -> dict:
    calc = db.get(Calculation, calc_id)
    if calc is None:
        raise HTTPException(404, f"No calculation with id {calc_id}")
    if calc.status == "superseded":
        raise HTTPException(409, "A superseded calculation cannot be approved")
    if calc.status == "approved":
        return _out(calc, _emission_id(db, calc.id))
    calculator.approve(db, calc, actor)
    db.commit()
    return _out(calc, _emission_id(db, calc.id))


@router.post("/recalculate")
def recalculate(req: RecalculateRequest, db: Session = Depends(get_db)) -> dict:
    """Supersede calculations with new versions against the currently valid factor.

    Pass `factor_id` to recalculate everything still pinned to that factor version, or
    `calculation_ids` for a specific set. Old rows are kept and marked superseded.
    """
    if req.factor_id is None and not req.calculation_ids:
        raise HTTPException(400, "Provide either factor_id or calculation_ids")

    if req.factor_id is not None:
        factor = db.get(EmissionFactor, req.factor_id)
        if factor is None:
            raise HTTPException(404, f"No factor with id {req.factor_id}")
        targets = calculator.affected_by(db, factor)
    else:
        targets = [db.get(Calculation, i) for i in req.calculation_ids]
        missing = [i for i, c in zip(req.calculation_ids, targets) if c is None]
        if missing:
            raise HTTPException(404, f"No calculation(s) with id {missing}")
        targets = [c for c in targets if c.status != "superseded"]

    before = sum(c.result_kgco2e for c in targets) / 1000.0
    changes = []
    for calc in targets:
        old_tco2e = calc.result_kgco2e / 1000.0
        old_label = f"{calc.factor.code} {calc.factor.version}"
        new_calc = calculator.recalculate(db, calc, req.actor)
        changes.append({
            "old_calculation_id": calc.id,
            "new_calculation_id": new_calc.id,
            "calc_version": new_calc.calc_version,
            "facility": new_calc.activity.facility.name,
            "period_month": new_calc.activity.period_start.strftime("%Y-%m"),
            "from_factor": old_label,
            "to_factor": f"{new_calc.factor.code} {new_calc.factor.version}",
            "old_tco2e": round(old_tco2e, 2),
            "new_tco2e": round(new_calc.result_kgco2e / 1000.0, 2),
        })
    after = sum(c["new_tco2e"] for c in changes)
    db.commit()
    return {
        "recalculated": len(changes),
        "before_tco2e": round(before, 1),
        "after_tco2e": round(after, 1),
        "delta_tco2e": round(after - before, 1),
        "delta_pct": round(100.0 * (after - before) / before, 2) if before else 0.0,
        "note": "Superseded calculations are retained unchanged; new versions carry the "
                "new factor. Nothing was overwritten.",
        "changes": changes[:50],
    }


@router.get("/{calc_id}")
def get_calculation(calc_id: int, db: Session = Depends(get_db)) -> dict:
    calc = db.get(Calculation, calc_id)
    if calc is None:
        raise HTTPException(404, f"No calculation with id {calc_id}")
    return _out(calc, _emission_id(db, calc.id))
