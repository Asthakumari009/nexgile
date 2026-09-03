"""Deterministic seed. Runs once at startup if the DB is empty.

Every number here is driven by a fixed RNG seed, so the demo looks identical on every
machine and every run. Deliberately baked in: one anomaly (Pune gas, Aug 2025), two data
gaps (Munich waste Q4 2025, Chennai refrigerant), and a factor version bump for the India
grid so the recalculation banner has real work to do.
"""
from __future__ import annotations

import hashlib
import math
import random
import statistics
from datetime import date, datetime, timedelta

from sqlalchemy import select

from database import Base, STORAGE_DIR, SessionLocal, engine
from engine import calculator, factors, units
from models import (
    ActivityData,
    BomItem,
    CarbonBudget,
    Department,
    EmissionFactor,
    Entity,
    EvidenceDocument,
    Facility,
    Offset,
    Organization,
    Product,
    ReductionLever,
    Supplier,
)

RNG_SEED = 20240101
MONTHS = [(y, m) for y in (2024, 2025) for m in range(1, 13)]

# Only Hyderabad holds renewable certificates, so only it gets a near-zero market-based
# factor. Every other site falls back to the grid factor as a residual-mix proxy.
REC_FACILITIES = {"Hyderabad Plant"}


# --------------------------------------------------------------------------- factors
# (code, name, scope, category, unit, kgco2e, source, version, from, to, unc, region, method)
FACTORS = [
    ("EF-NG-01", "Natural gas, stationary", 1, "natural_gas", "m3", 2.02,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 3.0, None, None),
    ("EF-DSL-01", "Diesel, mobile", 1, "diesel", "litre", 2.68,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 3.0, None, None),
    ("EF-PET-01", "Petrol, mobile", 1, "petrol", "litre", 2.31,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 3.0, None, None),
    ("EF-R410-01", "R-410A fugitive (GWP)", 1, "refrigerant_r410a", "kg", 2088.0,
     "IPCC AR5", "v1", "2023-01-01", "2026-12-31", 10.0, None, None),
    # Deliberate version bump: v1 covers 2024, v2 covers 2025 onward.
    ("EF-GRID-IN-01", "India grid, location-based", 2, "grid_electricity", "kWh", 0.727,
     "CEA 2023", "v1", "2023-01-01", "2024-12-31", 5.0, "IN", "location_based"),
    ("EF-GRID-IN-02", "India grid, location-based", 2, "grid_electricity", "kWh", 0.716,
     "CEA 2024", "v2", "2025-01-01", "2026-12-31", 5.0, "IN", "location_based"),
    ("EF-GRID-IN-MKT", "India grid, market-based (REC)", 2, "grid_electricity", "kWh", 0.041,
     "Contractual", "v1", "2023-01-01", "2026-12-31", 8.0, "IN", "market_based"),
    ("EF-GRID-DE-01", "Germany grid, location-based", 2, "grid_electricity", "kWh", 0.363,
     "AIB 2024", "v1", "2023-01-01", "2026-12-31", 5.0, "DE", "location_based"),
    ("EF-STEEL-01", "Steel, primary", 3, "steel", "kg", 1.85,
     "ecoinvent 3.9 (proxy)", "v1", "2023-01-01", "2026-12-31", 15.0, None, None),
    ("EF-ALU-V-01", "Aluminium, virgin", 3, "aluminium_virgin", "kg", 16.50,
     "ecoinvent 3.9 (proxy)", "v1", "2023-01-01", "2026-12-31", 15.0, None, None),
    ("EF-ALU-R-01", "Aluminium, recycled", 3, "aluminium_recycled", "kg", 2.30,
     "ecoinvent 3.9 (proxy)", "v1", "2023-01-01", "2026-12-31", 15.0, None, None),
    ("EF-PP-01", "Polypropylene", 3, "polypropylene", "kg", 1.95,
     "ecoinvent 3.9 (proxy)", "v1", "2023-01-01", "2026-12-31", 15.0, None, None),
    ("EF-SPEND-MFG", "Purchased goods, spend-based", 3, "purchased_goods_spend", "INR", 0.00052,
     "EEIO proxy", "v1", "2023-01-01", "2026-12-31", 30.0, None, None),
    ("EF-AIR-01", "Air travel, long haul", 3, "business_travel", "passenger-km", 0.150,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 12.0, None, None),
    ("EF-ROAD-01", "Road freight", 3, "upstream_transport", "tonne-km", 0.107,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 12.0, None, None),
    ("EF-COMMUTE-01", "Employee commuting", 3, "employee_commuting", "km", 0.130,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 25.0, None, None),
    ("EF-WASTE-LF-01", "Waste to landfill", 3, "waste", "kg", 0.450,
     "DEFRA 2024", "v1", "2023-01-01", "2026-12-31", 20.0, None, None),
]

