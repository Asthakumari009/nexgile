"""THE calculation engine.

Every step is recorded on the calculation row so the lineage endpoint can reconstruct the
chain without recomputing anything. Approved calculations are never mutated - a factor
version bump supersedes them with a new version.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine import factors, units
from models import ActivityData, Calculation, EmissionFactor, Emission

METHODOLOGY_VERSION = "2024.1"

_CONFIDENCE = {"primary": "high", "secondary": "medium", "estimated": "low"}

# Consolidation approach -> share of the facility's emissions the group reports.
_CONSOLIDATION_BASIS = {
    "operational_control": "operational control",
    "equity_share": "equity share",
    "financial_control": "financial control",
}


def _allocation(activity: ActivityData) -> tuple[str, float]:
    """One consolidation approach governs the whole inventory - it lives on the org."""
    entity = activity.facility.entity
    method = entity.org.consolidation_method
    # Control approaches consolidate 100% of a controlled entity; equity share
    # consolidates the ownership percentage.
    pct = 100.0 if method in ("operational_control", "financial_control") else entity.ownership_pct
    return _CONSOLIDATION_BASIS.get(method, method), pct


def _fmt(value: float) -> str:
    """Human-readable number for the formula string shown verbatim in the lineage panel."""
    if value == int(value) and abs(value) < 1e15:
        return f"{int(value):,}"
    if abs(value) < 0.01:
        return f"{value:,.5f}".rstrip("0")
    return f"{value:,.2f}"


def calculate(
    db: Session,
    activity: ActivityData,
    methodology: str,
    actor: str,
    *,
    factor: EmissionFactor | None = None,
    calc_version: int = 1,
) -> Calculation:
    """Run the full chain for one activity row and write the calculation + emission."""
    # 1. Resolve factor (version-aware, region-aware, method-aware).
    method = methodology if methodology in ("location_based", "market_based") else None
    if factor is None:
        factor = factors.resolve_for_activity(db, activity, method=method)

    # 2. Convert units - never silently assume they match.
    multiplier, converted = units.convert(db, activity.quantity, activity.unit, factor.unit)

    # 3. Compute.
    basis, allocation_pct = _allocation(activity)
    result_kgco2e = converted * factor.value_kgco2e * (allocation_pct / 100.0)

    # 4. Record the formula verbatim.
    formula = f"{_fmt(converted)} {factor.unit} x {factor.value_kgco2e} kgCO2e/{factor.unit}"
    if allocation_pct != 100.0:
        formula += f" x {allocation_pct:g}% ({basis})"

    calc = Calculation(
        activity_id=activity.id,
        factor_id=factor.id,
        methodology=methodology,
        methodology_version=METHODOLOGY_VERSION,
        input_quantity=activity.quantity,
        input_unit=activity.unit,
        conversion_multiplier=multiplier,
        converted_quantity=converted,
        converted_unit=factor.unit,
        factor_value=factor.value_kgco2e,
        formula_text=formula,
        result_kgco2e=result_kgco2e,
        # 5. Uncertainty propagates from the factor.
        uncertainty_pct=factor.uncertainty_pct,
        allocation_basis=basis,
        allocation_pct=allocation_pct,
        # 6. New calculations start as drafts.
        calc_version=calc_version,
        status="draft",
        created_by=actor,
        created_at=datetime.utcnow(),
    )
    db.add(calc)
    db.flush()

    # 7. Write the read-model emission row in tCO2e.
    db.add(
        Emission(
            calculation_id=calc.id,
            facility_id=activity.facility_id,
            entity_id=activity.facility.entity_id,
            scope=activity.scope,
            ghg_category=activity.ghg_category,
            period_month=activity.period_start.strftime("%Y-%m"),
            tco2e=result_kgco2e / 1000.0,
            data_quality=activity.data_quality,
            confidence=_CONFIDENCE.get(activity.data_quality, "low"),
        )
    )
    db.flush()
    return calc


def approve(db: Session, calc: Calculation, actor: str) -> Calculation:
    calc.status = "approved"
    calc.approved_by = actor
    calc.approved_at = datetime.utcnow()
    db.flush()
    return calc


def affected_by(db: Session, old_factor: EmissionFactor) -> list[Calculation]:
    """Live (non-superseded) calculations still pinned to a superseded factor version."""
    return list(
        db.scalars(
            select(Calculation).where(
                Calculation.factor_id == old_factor.id,
                Calculation.status != "superseded",
            )
        )
    )


def recalculate(db: Session, calc: Calculation, actor: str) -> Calculation:
    """Supersede a calculation with a new version against the currently valid factor.

    The old row is never mutated beyond its status/pointer - the audit trail keeps both.
    """
    activity = calc.activity
    method = calc.methodology if calc.methodology in ("location_based", "market_based") else None
    new_factor = factors.resolve_for_activity(db, activity, method=method)

    new_calc = calculate(
        db,
        activity,
        calc.methodology,
        actor,
        factor=new_factor,
        calc_version=calc.calc_version + 1,
    )
    calc.status = "superseded"
    calc.superseded_by_id = new_calc.id

    # The old emission row must stop counting, or the dashboard double-counts.
    old_emission = db.scalar(select(Emission).where(Emission.calculation_id == calc.id))
    if old_emission is not None:
        db.delete(old_emission)

    db.flush()
    return new_calc
