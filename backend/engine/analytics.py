"""Analytics over the emissions read model.

Everything here goes through `reported()`. Scope 2 is dual-reported, so the emissions
table holds a location-based AND a market-based row for every electricity activity.
Summing the table naively double-counts Scope 2. That guard belongs in one place.
"""
from collections import defaultdict

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models import ActivityData, Calculation, Emission, Facility

# z-score above which a monthly value is flagged. CLAUDE.md section 7.
ANOMALY_Z = 2.0


def reported(*, approved_only: bool = False, basis: str = "location_based") -> Select:
    """Emission rows that count toward the reported inventory, joined to their calculation.

    `basis` picks which Scope 2 methodology is included; Scope 1 and 3 are unaffected.
    """
    other = "market_based" if basis == "location_based" else "location_based"
    stmt = (
        select(Emission, Calculation)
        .join(Calculation, Emission.calculation_id == Calculation.id)
        .where(Calculation.status != "superseded")
        .where(Calculation.methodology != other)
    )
    if approved_only:
        stmt = stmt.where(Calculation.status == "approved")
    return stmt


def _rows(db: Session, **kw) -> list[tuple[Emission, Calculation]]:
    return list(db.execute(reported(**kw)).all())


# --------------------------------------------------------------------------- summary
GHG_CATEGORY = {
    1: "Purchased goods & services", 2: "Capital goods",
    3: "Fuel & energy-related activities", 4: "Upstream transport & distribution",
    5: "Waste generated in operations", 6: "Business travel",
    7: "Employee commuting", 8: "Upstream leased assets",
    9: "Downstream transport & distribution", 10: "Processing of sold products",
    11: "Use of sold products", 12: "End-of-life of sold products",
    13: "Downstream leased assets", 14: "Franchises", 15: "Investments",
}


def summary(db: Session, group_by: str, *, approved_only: bool = False,
            basis: str = "location_based") -> list[dict]:
    """Totals grouped one dimension at a time. Every bucket carries an emission id so the
    dashboard can open the lineage panel from any number on screen."""
    facilities = {f.id: f for f in db.scalars(select(Facility))}
    entities = {f.entity_id: f.entity.name for f in facilities.values()}

    def key_of(e: Emission, c: Calculation):
        if group_by == "scope":
            return (f"Scope {e.scope}", e.scope)
        if group_by == "facility":
            return (facilities[e.facility_id].name, e.facility_id)
        if group_by == "entity":
            return (entities[e.entity_id], e.entity_id)
        if group_by == "month":
            return (e.period_month, e.period_month)
        if group_by == "category":
            if e.scope == 3:
                return (GHG_CATEGORY.get(e.ghg_category, "Other Scope 3"), e.ghg_category)
            return (f"Scope {e.scope} direct/energy", e.scope)
        if group_by == "activity_type":
            return (c.activity.activity_type.replace("_", " "), c.activity.activity_type)
        raise ValueError(f"Unsupported group_by {group_by!r}")

    buckets: dict = defaultdict(
        lambda: {"tco2e": 0.0, "count": 0, "emission_id": None, "_max": 0.0,
                 "quality": defaultdict(int)}
    )
    for e, c in _rows(db, approved_only=approved_only, basis=basis):
        label, gid = key_of(e, c)
        b = buckets[(label, gid)]
        b["tco2e"] += e.tco2e
        b["count"] += 1
        b["quality"][e.data_quality] += 1
        # Largest single contributor is the most useful drill-in target.
        if e.tco2e > b["_max"]:
            b["emission_id"], b["_max"] = e.id, e.tco2e

    total = sum(b["tco2e"] for b in buckets.values()) or 1.0
    out = [
        {
            "group": label,
            "group_id": gid,
            "tco2e": round(b["tco2e"], 1),
            "share_pct": round(100.0 * b["tco2e"] / total, 1),
            "count": b["count"],
            "emission_id": b["emission_id"],
            "primary_pct": round(100.0 * b["quality"]["primary"] / b["count"], 1),
        }
        for (label, gid), b in buckets.items()
    ]
    # Months read chronologically; every other dimension reads largest-first.
    out.sort(key=lambda r: r["group"] if group_by == "month" else -r["tco2e"])
    return out