# ------------------------------------------------------------------- activity streams
# facility -> activity_type -> (base_qty, unit, description, source, quality, ghg_cat)
STREAMS: dict[str, list[tuple]] = {
    "Hyderabad Plant": [
        ("purchased_electricity", 1780, "MWh", "Grid electricity purchased, TSSPDCL", "invoice", "primary", None),
        ("stationary_combustion", 62000, "m3", "Natural gas, process boilers", "meter", "primary", None),
        ("mobile_combustion", 14000, "litre", "Diesel, plant vehicle fleet", "invoice", "primary", None),
        ("mobile_combustion", 3200, "litre", "Petrol, light vehicles", "invoice", "primary", None),
        ("purchased_goods_spend", 2_400_000_000, "INR", "Purchased goods and services", "erp", "secondary", 1),
        ("business_travel", 320000, "passenger-km", "Air travel, long haul", "erp", "secondary", 6),
        ("upstream_transport", 2_800_000, "tonne-km", "Inbound road freight", "erp", "secondary", 4),
        ("employee_commuting", 980000, "km", "Employee commuting", "estimate", "estimated", 7),
        ("waste", 180000, "kg", "Process waste to landfill", "invoice", "primary", 5),
    ],
    "Pune Plant": [
        ("purchased_electricity", 1240, "MWh", "Grid electricity purchased, MSEDCL", "invoice", "primary", None),
        ("stationary_combustion", 48000, "m3", "Natural gas, process boilers", "meter", "primary", None),
        ("mobile_combustion", 11000, "litre", "Diesel, plant vehicle fleet", "invoice", "primary", None),
        ("purchased_goods_spend", 1_800_000_000, "INR", "Purchased goods and services", "erp", "secondary", 1),
        ("business_travel", 210000, "passenger-km", "Air travel, long haul", "erp", "secondary", 6),
        ("upstream_transport", 2_100_000, "tonne-km", "Inbound road freight", "erp", "secondary", 4),
        ("employee_commuting", 720000, "km", "Employee commuting", "estimate", "estimated", 7),
        ("waste", 140000, "kg", "Process waste to landfill", "invoice", "primary", 5),
    ],
    "Chennai Warehouse": [
        ("purchased_electricity", 210, "MWh", "Grid electricity purchased, TANGEDCO", "invoice", "primary", None),
        ("mobile_combustion", 6500, "litre", "Diesel, forklift and yard fleet", "invoice", "primary", None),
        ("mobile_combustion", 2100, "litre", "Petrol, light vehicles", "invoice", "primary", None),
        ("purchased_goods_spend", 300_000_000, "INR", "Purchased goods and services", "erp", "secondary", 1),
        ("business_travel", 60000, "passenger-km", "Air travel, long haul", "erp", "secondary", 6),
        ("upstream_transport", 1_600_000, "tonne-km", "Outbound road freight", "erp", "secondary", 4),
        ("employee_commuting", 180000, "km", "Employee commuting", "estimate", "estimated", 7),
        ("waste", 35000, "kg", "Packaging waste to landfill", "invoice", "primary", 5),
    ],
    "Munich Assembly": [
        ("purchased_electricity", 940, "MWh", "Grid electricity purchased, Stadtwerke Muenchen", "invoice", "primary", None),
        ("stationary_combustion", 35000, "m3", "Natural gas, space and process heat", "meter", "primary", None),
        ("mobile_combustion", 5200, "litre", "Diesel, site vehicle fleet", "invoice", "primary", None),
        ("purchased_goods_spend", 1_500_000_000, "INR", "Purchased goods and services", "erp", "secondary", 1),
        ("business_travel", 280000, "passenger-km", "Air travel, long haul", "erp", "secondary", 6),
        ("upstream_transport", 1_400_000, "tonne-km", "Inbound road freight", "erp", "secondary", 4),
        ("employee_commuting", 340000, "km", "Employee commuting", "estimate", "estimated", 7),
        ("waste", 95000, "kg", "Process waste to landfill", "estimate", "estimated", 5),
    ],
}

# Refrigerant top-ups are quarterly, not monthly. Chennai is deliberately absent.
FUGITIVE = {"Hyderabad Plant": 42.0, "Pune Plant": 28.0, "Munich Assembly": 18.0}

DEPARTMENTS = {
    "manufacturing": [("Production", "CC-100"), ("Facilities", "CC-200"), ("Logistics", "CC-300")],
    "warehouse": [("Operations", "CC-400"), ("Logistics", "CC-300")],
}


# Month-to-month noise is an AR(1) walk in log space rather than an independent draw per
# month: real consumption drifts and the drift persists, which is what makes a meter
# series look like a meter series rather than white noise around a mean.
NOISE_RHO = 0.55
NOISE_SIGMA = 0.112

