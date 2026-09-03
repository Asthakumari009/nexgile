"""Supplier profile, evidence, and submission endpoints for the external portal."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import STORAGE_DIR, get_db
from engine import calculator
from models import ActivityData, EvidenceDocument, Facility, Organization, Supplier, SupplierSubmission
from schemas import SupplierCreateRequest, SupplierSubmissionRequest

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


def _supplier_out(supplier: Supplier) -> dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "country": supplier.country,
        "tier": supplier.tier,
        "category": supplier.category,
        "engagement_status": supplier.engagement_status,
        "maturity": supplier.maturity,
        "score": supplier.score,
        "annual_spend": supplier.annual_spend,
        "currency": supplier.currency,
        "scope3_tco2e": supplier.scope3_tco2e,
        "carbon_intensity": supplier.carbon_intensity,
        "yoy_change_pct": supplier.yoy_change_pct,
        "parent_supplier_id": supplier.parent_supplier_id,
        "lat": supplier.lat,
        "lon": supplier.lon,
    }


def _submission_out(submission: SupplierSubmission) -> dict:
    return {
        "id": submission.id,
        "period": submission.period,
        "reported_scope1": submission.reported_scope1,
        "reported_scope2": submission.reported_scope2,
        "reported_scope3": submission.reported_scope3,
        "evidence_id": submission.evidence_id,
        "validation_state": submission.validation_state,
        "attested": submission.attested,
        "reviewer_note": submission.reviewer_note,
        "submitted_at": submission.submitted_at.isoformat(),
    }


def _get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, f"No supplier with id {supplier_id}")
    return supplier


@router.get("")
def list_suppliers(db: Session = Depends(get_db)) -> dict:
    """A small directory used to make the demo portal's recipient explicit."""
    rows = list(db.scalars(select(Supplier).order_by(Supplier.name)))
    return {"count": len(rows), "rows": [_supplier_out(supplier) for supplier in rows]}


@router.post("")
def create_supplier(req: SupplierCreateRequest, db: Session = Depends(get_db)) -> dict:
    org = db.scalar(select(Organization))
    if org is None:
        raise HTTPException(422, "Create the company and a facility before inviting suppliers")
    supplier = Supplier(org_id=org.id, name=req.name, country=req.country.upper(), lat=0.0, lon=0.0,
        tier=1, parent_supplier_id=None, category=req.category, annual_spend=0.0, currency="INR",
        engagement_status="not_invited", maturity="low", score=0.0, scope3_tco2e=0.0,
        carbon_intensity=0.0, yoy_change_pct=0.0)
    db.add(supplier); db.commit()
    return _supplier_out(supplier)


@router.get("/{supplier_id}")
def supplier_detail(supplier_id: int, db: Session = Depends(get_db)) -> dict:
    supplier = _get_supplier(db, supplier_id)
    latest = db.scalar(
        select(SupplierSubmission)
        .where(SupplierSubmission.supplier_id == supplier_id)
        .order_by(SupplierSubmission.submitted_at.desc())
    )
    return {"supplier": _supplier_out(supplier), "latest_submission": _submission_out(latest) if latest else None}


@router.post("/{supplier_id}/invite")
def invite(supplier_id: int, db: Session = Depends(get_db)) -> dict:
    supplier = _get_supplier(db, supplier_id)
    if supplier.engagement_status == "not_invited":
        supplier.engagement_status = "invited"
        db.commit()
    return {"supplier": _supplier_out(supplier), "portal_path": f"/supplier/invite/supplier-{supplier.id}"}


@router.get("/invite-token/{token}")
def invite_detail(token: str, db: Session = Depends(get_db)) -> dict:
    if not token.startswith("supplier-") or not token.removeprefix("supplier-").isdigit():
        raise HTTPException(404, "Invalid supplier invitation")
    return {"supplier": _supplier_out(_get_supplier(db, int(token.removeprefix("supplier-"))))}


@router.post("/{supplier_id}/evidence")
async def upload_evidence(
    supplier_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    _get_supplier(db, supplier_id)
    if not file.filename:
        raise HTTPException(400, "An evidence filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Evidence file is empty")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Evidence files must be 10 MB or smaller")

    filename = Path(file.filename).name
    stored_name = f"supplier-{supplier_id}-{uuid4().hex[:10]}-{filename}"
    path = STORAGE_DIR / stored_name
    path.write_bytes(content)
    document = EvidenceDocument(
        filename=filename,
        doc_type="supplier_report",
        uploaded_by=f"supplier:{supplier_id}",
        uploaded_at=datetime.utcnow(),
        sha256=sha256(content).hexdigest(),
        file_path=str(path),
        page_ref=None,
        notes="Submitted through the supplier portal",
    )
    db.add(document)
    db.commit()
    return {"id": document.id, "filename": document.filename, "url": f"/storage/{stored_name}"}


@router.post("/{supplier_id}/submissions")
def submit(
    supplier_id: int,
    req: SupplierSubmissionRequest,
    db: Session = Depends(get_db),
) -> dict:
    supplier = _get_supplier(db, supplier_id)
    if not req.attested:
        raise HTTPException(422, "An authorised representative must attest to this submission")
    if req.evidence_id is not None and db.get(EvidenceDocument, req.evidence_id) is None:
        raise HTTPException(422, f"No evidence document with id {req.evidence_id}")

    submission = SupplierSubmission(
        supplier_id=supplier.id,
        period=req.period,
        reported_scope1=req.reported_scope1,
        reported_scope2=req.reported_scope2,
        reported_scope3=req.reported_scope3,
        evidence_id=req.evidence_id,
        validation_state="pending",
        attested=True,
        reviewer_note=None,
        submitted_at=datetime.utcnow(),
    )
    supplier.engagement_status = "submitted"
    db.add(submission)
    facility = db.scalar(select(Facility).order_by(Facility.id))
    if facility is None:
        raise HTTPException(422, "A company facility is required before supplier data can be reported")
    total_tco2e = req.reported_scope1 + req.reported_scope2 + req.reported_scope3
    activity = ActivityData(facility_id=facility.id, department_id=None, scope=3, ghg_category=1,
        activity_type="supplier_report", description=f"Supplier-reported inventory: {supplier.name}",
        quantity=total_tco2e, unit="tCO2e", period_start=datetime(int(req.period), 1, 1).date(),
        period_end=datetime(int(req.period), 12, 31).date(), data_source="supplier_primary",
        data_quality="primary", evidence_id=req.evidence_id, supplier_id=supplier.id, created_at=datetime.utcnow())
    db.add(activity); db.flush()
    calculation = calculator.calculate(db, activity, "supplier_specific", f"supplier:{supplier.id}")
    supplier.scope3_tco2e += total_tco2e
    db.commit()
    return {"supplier": _supplier_out(supplier), "submission": _submission_out(submission), "emission_id": calculation.id}