def scope2_dual(db: Session, *, approved_only: bool = False) -> dict:
    """Location-based vs market-based Scope 2, side by side. A named requirement."""
    def total(basis: str) -> float:
        return sum(
            e.tco2e for e, _ in _rows(db, approved_only=approved_only, basis=basis)
            if e.scope == 2
        )

    loc, mkt = total("location_based"), total("market_based")
    return {
        "location_based_tco2e": round(loc, 1),
        "market_based_tco2e": round(mkt, 1),
        "instrument_benefit_tco2e": round(loc - mkt, 1),
        "note": "Market-based uses contractual instruments (RECs) where held; sites "
                "without an instrument fall back to the grid factor as a residual-mix "
                "proxy, so the two figures converge at those sites.",
    }


def totals(db: Session, *, approved_only: bool = False) -> dict:
    """Headline KPI figures. One pass, so the dashboard is one request for the top row."""
    rows = _rows(db, approved_only=approved_only)
    all_rows = _rows(db)
    facility = db.scalars(select(Facility)).first()
    if facility is None:
        return {
            "gross_tco2e": 0.0, "by_scope": {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0},
            "latest_year": None, "latest_year_tco2e": 0.0, "prior_year_tco2e": 0.0,
            "yoy_change_pct": None, "baseline_year": None, "baseline_is_proxy": False,
            "baseline_tco2e": 0.0, "target_year": 2030, "target_reduction_pct": 0.0,
            "target_tco2e": 0.0, "vs_target_pct": None, "primary_data_pct": 0.0,
            "record_count": 0, "approved_pct": 0.0, "consolidation": "not configured",
            "organization": "Set up your company to begin reporting",
        }
    gross = sum(e.tco2e for e, _ in rows)
    by_scope = defaultdict(float)
    quality = defaultdict(int)
    for e, _ in rows:
        by_scope[e.scope] += e.tco2e
        quality[e.data_quality] += 1

    org = facility.entity.org
    months = sorted({e.period_month for e, _ in rows})
    latest_year = months[-1][:4] if months else None
    baseline_year = str(org.baseline_year)
    year_total = lambda y: sum(e.tco2e for e, _ in rows if e.period_month.startswith(y))

    latest = year_total(latest_year) if latest_year else 0.0
    prior = year_total(str(int(latest_year) - 1)) if latest_year else 0.0
    # Baseline year predates the seeded window, so the first full year in the data stands
    # in for it. Stated on the card rather than silently substituted.
    baseline_in_data = baseline_year in {m[:4] for m in months}
    baseline = year_total(baseline_year) if baseline_in_data else prior
    target = baseline * (1 - org.target_reduction_pct / 100.0)

    n = len(rows) or 1
    return {
        "gross_tco2e": round(gross, 1),
        "by_scope": {f"scope{s}": round(v, 1) for s, v in sorted(by_scope.items())},
        "latest_year": latest_year,
        "latest_year_tco2e": round(latest, 1),
        "prior_year_tco2e": round(prior, 1),
        "yoy_change_pct": round(100.0 * (latest - prior) / prior, 1) if prior else None,
        "baseline_year": int(baseline_year) if baseline_in_data else (
            int(latest_year) - 1 if latest_year else None),
        "baseline_is_proxy": not baseline_in_data,
        "baseline_tco2e": round(baseline, 1),
        "target_year": org.target_year,
        "target_reduction_pct": org.target_reduction_pct,
        "target_tco2e": round(target, 1),
        "vs_target_pct": round(100.0 * (latest - target) / target, 1) if target else None,
        "primary_data_pct": round(100.0 * quality["primary"] / n, 1),
        "record_count": len(rows),
        "approved_pct": round(
            100.0 * sum(1 for _, c in all_rows if c.status == "approved") / (len(all_rows) or 1), 1
        ),
        "consolidation": org.consolidation_method,
        "organization": org.name,
    }