# Each series is then normalised to a target coefficient of variation drawn from this
# band. Normalising rather than relying on the raw walk is deliberate: at n=24 the sample
# CV of an unconstrained walk scatters roughly +/-5 points, so two thirds of the series
# would land outside the band by chance. Rescaling in log space fixes the dispersion
# while preserving the walk's autocorrelation and the seasonal shape on top of it.
TARGET_CV = (0.13, 0.17)

# The Pune Aug-2025 spike is specified in standard deviations of its own series baseline,
# not as a multiplier, so its severity is stable no matter how the series is scaled. High
# enough to flag reliably, low enough that the detector has to actually work for it.
ANOMALY_Z = 5.0


def _ar1_walk(rng: random.Random, n: int) -> list[float]:
    walk, noise = [], 0.0
    for _ in range(n):
        noise = NOISE_RHO * noise + rng.gauss(0.0, NOISE_SIGMA)
        walk.append(noise)
    return walk


def _rescale_cv(values: list[float], target_cv: float) -> list[float]:
    """Scale a series' log-variance so its coefficient of variation hits target_cv.

    Shape is preserved - every point keeps its position relative to the series mean, so
    seasonality and the AR(1) drift both survive; only the amplitude changes.
    """
    logs = [math.log(v) for v in values]
    mean_l = statistics.fmean(logs)
    sd_l = statistics.pstdev(logs)
    if sd_l == 0:
        return list(values)
    # For a lognormal, CV = sqrt(exp(sd_log^2) - 1). Invert for the log sd we need.
    k = math.sqrt(math.log(1 + target_cv ** 2)) / sd_l
    return [math.exp(mean_l + (l - mean_l) * k) for l in logs]


def _inject_anomaly(values: list[float], index: int) -> list[float]:
    """Set one point to ANOMALY_Z sigma above the mean of the rest of the series."""
    rest = [v for i, v in enumerate(values) if i != index]
    out = list(values)
    out[index] = statistics.fmean(rest) + ANOMALY_Z * statistics.pstdev(rest)
    return out


def _seasonal(country: str, activity_type: str, month: int) -> float:
    """Deterministic seasonal shape - Indian summer cooling, German winter heating."""
    if activity_type == "purchased_electricity":
        if country == "IN":
            return {3: 1.16, 4: 1.22, 5: 1.24, 6: 1.15, 7: 1.06, 8: 1.05, 9: 1.03}.get(month, 1.0)
        return {11: 1.10, 12: 1.14, 1: 1.15, 2: 1.11}.get(month, 1.0)
    if activity_type == "stationary_combustion" and country == "DE":
        # Damped relative to a real heating curve so the seasonal swing does not push
        # this series' CV past the 18% ceiling once noise is layered on.
        return {10: 1.06, 11: 1.12, 12: 1.16, 1: 1.18, 2: 1.13, 3: 1.07}.get(month, 0.94)
    return 1.0


# ------------------------------------------------------------------------ evidence PDF
def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    """Minimal single-page PDF. No dependency, opens in any browser."""
    body = ["BT", "/F1 15 Tf", "50 760 Td", f"({title}) Tj", "/F1 10 Tf", "0 -28 Td"]
    for line in lines:
        safe = line.replace("\\", "").replace("(", "[").replace(")", "]")
        body += [f"({safe}) Tj", "0 -16 Td"]
    body.append("ET")
    stream = "\n".join(body).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


