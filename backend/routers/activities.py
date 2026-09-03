"""Activity data: the filterable table behind Carbon Accounting, plus CSV import."""
import csv
import io
import uuid
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from engine import calculator
from models import ActivityData, Calculation, Emission, Facility

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])

# In-memory import jobs. Restarting the API loses them, which is correct for a demo -
# a real build would persist these. ponytail: dict, swap for a table if jobs must survive.
JOBS: dict[str, dict] = {}

REQUIRED_COLUMNS = ("facility", "scope", "activity_type", "description",
                    "quantity", "unit", "period_start", "period_end",
                    "data_source", "data_quality")


def _row(a: ActivityData, calcs: dict[int, list[Calculation]]) -> dict:
    mine = calcs.get(a.id, [])
    return {
        "id": a.id,
        "facility": a.facility.name,
        "facility_id": a.facility_id,
        "scope": a.scope,
        "ghg_category": a.ghg_category,
        "activity_type": a.activity_type,
        "description": a.description,
        "quantity": a.quantity,
        "unit": a.unit,
        "period_start": a.period_start.isoformat(),
        "period_end": a.period_end.isoformat(),
        "period_month": a.period_start.strftime("%Y-%m"),
        "data_source": a.data_source,
        "data_quality": a.data_quality,
        "evidence_id": a.evidence_id,
        "evidence_filename": a.evidence.filename if a.evidence else None,
        "supplier_id": a.supplier_id,
        "calculations": [
            {
                "id": c.id,
                "methodology": c.methodology,
                "calc_version": c.calc_version,
                "status": c.status,
                "formula_text": c.formula_text,
                "tco2e": round(c.result_kgco2e / 1000.0, 2),
                "factor_code": c.factor.code,
                "factor_version": c.factor.version,
                "approved_by": c.approved_by,
                # Filled in by the caller, which batches the emission lookup.
                "emission_id": None,
            }
            for c in sorted(mine, key=lambda c: (c.methodology, c.calc_version))
        ],
    }


