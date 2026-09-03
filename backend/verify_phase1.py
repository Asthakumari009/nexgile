"""Phase 1 gate: rebuild the DB, assert the engine is right, print totals per scope.

Run:  python backend/verify_phase1.py
This is the one runnable check for the calculation chain. If it passes, the numbers on
the dashboard are reconstructible.
"""
import os
from collections import defaultdict

from sqlalchemy import select

from database import DB_PATH, SessionLocal
from models import ActivityData, Calculation, EmissionFactor, Emission, Facility
from seed import seed_if_empty


def rebuild() -> None:
    if DB_PATH.exists():
        os.remove(DB_PATH)
    seed_if_empty()


def main() -> None:
    rebuild()
    db = SessionLocal()

    activities = list(db.scalars(select(ActivityData)))
    calcs = list(db.scalars(select(Calculation)))
    emissions = list(db.scalars(select(Emission)))
    facilities = {f.id: f for f in db.scalars(select(Facility))}

    # Scope 2 is dual-reported, so an emission row alone is ambiguous. Join to the
    # calculation to know which reporting basis it belongs to.
    basis = {c.id: c.methodology for c in calcs}

    by_scope: dict[str, float] = defaultdict(float)
    by_scope_year: dict[tuple[str, str], float] = defaultdict(float)
    by_facility: dict[str, float] = defaultdict(float)
    by_category: dict[int, float] = defaultdict(float)

    for e in emissions:
        method = basis[e.calculation_id]
        if e.scope == 2:
            key = "Scope 2 (location-based)" if method == "location_based" \
                else "Scope 2 (market-based)"
        else:
            key = f"Scope {e.scope}"
        by_scope[key] += e.tco2e
        by_scope_year[(key, e.period_month[:4])] += e.tco2e
        # Headline footprint uses location-based Scope 2, per GHG Protocol convention.
        if not (e.scope == 2 and method == "market_based"):
            by_facility[facilities[e.facility_id].name] += e.tco2e
            if e.scope == 3:
                by_category[e.ghg_category] += e.tco2e

    def line(char="-", n=78):
        print(char * n)

    print()
    line("=")
    print("NEXGILE DECARBX - PHASE 1 VERIFICATION")
    line("=")
    print(f"  activity_data rows : {len(activities):>6}")
    print(f"  calculations       : {len(calcs):>6}")
    print(f"  emissions rows     : {len(emissions):>6}")
    print(f"  emission_factors   : {len(list(db.scalars(select(EmissionFactor)))):>6}")
    print(f"  approved calcs     : {sum(1 for c in calcs if c.status == 'approved'):>6}")
    print(f"  draft calcs        : {sum(1 for c in calcs if c.status == 'draft'):>6}")

    print()
    line("=")
    print("TOTAL tCO2e PER SCOPE  (Jan 2024 - Dec 2025, 24 months)")
    line("=")
    print(f"  {'Basis':<32}{'2024':>14}{'2025':>14}{'TOTAL':>16}")
    line()
    order = ["Scope 1", "Scope 2 (location-based)", "Scope 2 (market-based)", "Scope 3"]
    for key in order:
        y24 = by_scope_year[(key, "2024")]
        y25 = by_scope_year[(key, "2025")]
        print(f"  {key:<32}{y24:>14,.1f}{y25:>14,.1f}{by_scope[key]:>16,.1f}")
    line()

    headline = by_scope["Scope 1"] + by_scope["Scope 2 (location-based)"] + by_scope["Scope 3"]
    market = by_scope["Scope 1"] + by_scope["Scope 2 (market-based)"] + by_scope["Scope 3"]
    h24 = (by_scope_year[("Scope 1", "2024")]
           + by_scope_year[("Scope 2 (location-based)", "2024")]
           + by_scope_year[("Scope 3", "2024")])
    h25 = (by_scope_year[("Scope 1", "2025")]
           + by_scope_year[("Scope 2 (location-based)", "2025")]
           + by_scope_year[("Scope 3", "2025")])
    print(f"  {'GROSS TOTAL (location-based)':<32}{h24:>14,.1f}{h25:>14,.1f}{headline:>16,.1f}")
    print(f"  {'GROSS TOTAL (market-based)':<32}{'':>14}{'':>14}{market:>16,.1f}")
    line()
    for key in order:
        if key == "Scope 2 (market-based)":
            continue
        print(f"  {key:<32}{by_scope[key] / headline * 100:>10.1f}% of gross")

    print()
    line("=")
    print("BY FACILITY  (location-based, after consolidation allocation)")
    line("=")
    for name, val in sorted(by_facility.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<32}{val:>16,.1f} tCO2e{val / headline * 100:>8.1f}%")

    print()
    line("=")
    print("SCOPE 3 BY GHG CATEGORY")
    line("=")
    cat_names = {1: "1  Purchased goods and services", 4: "4  Upstream transport",
                 5: "5  Waste generated in operations", 6: "6  Business travel",
                 7: "7  Employee commuting"}
    for cat, val in sorted(by_category.items(), key=lambda kv: -kv[1]):
        print(f"  {cat_names.get(cat, cat):<32}{val:>16,.1f} tCO2e")

    # ---------------------------------------------------------------- assertions
    print()
    line("=")
    print("ENGINE ASSERTIONS")
    line("=")

    # 1. A calculation is reproducible by hand, end to end.
    hyd = next(f for f in facilities.values() if f.name == "Hyderabad Plant")
    act = db.scalar(
        select(ActivityData).where(
            ActivityData.facility_id == hyd.id,
            ActivityData.activity_type == "purchased_electricity",
            ActivityData.period_start == __import__("datetime").date(2025, 7, 1),
        )
    )
    calc = db.scalar(
        select(Calculation).where(
            Calculation.activity_id == act.id, Calculation.methodology == "location_based"
        )
    )
    expected = act.quantity * 1000 * 0.716 * 1.0
    assert abs(calc.result_kgco2e - expected) < 1e-6, (calc.result_kgco2e, expected)
    assert calc.conversion_multiplier == 1000.0
    assert calc.factor.code == "EF-GRID-IN-02"
    print(f"  [ok] hand-check  {act.quantity:,.0f} MWh x 1000 x 0.716 = "
          f"{calc.result_kgco2e:,.1f} kgCO2e  ({calc.result_kgco2e / 1000:,.1f} tCO2e)")
    print(f"       formula_text stored: {calc.formula_text}")

    # 2. Units are converted, never assumed.
    assert all(c.converted_unit == c.factor.unit for c in calcs)
    print(f"  [ok] all {len(calcs)} calculations converted into their factor's unit")

    # 3. Factor versioning actually bites: 2024 on v1, 2025 on v2.
    v1 = db.scalar(select(EmissionFactor).where(EmissionFactor.code == "EF-GRID-IN-01"))
    v2 = db.scalar(select(EmissionFactor).where(EmissionFactor.code == "EF-GRID-IN-02"))
    on_v1 = [c for c in calcs if c.factor_id == v1.id]
    on_v2 = [c for c in calcs if c.factor_id == v2.id]
    assert on_v1 and on_v2
    assert all(c.activity.period_start.year == 2024 for c in on_v1)
    assert all(c.activity.period_start.year == 2025 for c in on_v2)
    print(f"  [ok] factor version split: {len(on_v1)} calcs on EF-GRID-IN-01 (CEA 2023), "
          f"{len(on_v2)} on EF-GRID-IN-02 (CEA 2024)")

    # 4. Equity-share consolidation is applied to the German entity only.
    de = [c for c in calcs if c.activity.facility.country == "DE"]
    inr = [c for c in calcs if c.activity.facility.country == "IN"]
    assert all(c.allocation_pct == 75.0 for c in de)
    assert all(c.allocation_pct == 100.0 for c in inr)
    print(f"  [ok] allocation: {len(de)} DE calcs at 75% equity share, "
          f"{len(inr)} IN calcs at 100% operational control")

    # 5. Scope 2 dual reporting exists for every electricity activity.
    elec = [a for a in activities if a.activity_type == "purchased_electricity"]
    for a in elec:
        methods = {c.methodology for c in calcs if c.activity_id == a.id}
        assert methods == {"location_based", "market_based"}, methods
    print(f"  [ok] all {len(elec)} electricity activities dual-reported "
          f"(location + market based)")

    # 6. The deliberate anomaly is present and large enough for a z-score to catch.
    pune = next(f for f in facilities.values() if f.name == "Pune Plant")
    gas = [a for a in activities
           if a.facility_id == pune.id and a.activity_type == "stationary_combustion"]
    aug = next(a for a in gas if a.period_start.strftime("%Y-%m") == "2025-08")
    others = [a.quantity for a in gas if a is not aug]
    mean = sum(others) / len(others)
    sd = (sum((q - mean) ** 2 for q in others) / len(others)) ** 0.5
    z = (aug.quantity - mean) / sd
    assert z > 2.0, z
    print(f"  [ok] anomaly present: Pune gas Aug-2025 = {aug.quantity:,.0f} m3 "
          f"vs mean {mean:,.0f} m3  (z = {z:.1f})")

    # 7. The deliberate data gaps are present for the data-quality panel.
    munich = next(f for f in facilities.values() if f.name == "Munich Assembly")
    chennai = next(f for f in facilities.values() if f.name == "Chennai Warehouse")
    q4 = [a for a in activities if a.facility_id == munich.id and a.activity_type == "waste"
          and a.period_start.strftime("%Y-%m") in ("2025-10", "2025-11", "2025-12")]
    assert q4 == [], q4
    assert not [a for a in activities
                if a.facility_id == chennai.id and a.activity_type == "fugitive"]
    print("  [ok] data gaps present: Munich waste Q4-2025 missing, "
          "Chennai refrigerant missing")

    # 8. Evidence is on disk, hashed, and reachable from the calculation chain.
    from database import STORAGE_DIR
    from seed import EVIDENCE, EVIDENCE_LINKS
    linked = [a for a in activities if a.evidence_id is not None]
    assert len(linked) == len(EVIDENCE_LINKS), (len(linked), len(EVIDENCE_LINKS))
    doc = act.evidence
    assert doc is not None and (STORAGE_DIR / doc.filename).exists()
    print(f"  [ok] lineage bottom reachable: activity #{act.id} -> {doc.filename} "
          f"(sha256 {doc.sha256[:8]}...) on disk")

    # 9. The document states the number the calculation consumed. If these ever drift,
    #    the audit trail is decorative and the whole demo is a lie.
    import hashlib
    for a in linked:
        raw = (STORAGE_DIR / a.evidence.filename).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == a.evidence.sha256, a.evidence.filename
        assert f"{a.quantity:,.2f}".encode() in raw, (a.evidence.filename, a.quantity)
    print(f"  [ok] all {len(linked)} evidence PDFs state the exact activity quantity "
          f"and match their stored sha256")

    # 10. Data quality is mixed, so the confidence badges are not uniformly green.
    mix = defaultdict(int)
    for a in activities:
        mix[a.data_quality] += 1
    assert len(mix) == 3, dict(mix)
    print(f"  [ok] data quality mix: {dict(mix)}")

    print()
    line("=")
    print("PHASE 1 OK - calculation engine verified.")
    line("=")
    print()
    db.close()


if __name__ == "__main__":
    main()