# (filename, doc_type, uploaded_by, uploaded_at, page_ref, title, lines)
# {qty} / {open} / {close} are filled from the linked activity row after seeding, so the
# document an auditor opens states the same number the calculation consumed.
EVIDENCE = [
    ("TSSPDCL_Invoice_Jul2025.pdf", "invoice", "k.rao", "2025-08-04", "p.1",
     "TSSPDCL - Commercial HT Electricity Invoice",
     ["Consumer: Nexgile Industries Ltd - Hyderabad Plant",
      "Service number: HT-2201-44819", "Billing period: 01 Jul 2025 - 31 Jul 2025",
      "Recorded consumption: {qty:,.2f} MWh", "Tariff category: HT-I Industrial",
      "Meter serial: TS-88214-A   Multiplier: 1.0"]),
    ("TSSPDCL_Invoice_Mar2025.pdf", "invoice", "k.rao", "2025-04-05", "p.1",
     "TSSPDCL - Commercial HT Electricity Invoice",
     ["Consumer: Nexgile Industries Ltd - Hyderabad Plant",
      "Service number: HT-2201-44819", "Billing period: 01 Mar 2025 - 31 Mar 2025",
      "Recorded consumption: {qty:,.2f} MWh", "Tariff category: HT-I Industrial"]),
    ("MSEDCL_Invoice_Aug2025.pdf", "invoice", "a.deshpande", "2025-09-03", "p.1",
     "MSEDCL - HT Industrial Electricity Invoice",
     ["Consumer: Nexgile Industries Ltd - Pune Plant",
      "Service number: HT-3390-11726", "Billing period: 01 Aug 2025 - 31 Aug 2025",
      "Recorded consumption: {qty:,.2f} MWh"]),
    ("TANGEDCO_Invoice_Jun2025.pdf", "invoice", "s.natarajan", "2025-07-06", "p.1",
     "TANGEDCO - LT Commercial Electricity Invoice",
     ["Consumer: Nexgile Industries Ltd - Chennai Warehouse",
      "Service number: LT-CH-770412", "Billing period: 01 Jun 2025 - 30 Jun 2025",
      "Recorded consumption: {qty:,.2f} MWh"]),
    ("SWM_Stromrechnung_Sep2025.pdf", "invoice", "m.keller", "2025-10-02", "S.1",
     "Stadtwerke Muenchen - Stromrechnung",
     ["Kunde: Nexgile Europe GmbH - Munich Assembly",
      "Zaehlernummer: SWM-4471-B",
      "Abrechnungszeitraum: 01.09.2025 - 30.09.2025", "Verbrauch: {qty:,.2f} MWh"]),
    ("GAIL_GasMeter_Aug2025.pdf", "meter_reading", "a.deshpande", "2025-09-02", "p.2",
     "GAIL India - Industrial Gas Meter Reading",
     ["Site: Nexgile Industries Ltd - Pune Plant", "Meter: GAIL-PN-3391",
      "Period: 01 Aug 2025 - 31 Aug 2025",
      "Opening: {open:,.2f} scm    Closing: {close:,.2f} scm",
      "Consumption: {qty:,.2f} scm",
      "NOTE: reading flagged by site engineer - furnace 3 commissioning trial"]),
    ("GAIL_GasMeter_Jul2025.pdf", "meter_reading", "k.rao", "2025-08-02", "p.1",
     "GAIL India - Industrial Gas Meter Reading",
     ["Site: Nexgile Industries Ltd - Hyderabad Plant", "Meter: GAIL-HY-1188",
      "Period: 01 Jul 2025 - 31 Jul 2025",
      "Opening: {open:,.2f} scm    Closing: {close:,.2f} scm",
      "Consumption: {qty:,.2f} scm"]),
    ("REC_Certificate_FY2025_Hyderabad.pdf", "certificate", "s.mehta", "2025-04-18", "p.1",
     "Renewable Energy Certificate - Redemption Statement",
     ["Registry: Indian Renewable Energy Certificate Registry",
      "Beneficiary: Nexgile Industries Ltd - Hyderabad Plant",
      "Certificates redeemed: 21,360 (1 REC = 1 MWh)", "Compliance year: FY 2025",
      "Basis for market-based Scope 2 reporting at this site"]),
    ("Diesel_Invoice_Sep2025.pdf", "invoice", "k.rao", "2025-10-04", "p.1",
     "Bharat Petroleum - Bulk Diesel Supply Invoice",
     ["Buyer: Nexgile Industries Ltd - Hyderabad Plant",
      "Delivery period: 01 Sep 2025 - 30 Sep 2025",
      "High speed diesel delivered: {qty:,.2f} litres"]),
    ("Supplier_Attestation_Bhavani_2025.pdf", "attestation", "portal.upload", "2025-08-21", "p.1",
     "Supplier Attestation - Reporting Year 2025",
     ["Supplier: Bhavani Metals Pvt Ltd", "Buyer: Nexgile Industries Ltd",
      "Reported Scope 1: 4,120 tCO2e   Scope 2: 9,340 tCO2e",
      "Signatory: R. Bhavani, Managing Director",
      "The data submitted is accurate to the best of our knowledge."]),
    ("Freight_Manifest_Sep2025.pdf", "supplier_report", "logistics.bot", "2025-10-01", "p.4",
     "Consolidated Road Freight Manifest",
     ["Carrier: TCI Freight", "Shipper: Nexgile Industries Ltd - Hyderabad Plant",
      "Period: 01 Sep 2025 - 30 Sep 2025",
      "Total inbound freight: {qty:,.2f} tonne-km"]),
    ("Waste_Manifest_Sep2025.pdf", "supplier_report", "s.natarajan", "2025-10-08", "p.1",
     "Hazardous and General Waste Disposal Manifest",
     ["Generator: Nexgile Industries Ltd - Chennai Warehouse",
      "Period: 01 Sep 2025 - 30 Sep 2025",
      "Landfilled packaging waste: {qty:,.2f} kg"]),
]