@router.get("")
def list_activities(
    scope: int | None = None,
    facility_id: int | None = None,
    period: str | None = Query(None, description="YYYY-MM"),
    quality: str | None = Query(None, pattern="^(primary|secondary|estimated)$"),
    activity_type: str | None = None,
    q: str | None = Query(None, description="substring match on description"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(ActivityData)
    if scope is not None:
        stmt = stmt.where(ActivityData.scope == scope)
    if facility_id is not None:
        stmt = stmt.where(ActivityData.facility_id == facility_id)
    if quality:
        stmt = stmt.where(ActivityData.data_quality == quality)
    if activity_type:
        stmt = stmt.where(ActivityData.activity_type == activity_type)
    if q:
        stmt = stmt.where(ActivityData.description.ilike(f"%{q}%"))
    if period:
        # period_start is a Date, so match the month by range rather than by string.
        year, month = (int(p) for p in period.split("-"))
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1)
        stmt = stmt.where(ActivityData.period_start >= start,
                          ActivityData.period_start < end)

    total = len(list(db.scalars(stmt)))
    rows = list(
        db.scalars(
            stmt.order_by(ActivityData.period_start.desc(), ActivityData.id.desc())
            .offset(offset).limit(limit)
        )
    )
    calcs: dict[int, list[Calculation]] = {}
    if rows:
        for c in db.scalars(
            select(Calculation).where(Calculation.activity_id.in_([a.id for a in rows]))
        ):
            calcs.setdefault(c.activity_id, []).append(c)

    emission_ids = {
        e.calculation_id: e.id
        for e in db.scalars(
            select(Emission).where(
                Emission.calculation_id.in_(
                    [c.id for group in calcs.values() for c in group]
                )
            )
        )
    } if calcs else {}

    out = []
    for a in rows:
        row = _row(a, calcs)
        for c in row["calculations"]:
            c["emission_id"] = emission_ids.get(c["id"])
        out.append(row)
    return {"total": total, "offset": offset, "limit": limit, "rows": out}


@router.get("/facets")
def facets(db: Session = Depends(get_db)) -> dict:
    """Distinct filter values, so the table's dropdowns come from real data."""
    types = sorted({t for t in db.scalars(select(ActivityData.activity_type).distinct())})
    months = sorted(
        {d.strftime("%Y-%m")
         for d in db.scalars(select(ActivityData.period_start).distinct())},
        reverse=True,
    )
    facilities = [
        {"id": f.id, "name": f.name} for f in db.scalars(select(Facility).order_by(Facility.id))
    ]
    return {
        "activity_types": types,
        "periods": months,
        "facilities": facilities,
        "qualities": ["primary", "secondary", "estimated"],
        "scopes": [1, 2, 3],
    }


@router.get("/{activity_id}")
def get_activity(activity_id: int, db: Session = Depends(get_db)) -> dict:
    a = db.get(ActivityData, activity_id)
    if a is None:
        raise HTTPException(404, f"No activity with id {activity_id}")
    calcs = {activity_id: list(
        db.scalars(select(Calculation).where(Calculation.activity_id == activity_id))
    )}
    row = _row(a, calcs)
    for c in row["calculations"]:
        e = db.scalar(select(Emission).where(Emission.calculation_id == c["id"]))
        c["emission_id"] = e.id if e else None
    return row


# ------------------------------------------------------------------------ CSV import
def _parse_row(db: Session, raw: dict, facilities: dict[str, Facility]) -> ActivityData:
    missing = [c for c in REQUIRED_COLUMNS if not (raw.get(c) or "").strip()]
    if missing:
        raise ValueError(f"missing required column(s): {', '.join(missing)}")

    facility = facilities.get(raw["facility"].strip().lower())
    if facility is None:
        raise ValueError(f"unknown facility {raw['facility']!r}")

    quantity = float(raw["quantity"])
    if quantity < 0:
        raise ValueError(f"quantity must not be negative (got {quantity})")

    quality = raw["data_quality"].strip().lower()
    if quality not in ("primary", "secondary", "estimated"):
        raise ValueError(f"data_quality must be primary|secondary|estimated, got {quality!r}")

    return ActivityData(
        facility_id=facility.id,
        scope=int(raw["scope"]),
        ghg_category=int(raw["ghg_category"]) if (raw.get("ghg_category") or "").strip() else None,
        activity_type=raw["activity_type"].strip(),
        description=raw["description"].strip(),
        quantity=quantity,
        unit=raw["unit"].strip(),
        period_start=date.fromisoformat(raw["period_start"].strip()),
        period_end=date.fromisoformat(raw["period_end"].strip()),
        data_source=raw["data_source"].strip(),
        data_quality=quality,
        created_at=datetime.utcnow(),
    )


def _run_import(job_id: str, text: str, actor: str) -> None:
    """Parse, insert and calculate row by row. One bad row fails only itself."""
    job = JOBS[job_id]
    db = SessionLocal()
    try:
        facilities = {f.name.lower(): f for f in db.scalars(select(Facility))}
        rows = list(csv.DictReader(io.StringIO(text)))
        job["total"] = len(rows)
        for i, raw in enumerate(rows, start=2):  # line 1 is the header
            job["processed"] += 1
            try:
                activity = _parse_row(db, raw, facilities)
                db.add(activity)
                db.flush()
                methodologies = (
                    ["location_based", "market_based"]
                    if activity.activity_type == "purchased_electricity"
                    else [_default_methodology(activity)]
                )
                for m in methodologies:
                    calculator.calculate(db, activity, m, actor)
                db.commit()
                job["succeeded"] += 1
            except Exception as exc:  # noqa: BLE001 - per-row isolation is the point
                db.rollback()
                job["failed"] += 1
                if len(job["errors"]) < 50:
                    job["errors"].append({"line": i, "error": str(exc),
                                          "row": {k: v for k, v in raw.items() if v}})
        job["status"] = "complete"
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["errors"].append({"line": None, "error": f"import aborted: {exc}", "row": {}})
    finally:
        db.close()


def _default_methodology(activity: ActivityData) -> str:
    if activity.activity_type == "purchased_goods_spend":
        return "spend_based"
    if activity.activity_type in ("business_travel", "upstream_transport"):
        return "distance_based"
    return "activity_based"


@router.post("/import")
async def import_csv(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    actor: str = "csv.import",
    db: Session = Depends(get_db),
) -> dict:
    """Upload activity rows as CSV. Returns a job_id to poll - FastAPI BackgroundTasks."""
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"job_id": job_id, "status": "running", "filename": file.filename,
                    "total": 0, "processed": 0, "succeeded": 0, "failed": 0, "errors": []}
    background.add_task(_run_import, job_id, text, actor)
    return {"job_id": job_id, "status": "running",
            "required_columns": list(REQUIRED_COLUMNS)}


@router.get("/import/{job_id}")
def import_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, f"No import job {job_id}")
    return job