# -------------------------------------------------------------------------- hotspots
def hotspots(db: Session, *, limit: int = 12, approved_only: bool = False) -> dict:
    """Pareto: which facility x activity pairs carry the emissions, with cumulative %."""
    agg: dict[tuple[str, str], dict] = {}
    for e, c in _rows(db, approved_only=approved_only):
        a: ActivityData = c.activity
        key = (a.facility.name, a.activity_type)
        row = agg.setdefault(key, {"tco2e": 0.0, "scope": e.scope, "emission_id": e.id,
                                   "_max": 0.0})
        row["tco2e"] += e.tco2e
        if e.tco2e > row["_max"]:
            row["emission_id"], row["_max"] = e.id, e.tco2e

    ranked = sorted(agg.items(), key=lambda kv: -kv[1]["tco2e"])
    total = sum(v["tco2e"] for v in agg.values()) or 1.0
    out, cumulative = [], 0.0
    for (facility, activity_type), v in ranked:
        cumulative += v["tco2e"]
        out.append({
            "facility": facility,
            "activity_type": activity_type.replace("_", " "),
            "scope": v["scope"],
            "tco2e": round(v["tco2e"], 1),
            "share_pct": round(100.0 * v["tco2e"] / total, 1),
            "cumulative_pct": round(100.0 * cumulative / total, 1),
            "emission_id": v["emission_id"],
        })

    # How few hotspots account for 80% of the inventory - the actual Pareto claim.
    to_80 = next((i + 1 for i, r in enumerate(out) if r["cumulative_pct"] >= 80.0), len(out))
    return {
        "total_tco2e": round(total, 1),
        "hotspots_to_80pct": to_80,
        "hotspot_count": len(out),
        "rows": out[:limit],
    }


# ------------------------------------------------------------------------- anomalies
def anomalies(db: Session, *, threshold: float = ANOMALY_Z,
              approved_only: bool = False) -> list[dict]:
    """z-score outliers within each (facility, activity_type) monthly series.

    The z-score is computed against the series excluding the point under test. Otherwise a
    single large spike inflates the standard deviation it is being measured against and
    hides itself.
    """
    series: dict[tuple[int, str], dict[str, dict]] = defaultdict(dict)
    for e, c in _rows(db, approved_only=approved_only):
        a = c.activity
        point = series[(a.facility_id, a.activity_type)].setdefault(
            e.period_month,
            {"tco2e": 0.0, "emission_id": e.id, "facility": a.facility.name,
             "scope": e.scope, "activity_id": a.id, "unit": a.unit, "quantity": 0.0},
        )
        point["tco2e"] += e.tco2e
        point["quantity"] += a.quantity

    found = []
    for (_, activity_type), months in series.items():
        if len(months) < 6:
            continue  # too short for a meaningful z-score
        values = {m: p["tco2e"] for m, p in months.items()}
        for month, value in values.items():
            rest = [v for m, v in values.items() if m != month]
            mean = sum(rest) / len(rest)
            sd = (sum((v - mean) ** 2 for v in rest) / len(rest)) ** 0.5
            if sd == 0:
                continue
            z = (value - mean) / sd
            if abs(z) < threshold:
                continue
            p = months[month]
            found.append({
                "emission_id": p["emission_id"],
                "activity_id": p["activity_id"],
                "facility": p["facility"],
                "activity_type": activity_type.replace("_", " "),
                "scope": p["scope"],
                "period_month": month,
                "tco2e": round(value, 1),
                "expected_tco2e": round(mean, 1),
                "deviation_pct": round(100.0 * (value - mean) / mean, 1) if mean else None,
                "z_score": round(z, 2),
                "direction": "spike" if z > 0 else "dip",
            })
    found.sort(key=lambda r: -abs(r["z_score"]))
    return found


# -------------------------------------------------------------------------- forecast
def forecast(db: Session, *, approved_only: bool = False) -> dict:
    """Least-squares trend on the monthly series, projected against the target pathway."""
    monthly: dict[str, float] = defaultdict(float)
    for e, _ in _rows(db, approved_only=approved_only):
        monthly[e.period_month] += e.tco2e
    months = sorted(monthly)
    if not months:
        return {"actual": [], "trend": [], "gap_tco2e": 0.0}

    org = db.scalars(select(Facility)).first().entity.org
    n = len(months)
    xs = list(range(n))
    ys = [monthly[m] for m in months]
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    intercept = my - slope * mx

    first_year = int(months[0][:4])
    baseline = sum(v for m, v in monthly.items() if m.startswith(str(first_year)))
    target = baseline * (1 - org.target_reduction_pct / 100.0)

    last_year = int(months[-1][:4])
    years_out = max(org.target_year - last_year, 1)
    # Straight-line target pathway from the baseline year to the target year, sampled at
    # the same monthly granularity as the actuals so both render on one axis.
    span_months = (org.target_year - first_year) * 12 or 1
    pathway = [
        {
            "month": m,
            "target_tco2e": round(
                (baseline / 12) * (1 - (org.target_reduction_pct / 100.0)
                                   * (i / span_months)), 1),
        }
        for i, m in enumerate(months)
    ]
    projected_target_year = sum(
        max(intercept + slope * (n + 12 * (years_out - 1) + i), 0.0) for i in range(12)
    )
    return {
        "baseline_year": first_year,
        "baseline_tco2e": round(baseline, 1),
        "target_year": org.target_year,
        "target_tco2e": round(target, 1),
        "target_reduction_pct": org.target_reduction_pct,
        "monthly_slope_tco2e": round(slope, 2),
        "actual": [{"month": m, "tco2e": round(monthly[m], 1)} for m in months],
        "trend": [{"month": m, "tco2e": round(intercept + slope * i, 1)}
                  for i, m in enumerate(months)],
        "pathway": pathway,
        "projected_target_year_tco2e": round(projected_target_year, 1),
        "gap_tco2e": round(projected_target_year - target, 1),
        "on_track": projected_target_year <= target,
    }