# (facility, activity description, YYYY-MM) -> evidence filename. Keyed on the description
# rather than activity_type, because one facility can run two streams of the same type
# (diesel and petrol are both mobile_combustion).
EVIDENCE_LINKS = {
    ("Hyderabad Plant", "Grid electricity purchased, TSSPDCL", "2025-07"): "TSSPDCL_Invoice_Jul2025.pdf",
    ("Hyderabad Plant", "Grid electricity purchased, TSSPDCL", "2025-03"): "TSSPDCL_Invoice_Mar2025.pdf",
    ("Pune Plant", "Grid electricity purchased, MSEDCL", "2025-08"): "MSEDCL_Invoice_Aug2025.pdf",
    ("Chennai Warehouse", "Grid electricity purchased, TANGEDCO", "2025-06"): "TANGEDCO_Invoice_Jun2025.pdf",
    ("Munich Assembly", "Grid electricity purchased, Stadtwerke Muenchen", "2025-09"): "SWM_Stromrechnung_Sep2025.pdf",
    ("Pune Plant", "Natural gas, process boilers", "2025-08"): "GAIL_GasMeter_Aug2025.pdf",
    ("Hyderabad Plant", "Natural gas, process boilers", "2025-07"): "GAIL_GasMeter_Jul2025.pdf",
    ("Hyderabad Plant", "Diesel, plant vehicle fleet", "2025-09"): "Diesel_Invoice_Sep2025.pdf",
    ("Hyderabad Plant", "Inbound road freight", "2025-09"): "Freight_Manifest_Sep2025.pdf",
    ("Chennai Warehouse", "Packaging waste to landfill", "2025-09"): "Waste_Manifest_Sep2025.pdf",
}

# Cumulative meter readings the consumption is derived from.
METER_OPENING = {"GAIL_GasMeter_Aug2025.pdf": 4_182_660.0, "GAIL_GasMeter_Jul2025.pdf": 8_914_300.0}

SUPPLIERS = [
    # name, country, lat, lon, tier, parent_idx, category, spend, engagement, maturity, score
    ("Bhavani Metals Pvt Ltd", "IN", 17.385, 78.487, 1, None, "Metals", 980_000_000, "validated", "advanced", 82),
    ("Kirloskar Castings Ltd", "IN", 18.520, 73.856, 1, None, "Castings", 720_000_000, "submitted", "developing", 64),
    ("Rheinstahl Praezision GmbH", "DE", 51.227, 6.773, 1, None, "Precision parts", 640_000_000, "validated", "advanced", 88),
    ("Shenzhen Kaiyuan Electronics", "CN", 22.543, 114.058, 1, None, "Electronics", 810_000_000, "in_progress", "developing", 51),
    ("Hanoi Precision Plastics JSC", "VN", 21.028, 105.854, 1, None, "Polymers", 310_000_000, "invited", "low", 28),
    ("Coromandel Packaging Ltd", "IN", 13.083, 80.271, 1, None, "Packaging", 190_000_000, "submitted", "developing", 58),
    ("Deccan Alloys Pvt Ltd", "IN", 17.240, 78.430, 2, 0, "Alloys", 420_000_000, "invited", "low", 34),
    ("Bayern Aluminiumwerk AG", "DE", 48.783, 11.433, 2, 2, "Aluminium", 380_000_000, "validated", "advanced", 79),
    ("Guangdong Circuit Substrates", "CN", 23.129, 113.264, 2, 3, "PCB substrate", 260_000_000, "not_invited", "low", 0),
    ("Vizag Steel Rolling Pvt Ltd", "IN", 17.686, 83.218, 2, 0, "Steel", 550_000_000, "in_progress", "developing", 46),
    ("Jiangxi Rare Earth Mining Co", "CN", 28.682, 115.858, 3, 8, "Raw materials", 120_000_000, "not_invited", "low", 0),
    ("Odisha Bauxite Minerals Ltd", "IN", 20.951, 85.098, 3, 7, "Raw materials", 145_000_000, "not_invited", "low", 0),
]

