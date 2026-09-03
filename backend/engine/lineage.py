"""Builds the audit trail for a single reported emission.

The chain is reconstructed entirely from what the calculator recorded at the time - no
value here is recomputed. If a factor was later superseded, this still shows the factor
version that actually produced the number, which is the whole point of an audit trail.
"""
from sqlalchemy.orm import Session

from engine.calculator import fmt_number
from models import Calculation, Emission

_MONTH = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_METHOD_LABEL = {
    "location_based": "location-based",
    "market_based": "market-based",
    "spend_based": "spend-based",
    "activity_based": "activity-based",
    "supplier_specific": "supplier-specific",
    "distance_based": "distance-based",
}


def _period(period_month: str) -> str:
    year, month = period_month.split("-")
    return f"{_MONTH[int(month) - 1]} {year}"


def _stamp(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else ""


def build(db: Session, emission: Emission) -> dict:
    calc: Calculation = emission.calculation
    activity = calc.activity
    factor = calc.factor
    facility = activity.facility
    evidence = activity.evidence

    method = _METHOD_LABEL.get(calc.methodology, calc.methodology)
    chain = [
        {
            "step": "reported_value",
            "label": "Reported emission",
            "value": f"{emission.tco2e:,.1f} tCO2e",
            "detail": f"Scope {emission.scope}"
                      + (f", {method}" if emission.scope == 2 else "")
                      + f", {_period(emission.period_month)} | {facility.name}",
        },
        {
            "step": "calculation",
            "label": f"Calculation #{calc.id} v{calc.calc_version}",
            "value": calc.formula_text,
            "detail": f"Methodology: {calc.methodology} v{calc.methodology_version}"
                      f" | Allocation: {calc.allocation_pct:g}% {calc.allocation_basis}"
                      f" | Status: {calc.status}",
        },
    ]

    # Unit conversion is always shown, including the identity case - "we checked and they
    # matched" is a different statement from silence.
    if calc.conversion_multiplier == 1.0:
        chain.append({
            "step": "unit_conversion",
            "label": "Unit conversion",
            "value": f"{fmt_number(calc.input_quantity)} {calc.input_unit} "
                     f"(no conversion required)",
            "detail": f"Activity unit already matches the factor denominator "
                      f"({factor.unit})",
        })
    else:
        chain.append({
            "step": "unit_conversion",
            "label": "Unit conversion",
            "value": f"{fmt_number(calc.input_quantity)} {calc.input_unit} -> "
                     f"{fmt_number(calc.converted_quantity)} {calc.converted_unit}",
            "detail": f"multiplier {calc.conversion_multiplier:g}",
        })

    chain.append({
        "step": "emission_factor",
        "label": f"{factor.code} {factor.version}",
        "value": f"{factor.value_kgco2e} kgCO2e/{factor.unit}",
        "detail": f"{factor.source} | valid {factor.valid_from} to {factor.valid_to}"
                  f" | uncertainty +/-{factor.uncertainty_pct:g}%"
                  + (f" | region {factor.region}" if factor.region else "")
                  + ("" if factor.is_active else " | SUPERSEDED VERSION"),
    })

    chain.append({
        "step": "activity_data",
        "label": f"Activity record #{activity.id}",
        "value": f"{fmt_number(activity.quantity)} {activity.unit} "
                 f"{activity.activity_type.replace('_', ' ')}",
        "detail": f"{activity.description} | Source: {activity.data_source}"
                  f" | Quality: {activity.data_quality}"
                  f" | Period {activity.period_start} to {activity.period_end}",
    })

    if evidence is not None:
        chain.append({
            "step": "evidence",
            "label": evidence.filename,
            "value": f"sha256 {evidence.sha256[:12]}...",
            "detail": f"{evidence.doc_type.replace('_', ' ')}"
                      + (f" | {evidence.page_ref}" if evidence.page_ref else "")
                      + f" | Uploaded by {evidence.uploaded_by}"
                      f" {evidence.uploaded_at:%Y-%m-%d}",
            "url": evidence.file_path,
        })
    else:
        # A missing document is part of the audit trail, not a reason to hide the step.
        chain.append({
            "step": "evidence",
            "label": "No source document attached",
            "value": "-",
            "detail": f"This activity was recorded from {activity.data_source} without a "
                      f"supporting document. Data quality: {activity.data_quality}.",
        })

    if calc.status == "approved":
        chain.append({
            "step": "approval",
            "label": "Approved",
            "value": calc.approved_by,
            "detail": _stamp(calc.approved_at),
        })
    elif calc.status == "superseded":
        chain.append({
            "step": "approval",
            "label": "Superseded",
            "value": f"replaced by calculation #{calc.superseded_by_id}",
            "detail": "Retained unchanged for audit. This version no longer counts "
                      "toward reported totals.",
        })
    else:
        chain.append({
            "step": "approval",
            "label": "Pending approval",
            "value": "-",
            "detail": f"Created by {calc.created_by} {_stamp(calc.created_at)}. "
                      "Not yet signed off.",
        })

    return {
        "emission": {
            "id": emission.id,
            "tco2e": round(emission.tco2e, 1),
            "period": emission.period_month,
            "facility": facility.name,
            "scope": emission.scope,
        },
        "chain": chain,
        "assumptions": _assumptions(calc),
        "uncertainty_pct": calc.uncertainty_pct,
        "confidence": emission.confidence,
    }


def _assumptions(calc: Calculation) -> list[str]:
    """Stated from the data that actually produced the number, not a fixed list."""
    activity = calc.activity
    factor = calc.factor
    org = activity.facility.entity.org
    out = [f"{calc.allocation_basis.capitalize()} consolidation"]

    if calc.allocation_pct != 100.0:
        out.append(
            f"{activity.facility.entity.name} is {activity.facility.entity.ownership_pct:g}% "
            f"owned; {calc.allocation_pct:g}% of this facility's emissions are consolidated"
        )
    else:
        out.append(
            f"{activity.facility.entity.name} is wholly owned and consolidated at 100%"
        )

    if calc.methodology == "location_based":
        out.append("Grid factor applied at national level, no state-level split available")
    elif calc.methodology == "market_based":
        if factor.method == "market_based":
            out.append("Market-based factor from a contractual instrument (REC) held "
                       "for this site")
        else:
            out.append("No contractual instrument held at this site; residual mix "
                       "proxied by the location-based grid factor")
    elif calc.methodology == "spend_based":
        out.append("Spend-based EEIO proxy; accuracy is limited by the granularity of "
                   "the spend category")

    if activity.data_quality == "estimated":
        out.append("Activity data is an estimate, not a metered or invoiced quantity")
    if activity.evidence_id is None:
        out.append("No source document attached to this activity record")

    out.append(f"Emission factors are publicly-cited approximations used for "
               f"demonstration, not a licensed factor library "
               f"(this factor: {factor.source})")
    out.append(f"Reporting boundary: {org.name}, baseline {org.baseline_year}, "
               f"target {org.target_reduction_pct:g}% by {org.target_year}")
    return out