# ---------------------------------------------------------------------- data quality
def data_quality(db: Session) -> dict:
    """Completeness and quality mix per facility x scope, and the gaps behind the number.

    Completeness is measured against expected coverage: a facility should report every
    activity type it reports at all, in every month of that series' reporting window.
    Missing month-activity pairs are the gaps - they are what CSRD readiness turns on.
    """
    activities = list(db.scalars(select(ActivityData)))
    if not activities:
        return {"overall_completeness_pct": 0.0, "by_facility": [], "gaps": []}

    all_months = sorted({a.period_start.strftime("%Y-%m") for a in activities})
    seen: dict[tuple[int, str], set[str]] = defaultdict(set)
    quality: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    scope_of: dict[tuple[int, str], int] = {}
    facility_names: dict[int, str] = {}

    for a in activities:
        month = a.period_start.strftime("%Y-%m")
        seen[(a.facility_id, a.activity_type)].add(month)
        quality[(a.facility_id, a.scope)][a.data_quality] += 1
        scope_of[(a.facility_id, a.activity_type)] = a.scope
        facility_names[a.facility_id] = a.facility.name

    gaps, expected, present = [], 0, 0
    for (facility_id, activity_type), months in seen.items():
        # Only expect months inside this series' own reporting window - a series that
        # started late is not retroactively incomplete.
        window = [m for m in all_months if m >= min(months)]
        expected += len(window)
        present += len(months)
        missing = [m for m in window if m not in months]
        if missing:
            gaps.append({
                "facility": facility_names[facility_id],
                "activity_type": activity_type.replace("_", " "),
                "scope": scope_of[(facility_id, activity_type)],
                "missing_months": missing,
                "missing_count": len(missing),
            })

    by_facility = []
    for (facility_id, scope), mix in sorted(quality.items()):
        n = sum(mix.values())
        facility_gaps = sum(
            g["missing_count"] for g in gaps
            if g["facility"] == facility_names[facility_id] and g["scope"] == scope
        )
        by_facility.append({
            "facility": facility_names[facility_id],
            "scope": scope,
            "records": n,
            "primary_pct": round(100.0 * mix["primary"] / n, 1),
            "secondary_pct": round(100.0 * mix["secondary"] / n, 1),
            "estimated_pct": round(100.0 * mix["estimated"] / n, 1),
            "missing_months": facility_gaps,
        })

    # Activity types a facility never reports at all, which month-level completeness
    # cannot see. Seeded deliberately (Chennai refrigerant) - CLAUDE.md section 6.
    peers: dict[int, set[str]] = defaultdict(set)
    for (facility_id, activity_type) in seen:
        peers[facility_id].add(activity_type)
    universe = set().union(*peers.values()) if peers else set()
    unreported = [
        {"facility": facility_names[fid], "activity_type": t.replace("_", " "),
         "scope": None, "missing_months": ["all"], "missing_count": len(all_months)}
        for fid, types in sorted(peers.items()) for t in sorted(universe - types)
    ]

    gaps.sort(key=lambda g: -g["missing_count"])
    return {
        "overall_completeness_pct": round(100.0 * present / (expected or 1), 1),
        "reporting_months": len(all_months),
        "by_facility": by_facility,
        "gaps": gaps,
        "unreported_series": unreported,
    }