LEVERS = [
    ("Rooftop solar, Hyderabad + Pune", "renewable_electricity", 8600, 340_000_000, -42_000_000, 6.2, "approved", "s.mehta"),
    ("Corporate PPA, 60 MW wind", "renewable_electricity", 21400, 0, -95_000_000, 0.0, "in_progress", "s.mehta"),
    ("LED and HVAC retrofit, all sites", "energy_efficiency", 2150, 68_000_000, -19_000_000, 3.6, "approved", "d.iyer"),
    ("Recycled aluminium substitution", "material_substitution", 4300, 22_000_000, 8_000_000, 4.1, "proposed", "n.gupta"),
    ("Switch to low-carbon steel supplier", "supply_chain", 5900, 0, 31_000_000, 0.0, "proposed", "n.gupta"),
    ("Road to rail freight mode shift", "logistics", 3100, 14_000_000, -6_500_000, 2.2, "proposed", "r.chandra"),
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed(db) -> None:
    rng = random.Random(RNG_SEED)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    org = Organization(
        name="Nexgile Industries Ltd",
        base_currency="INR",
        baseline_year=2023,
        target_year=2030,
        target_reduction_pct=42.0,
        consolidation_method="equity_share",
    )
    db.add(org)
    db.flush()

    # Wholly owned, so equity share consolidates it at 100% anyway.
    india = Entity(org_id=org.id, name="Nexgile India Pvt Ltd", country="IN",
                   ownership_pct=100.0)
    europe = Entity(org_id=org.id, name="Nexgile Europe GmbH", country="DE",
                    ownership_pct=75.0)
    db.add_all([india, europe])
    db.flush()

    facilities = [
        Facility(entity_id=india.id, name="Hyderabad Plant", city="Hyderabad", country="IN",
                 lat=17.385, lon=78.487, facility_type="manufacturing", floor_area_m2=48000),
        Facility(entity_id=india.id, name="Pune Plant", city="Pune", country="IN",
                 lat=18.520, lon=73.856, facility_type="manufacturing", floor_area_m2=36000),
        Facility(entity_id=india.id, name="Chennai Warehouse", city="Chennai", country="IN",
                 lat=13.083, lon=80.271, facility_type="warehouse", floor_area_m2=21000),
        Facility(entity_id=europe.id, name="Munich Assembly", city="Munich", country="DE",
                 lat=48.137, lon=11.575, facility_type="manufacturing", floor_area_m2=29000),
    ]
    db.add_all(facilities)
    db.flush()

    by_name = {f.name: f for f in facilities}
    depts: dict[tuple[str, str], Department] = {}
    for f in facilities:
        for dname, cc in DEPARTMENTS[f.facility_type]:
            d = Department(facility_id=f.id, name=dname, cost_center=cc)
            db.add(d)
            depts[(f.name, dname)] = d
    db.flush()

    for row in FACTORS:
        code, name, scope, cat, unit, val, src, ver, vf, vt, unc, region, method = row
        db.add(EmissionFactor(
            code=code, name=name, scope=scope, category=cat, unit=unit, value_kgco2e=val,
            source=src, version=ver, valid_from=date.fromisoformat(vf),
            valid_to=date.fromisoformat(vt), uncertainty_pct=unc, region=region,
            method=method, is_active=date.fromisoformat(vt) >= date(2025, 12, 31),
        ))
    units.seed_conversions(db)
    db.flush()

    # Evidence rows first so activities can reference them; the files themselves are
    # written after seeding, once the real quantities are known.
    evidence: dict[str, EvidenceDocument] = {}
    for filename, doc_type, who, when, page_ref, title, _lines in EVIDENCE:
        doc = EvidenceDocument(
            filename=filename, doc_type=doc_type, uploaded_by=who,
            uploaded_at=datetime.fromisoformat(when + "T09:00:00"),
            sha256="", file_path=f"/storage/{filename}", page_ref=page_ref, notes=title,
        )
        db.add(doc)
        evidence[filename] = doc
    db.flush()

    _seed_suppliers(db, org)
    _seed_products(db, org)

    for name, cat, pot, capex, opex, payback, status, owner in LEVERS:
        db.add(ReductionLever(org_id=org.id, name=name, category=cat, potential_tco2e=pot,
                              capex=capex, opex_delta=opex, payback_years=payback,
                              status=status, owner=owner))

    db.add_all([
        Offset(org_id=org.id, project_name="Bundelkhand Improved Cookstoves", registry="Gold Standard",
               vintage=2023, tonnes=4000, price_per_tonne=1250, status="retired",
               retirement_evidence_id=None),
        Offset(org_id=org.id, project_name="Andhra Pradesh Afforestation", registry="Verra VCS",
               vintage=2024, tonnes=6500, price_per_tonne=1680, status="purchased",
               retirement_evidence_id=None),
    ])

    activities = _seed_activities(db, by_name, depts, evidence, rng)
    db.flush()

    _write_evidence_files(db, evidence, activities)
    _run_calculations(db, activities)
    _seed_budgets(db, [india, europe])
    db.commit()


def _seed_activities(db, by_name, depts, evidence, rng) -> list[ActivityData]:
    created: list[ActivityData] = []
    n = 0

    for fname, streams in STREAMS.items():
        facility = by_name[fname]
        for activity_type, base, unit, desc, source, quality, ghg_cat in streams:
            scope = {"purchased_electricity": 2}.get(activity_type, 1)
            if ghg_cat is not None:
                scope = 3

            dept_name = {
                "purchased_electricity": "Facilities", "stationary_combustion": "Production",
                "waste": "Production", "upstream_transport": "Logistics",
            }.get(activity_type)
            if facility.facility_type == "warehouse":
                dept_name = "Logistics" if dept_name == "Logistics" else "Operations"
            dept = depts.get((fname, dept_name)) if dept_name else None

            # Gap: Munich has no Scope 3 waste data for Q4 2025.
            gap = (lambda y, m: fname == "Munich Assembly" and activity_type == "waste"
                   and y == 2025 and m >= 10)
            months = [(y, m) for y, m in MONTHS if not gap(y, m)]

            # The AR(1) walk runs over all 24 months even where a row is suppressed, so a
            # data gap does not shift the series that surrounds it.
            walk = _ar1_walk(rng, len(MONTHS))
            raw = [base * _seasonal(facility.country, activity_type, m) * math.exp(w)
                   for (y, m), w in zip(MONTHS, walk) if not gap(y, m)]
            qtys = _rescale_cv(raw, rng.uniform(*TARGET_CV))

            if fname == "Pune Plant" and activity_type == "stationary_combustion":
                qtys = _inject_anomaly(qtys, months.index((2025, 8)))

            for (year, month), qty in zip(months, qtys):
                n += 1
                # Keep the quality badges honest rather than uniformly green.
                q, src = quality, source
                if n % 7 == 0 and quality == "primary":
                    q, src = "secondary", "erp"

                start = date(year, month, 1)
                end = (date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1))
                key = (fname, desc, f"{year}-{month:02d}")
                doc = evidence.get(EVIDENCE_LINKS.get(key, ""))

                a = ActivityData(
                    facility_id=facility.id,
                    department_id=dept.id if dept else None,
                    scope=scope, ghg_category=ghg_cat, activity_type=activity_type,
                    description=desc, quantity=round(qty, 2), unit=unit,
                    period_start=start, period_end=end, data_source=src, data_quality=q,
                    evidence_id=doc.id if doc else None, supplier_id=None,
                    created_at=datetime(year, month, 5, 9, 30),
                )
                db.add(a)
                created.append(a)

        # Refrigerant top-ups, quarterly. Chennai is a deliberate gap.
        if fname in FUGITIVE:
            quarters = [(y, m) for y, m in MONTHS if m in (3, 6, 9, 12)]
            walk = _ar1_walk(rng, len(quarters))
            qtys = _rescale_cv([FUGITIVE[fname] * math.exp(w) for w in walk],
                               rng.uniform(*TARGET_CV))
            for (year, month), qty in zip(quarters, qtys):
                start = date(year, month, 1)
                end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
                a = ActivityData(
                    facility_id=facility.id, department_id=depts.get((fname, "Facilities")).id
                    if (fname, "Facilities") in depts else None,
                    scope=1, ghg_category=None, activity_type="fugitive",
                    description="R-410A refrigerant top-up, chiller plant",
                    quantity=round(qty, 2), unit="kg", period_start=start, period_end=end,
                    data_source="estimate", data_quality="estimated", evidence_id=None,
                    supplier_id=None, created_at=datetime(year, month, 5, 9, 30),
                )
                db.add(a)
                created.append(a)

    db.flush()
    return created


