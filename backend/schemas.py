"""All Pydantic schemas. One file on purpose - see CLAUDE.md section 3."""
from pydantic import BaseModel


class LineageStep(BaseModel):
    step: str
    label: str
    value: str
    detail: str
    url: str | None = None


class LineageEmission(BaseModel):
    id: int
    tco2e: float
    period: str
    facility: str
    scope: int


class LineageResponse(BaseModel):
    emission: LineageEmission
    chain: list[LineageStep]
    assumptions: list[str]
    uncertainty_pct: float
    confidence: str
