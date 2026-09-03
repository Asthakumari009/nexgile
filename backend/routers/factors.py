"""Emission factor library, version history, and the impact of a version bump."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from engine import calculator, factors as F
from models import Calculation, EmissionFactor

router = APIRouter(prefix="/api/v1/factors", tags=["factors"])


class ReviseRequest(BaseModel):
    """A restatement: the publisher revises the factor for a period already reported."""

    value_kgco2e: float = Field(gt=0)
    source: str
    version: str | None = None
    uncertainty_pct: float | None = None
    note: str | None = None


def _out(f: EmissionFactor) -> dict:
    return {
        "id": f.id,
        "code": f.code,
        "name": f.name,
        "scope": f.scope,
        "category": f.category,
        "unit": f.unit,
        "value_kgco2e": f.value_kgco2e,
        "source": f.source,
        "version": f.version,
        "valid_from": f.valid_from.isoformat(),
        "valid_to": f.valid_to.isoformat(),
        "uncertainty_pct": f.uncertainty_pct,
        "region": f.region,
        "method": f.method,
        "is_active": f.is_active,
    }


@router.get("")
def list_factors(scope: int | None = None, active: bool | None = None,
                 db: Session = Depends(get_db)) -> dict:
    stmt = select(EmissionFactor)
    if scope is not None:
        stmt = stmt.where(EmissionFactor.scope == scope)
    if active is not None:
        stmt = stmt.where(EmissionFactor.is_active == active)
    rows = list(db.scalars(stmt.order_by(EmissionFactor.scope, EmissionFactor.code)))

    # How many live calculations each version is pinned to. This is what makes the
    # "N calculations affected" banner a fact rather than a decoration.
    usage: dict[int, int] = {}
    for c in db.scalars(select(Calculation).where(Calculation.status != "superseded")):
        usage[c.factor_id] = usage.get(c.factor_id, 0) + 1

    return {
        "count": len(rows),
        "rows": [{**_out(f), "calculations_using": usage.get(f.id, 0)} for f in rows],
    }


@router.get("/{factor_id}/versions")
def versions(factor_id: int, db: Session = Depends(get_db)) -> dict:
    factor = db.get(EmissionFactor, factor_id)
    if factor is None:
        raise HTTPException(404, f"No factor with id {factor_id}")
    family = F.versions(db, factor)
    return {
        "family": {"scope": factor.scope, "category": factor.category,
                   "region": factor.region, "method": factor.method},
        "versions": [_out(f) for f in family],
    }


@router.post("/{factor_id}/revise")
def revise(factor_id: int, req: ReviseRequest, db: Session = Depends(get_db)) -> dict:
    """Publish a restated version of a factor over the same validity window.

    Factors are versioned, never edited: the existing row is kept and deactivated, and a
    new row takes over its window. Calculations already made against the old row keep
    pointing at it - that is what `/impact` then quantifies and `recalculate` resolves.

    A period-succeeding bump (CEA 2023 -> CEA 2024) cannot affect anything, because the
    two windows do not overlap and resolution is by activity period. A restatement can,
    which is why this is the action that drives the impact banner.
    """
    old = db.get(EmissionFactor, factor_id)
    if old is None:
        raise HTTPException(404, f"No factor with id {factor_id}")
    if not old.is_active:
        raise HTTPException(409, f"{old.code} {old.version} is already superseded")

    family = F.versions(db, old)
    next_version = req.version or f"v{len(family) + 1}"
    if any(f.version == next_version for f in family):
        raise HTTPException(409, f"Version {next_version} already exists for this factor")

    new = EmissionFactor(
        code=old.code,
        name=old.name,
        scope=old.scope,
        category=old.category,
        unit=old.unit,
        value_kgco2e=req.value_kgco2e,
        source=req.source,
        version=next_version,
        valid_from=old.valid_from,
        valid_to=old.valid_to,
        uncertainty_pct=req.uncertainty_pct if req.uncertainty_pct is not None
        else old.uncertainty_pct,
        region=old.region,
        method=old.method,
        is_active=True,
    )
    old.is_active = False
    db.add(new)
    db.commit()

    affected = calculator.affected_by(db, old)
    current = sum(c.result_kgco2e for c in affected) / 1000.0
    projected = sum(
        c.converted_quantity * new.value_kgco2e * (c.allocation_pct / 100.0)
        for c in affected
    ) / 1000.0
    return {
        "superseded": _out(old),
        "published": _out(new),
        "calculations_affected": len(affected),
        "current_tco2e": round(current, 1),
        "projected_tco2e": round(projected, 1),
        "delta_tco2e": round(projected - current, 1),
        "delta_pct": round(100.0 * (projected - current) / current, 2) if current else 0.0,
        "note": req.note or "Existing calculations still reference the superseded version "
                            "until they are recalculated.",
    }


@router.get("/{factor_id}/impact")
def impact(factor_id: int, db: Session = Depends(get_db)) -> dict:
    """What recalculating against the currently valid factor would change.

    Read-only: nothing is written. It resolves the replacement factor the same way the
    calculator would, so the previewed delta is the delta you get.
    """
    old = db.get(EmissionFactor, factor_id)
    if old is None:
        raise HTTPException(404, f"No factor with id {factor_id}")

    affected = calculator.affected_by(db, old)
    current_total = sum(c.result_kgco2e for c in affected) / 1000.0

    projected, unresolved, samples = 0.0, [], []
    replacement_ids: set[int] = set()
    for c in affected:
        method = c.methodology if c.methodology in ("location_based", "market_based") else None
        try:
            new_factor = F.resolve_for_activity(db, c.activity, method=method)
        except F.FactorResolutionError as exc:
            unresolved.append({"calculation_id": c.id, "error": str(exc)})
            projected += c.result_kgco2e / 1000.0
            continue
        replacement_ids.add(new_factor.id)
        new_kg = c.converted_quantity * new_factor.value_kgco2e * (c.allocation_pct / 100.0)
        projected += new_kg / 1000.0
        if len(samples) < 5 and new_factor.id != c.factor_id:
            samples.append({
                "calculation_id": c.id,
                "facility": c.activity.facility.name,
                "period_month": c.activity.period_start.strftime("%Y-%m"),
                "from_factor": f"{old.code} {old.version}",
                "to_factor": f"{new_factor.code} {new_factor.version}",
                "old_tco2e": round(c.result_kgco2e / 1000.0, 2),
                "new_tco2e": round(new_kg / 1000.0, 2),
            })

    replacements = [
        _out(f) for f in (db.get(EmissionFactor, i) for i in sorted(replacement_ids))
        if f is not None and f.id != old.id
    ]
    delta = projected - current_total
    return {
        "factor": _out(old),
        "calculations_affected": len(affected),
        "current_tco2e": round(current_total, 1),
        "projected_tco2e": round(projected, 1),
        "delta_tco2e": round(delta, 1),
        "delta_pct": round(100.0 * delta / current_total, 2) if current_total else 0.0,
        "replacement_factors": replacements,
        "would_change": len(samples) > 0 or bool(replacements),
        "samples": samples,
        "unresolved": unresolved,
    }