def _write_evidence_files(db, evidence: dict, activities: list[ActivityData]) -> None:
    """Render each PDF using the quantity of the activity it backs, then hash the bytes.

    An auditor who opens the document at the bottom of the lineage chain must see the
    same number the calculation consumed, so the text is generated from the data rather
    than hardcoded alongside it.
    """
    linked = {a.evidence_id: a for a in activities if a.evidence_id is not None}

    for filename, _dt, _who, _when, _pr, title, lines in EVIDENCE:
        doc = evidence[filename]
        act = linked.get(doc.id)
        if act is not None:
            opening = METER_OPENING.get(filename, 0.0)
            fmt = {"qty": act.quantity, "open": opening, "close": opening + act.quantity}
            rendered = [ln.format(**fmt) if "{" in ln else ln for ln in lines]
        else:
            rendered = [ln for ln in lines if "{" not in ln]

        data = _pdf_bytes(title, rendered)
        (STORAGE_DIR / filename).write_bytes(data)
        doc.sha256 = _sha(data)
    db.flush()


def _closed_at(activity: ActivityData) -> datetime:
    """When the books were closed for that period - four days after the period ends.

    Seeded history must carry period-relative timestamps, not the moment the seed ran, or
    a 2024 record shows an approval dated today and the audit trail reads as fabricated.
    """
    return datetime.combine(activity.period_end, datetime.min.time()) + timedelta(
        days=4, hours=10, minutes=12
    )


def _run_calculations(db, activities: list[ActivityData]) -> None:
    """Run the engine over every activity. Scope 2 gets dual location/market reporting."""
    for a in activities:
        at = _closed_at(a)
        if a.activity_type == "purchased_electricity":
            calculator.calculate(db, a, "location_based", "system.seed", at=at)

            if a.facility.name in REC_FACILITIES:
                calculator.calculate(db, a, "market_based", "system.seed", at=at)
            else:
                # No contractual instrument at this site: GHG Protocol falls back to the
                # residual mix, proxied here by the grid factor. Still reported separately.
                loc = factors.resolve_for_activity(db, a, method="location_based")
                calculator.calculate(db, a, "market_based", "system.seed", factor=loc, at=at)
        else:
            calculator.calculate(db, a, _methodology_for(a), "system.seed", at=at)

    # Everything up to Sep 2025 is signed off; the tail stays in draft so the approval
    # workflow and the "approved only" toggle both have something to show.
    from models import Calculation
    for calc in db.scalars(select(Calculation)):
        if calc.activity.period_start <= date(2025, 9, 30):
            # Reviewed two days after the calculation was run.
            calculator.approve(db, calc, "s.mehta",
                               at=calc.created_at + timedelta(days=2, hours=1, minutes=14))
    db.flush()


