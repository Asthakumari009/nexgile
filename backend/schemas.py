"""All Pydantic schemas. One file on purpose - see CLAUDE.md section 3."""
from pydantic import BaseModel, Field


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


class SupplierSubmissionRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}$")
    reported_scope1: float = Field(ge=0)
    reported_scope2: float = Field(ge=0)
    reported_scope3: float = Field(ge=0)
    evidence_id: int | None = None
    attested: bool


class ActivityCreateRequest(BaseModel):
    facility_id: int
    scope: int = Field(ge=1, le=3)
    activity_type: str
    description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    period_start: str
    period_end: str
    data_source: str = "invoice"
    data_quality: str = "primary"
    evidence_id: int | None = None


class CompanySetupRequest(BaseModel):
    company_name: str = Field(min_length=2)
    country: str = Field(min_length=2, max_length=2)
    entity_name: str = Field(min_length=2)


class FacilityCreateRequest(BaseModel):
    entity_id: int
    name: str = Field(min_length=2)
    city: str = Field(min_length=2)
    country: str = Field(min_length=2, max_length=2)
    facility_type: str = "manufacturing"


class ResetDemoRequest(BaseModel):
    confirmation: str


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2, max_length=2)
    category: str = Field(min_length=2)
