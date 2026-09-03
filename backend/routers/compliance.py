"""Data-readiness indicators. They are not claims of regulatory compliance."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from engine import analytics

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])

FRAMEWORKS = {"csrd": "CSRD / ESRS", "cbam": "CBAM", "tcfd": "TCFD", "eu-taxonomy": "EU Taxonomy", "sec": "SEC climate disclosure", "cdp": "CDP"}


def _readiness(db: Session) -> list[dict]:
    quality, totals = analytics.data_quality(db), analytics.totals(db)
    completeness, primary, approved = quality["overall_completeness_pct"], totals["primary_data_pct"], totals["approved_pct"]
    gaps = [f"{g['facility']}: {g['activity_type']}" for g in (quality["gaps"] + quality["unreported_series"])[:3]]
    scores = {"csrd": round(.45 * completeness + .25 * primary + .30 * approved),
              "cbam": round(.30 * completeness + .30 * primary + .40 * approved),
              "tcfd": round(.25 * completeness + .20 * primary + .25 * approved + 25),
              "eu-taxonomy": round(.35 * completeness + .25 * primary + .20 * approved),
              "sec": round(.40 * completeness + .25 * primary + .35 * approved),
              "cdp": round(.45 * completeness + .30 * primary + .25 * approved)}
    return [{"framework": key, "name": name, "readiness_pct": min(scores[key], 100),
             "met": ["Scope 1, 2 and 3 inventory is calculated", "Calculation lineage is retained"],
             "unmet": ["Complete the identified reporting gaps", *gaps],
             "disclaimer": "Data-readiness indicator only. It is not a compliance determination."}
            for key, name in FRAMEWORKS.items()]


@router.get("/readiness")
def readiness(db: Session = Depends(get_db)) -> dict:
    return {"rows": _readiness(db)}


@router.get("/{framework}/export")
def export(framework: str, db: Session = Depends(get_db)) -> StreamingResponse:
    row = next((item for item in _readiness(db) if item["framework"] == framework), None)
    if row is None:
        raise HTTPException(404, f"Unsupported framework {framework}")
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(["framework", "readiness_pct", "met", "unmet", "disclaimer"])
    writer.writerow([row["name"], row["readiness_pct"], "; ".join(row["met"]), "; ".join(row["unmet"]), row["disclaimer"]])
    return StreamingResponse(iter([content.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{framework}-readiness.csv"'})