def _methodology_for(a: ActivityData) -> str:
    return {
        "purchased_goods_spend": "spend_based",
        "upstream_transport": "distance_based",
        "business_travel": "distance_based",
        "employee_commuting": "distance_based",
    }.get(a.activity_type, "activity_based")


def _seed_suppliers(db, org) -> None:
    rows: list[Supplier] = []
    for name, country, lat, lon, tier, parent, cat, spend, eng, mat, score in SUPPLIERS:
        s = Supplier(
            org_id=org.id, name=name, country=country, lat=lat, lon=lon, tier=tier,
            parent_supplier_id=None, category=cat, annual_spend=spend, currency="INR",
            engagement_status=eng, maturity=mat, score=score,
            scope3_tco2e=round(spend * 0.00052 / 1000 * 12, 1),
            carbon_intensity=round(0.00052 * 1000, 3),
            yoy_change_pct=round(-8.0 + (score % 17) * 0.9, 1),
        )
        db.add(s)
        rows.append(s)
    db.flush()
    for s, spec in zip(rows, SUPPLIERS):
        if spec[5] is not None:
            s.parent_supplier_id = rows[spec[5]].id
    db.flush()


def _seed_products(db, org) -> None:
    ctrl = Product(org_id=org.id, sku="NX-CTRL-100", name="Industrial Controller",
                   category="Electronics", functional_unit="1 unit",
                   boundary="cradle_to_gate", status="published")
    pump = Product(org_id=org.id, sku="NX-PUMP-250", name="Pump Unit", category="Mechanical",
                   functional_unit="1 unit", boundary="cradle_to_grave", status="draft")
    db.add_all([ctrl, pump])
    db.flush()

    def factor(code: str) -> int | None:
        f = db.scalar(select(EmissionFactor).where(EmissionFactor.code == code))
        return f.id if f else None

    def add(product, name, material, mass, qty, code, parent=None):
        item = BomItem(product_id=product.id, parent_bom_item_id=parent.id if parent else None,
                       component_name=name, material=material, mass_kg=mass, quantity=qty,
                       supplier_id=None, factor_id=factor(code))
        db.add(item)
        db.flush()
        return item

    housing = add(ctrl, "Housing", "Aluminium, virgin", 0.80, 1, "EF-ALU-V-01")
    add(ctrl, "Housing fasteners", "Steel, primary", 0.06, 8, "EF-STEEL-01", housing)
    pcba = add(ctrl, "PCB assembly", "Mixed", 0.22, 1, "EF-PP-01")
    add(ctrl, "Integrated circuits", "Silicon (proxy)", 0.02, 14, "EF-PP-01", pcba)
    add(ctrl, "Capacitors", "Mixed", 0.03, 26, "EF-PP-01", pcba)
    add(ctrl, "PCB substrate", "Polypropylene", 0.17, 1, "EF-PP-01", pcba)
    add(ctrl, "Display module", "Polypropylene", 0.14, 1, "EF-PP-01")
    add(ctrl, "Packaging", "Polypropylene", 0.19, 1, "EF-PP-01")

    body = add(pump, "Pump body", "Steel, primary", 12.0, 1, "EF-STEEL-01")
    add(pump, "Impeller", "Steel, primary", 1.6, 1, "EF-STEEL-01", body)
    motor = add(pump, "Motor assembly", "Mixed", 6.4, 1, "EF-STEEL-01")
    add(pump, "Motor windings", "Aluminium, virgin", 1.1, 1, "EF-ALU-V-01", motor)
    add(pump, "Seals and gaskets", "Polypropylene", 0.35, 6, "EF-PP-01")
    add(pump, "Packaging", "Polypropylene", 0.90, 1, "EF-PP-01")


def _seed_budgets(db, entities) -> None:
    from models import Emission
    for e in entities:
        for year in (2024, 2025):
            actual = sum(
                row.tco2e for row in db.scalars(
                    select(Emission).where(
                        Emission.entity_id == e.id,
                        Emission.period_month.startswith(str(year)),
                    )
                )
            )
            db.add(CarbonBudget(entity_id=e.id, year=year,
                                budget_tco2e=round(actual * 0.94, 1),
                                actual_tco2e=round(actual, 1)))


def seed_if_empty() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Organization)) is None:
            seed(db)


if __name__ == "__main__":
    import os
    from database import DB_PATH

    if DB_PATH.exists():
        os.remove(DB_PATH)
    seed_if_empty()
    print(f"Seeded {DB_PATH}")
