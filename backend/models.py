"""All SQLAlchemy models. One file on purpose - see CLAUDE.md section 3."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# --------------------------------------------------------------------------- org
class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    base_currency: Mapped[str] = mapped_column(String, default="INR")
    baseline_year: Mapped[int] = mapped_column(Integer)
    target_year: Mapped[int] = mapped_column(Integer)
    target_reduction_pct: Mapped[float] = mapped_column(Float)

    entities: Mapped[list["Entity"]] = relationship(back_populates="org")


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    ownership_pct: Mapped[float] = mapped_column(Float)
    consolidation_method: Mapped[str] = mapped_column(String)

    org: Mapped["Organization"] = relationship(back_populates="entities")
    facilities: Mapped[list["Facility"]] = relationship(back_populates="entity")


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    facility_type: Mapped[str] = mapped_column(String)
    floor_area_m2: Mapped[float] = mapped_column(Float)

    entity: Mapped["Entity"] = relationship(back_populates="facilities")
    departments: Mapped[list["Department"]] = relationship(back_populates="facility")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String)
    cost_center: Mapped[str] = mapped_column(String)

    facility: Mapped["Facility"] = relationship(back_populates="departments")


# ----------------------------------------------------------------- factors + units
class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    scope: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)  # denominator, e.g. kWh
    value_kgco2e: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    uncertainty_pct: Mapped[float] = mapped_column(Float)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UnitConversion(Base):
    __tablename__ = "unit_conversions"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_unit: Mapped[str] = mapped_column(String, index=True)
    to_unit: Mapped[str] = mapped_column(String, index=True)
    multiplier: Mapped[float] = mapped_column(Float)


# ------------------------------------------------------------------------ evidence
class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    doc_type: Mapped[str] = mapped_column(String)
    uploaded_by: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    sha256: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    page_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


# ------------------------------------------------------------- activity + calc chain
class ActivityData(Base):
    __tablename__ = "activity_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    scope: Mapped[int] = mapped_column(Integer, index=True)
    ghg_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_type: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date)
    data_source: Mapped[str] = mapped_column(String)
    data_quality: Mapped[str] = mapped_column(String)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_documents.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    facility: Mapped["Facility"] = relationship()
    department: Mapped["Department | None"] = relationship()
    evidence: Mapped["EvidenceDocument | None"] = relationship()


class Calculation(Base):
    __tablename__ = "calculations"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity_data.id"), index=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("emission_factors.id"), index=True)
    methodology: Mapped[str] = mapped_column(String)
    methodology_version: Mapped[str] = mapped_column(String)
    input_quantity: Mapped[float] = mapped_column(Float)
    input_unit: Mapped[str] = mapped_column(String)
    conversion_multiplier: Mapped[float] = mapped_column(Float)
    converted_quantity: Mapped[float] = mapped_column(Float)
    converted_unit: Mapped[str] = mapped_column(String)
    factor_value: Mapped[float] = mapped_column(Float)
    formula_text: Mapped[str] = mapped_column(String)
    result_kgco2e: Mapped[float] = mapped_column(Float)
    uncertainty_pct: Mapped[float] = mapped_column(Float)
    allocation_basis: Mapped[str] = mapped_column(String)
    allocation_pct: Mapped[float] = mapped_column(Float)
    calc_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("calculations.id"), nullable=True)

    activity: Mapped["ActivityData"] = relationship()
    factor: Mapped["EmissionFactor"] = relationship()


class Emission(Base):
    """Read model for the dashboard. Only calculator.py writes here."""

    __tablename__ = "emissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    calculation_id: Mapped[int] = mapped_column(ForeignKey("calculations.id"), index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    scope: Mapped[int] = mapped_column(Integer, index=True)
    ghg_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_month: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM
    tco2e: Mapped[float] = mapped_column(Float)
    data_quality: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)

    calculation: Mapped["Calculation"] = relationship()


# ----------------------------------------------------------------------- suppliers
class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    tier: Mapped[int] = mapped_column(Integer)
    parent_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    category: Mapped[str] = mapped_column(String)
    annual_spend: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String)
    engagement_status: Mapped[str] = mapped_column(String)
    maturity: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    scope3_tco2e: Mapped[float] = mapped_column(Float)
    carbon_intensity: Mapped[float] = mapped_column(Float)
    yoy_change_pct: Mapped[float] = mapped_column(Float)


class SupplierSubmission(Base):
    __tablename__ = "supplier_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    period: Mapped[str] = mapped_column(String)
    reported_scope1: Mapped[float] = mapped_column(Float)
    reported_scope2: Mapped[float] = mapped_column(Float)
    reported_scope3: Mapped[float] = mapped_column(Float)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_documents.id"), nullable=True)
    validation_state: Mapped[str] = mapped_column(String, default="pending")
    attested: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewer_note: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)


# ---------------------------------------------------------------------- product/PCF
class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    sku: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    functional_unit: Mapped[str] = mapped_column(String)
    boundary: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class BomItem(Base):
    __tablename__ = "bom_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    parent_bom_item_id: Mapped[int | None] = mapped_column(ForeignKey("bom_items.id"), nullable=True)
    component_name: Mapped[str] = mapped_column(String)
    material: Mapped[str] = mapped_column(String)
    mass_kg: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    factor_id: Mapped[int | None] = mapped_column(ForeignKey("emission_factors.id"), nullable=True)


class PcfResult(Base):
    __tablename__ = "pcf_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    stage: Mapped[str] = mapped_column(String)
    kgco2e: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String)
    uncertainty_pct: Mapped[float] = mapped_column(Float)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_documents.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    verification_status: Mapped[str] = mapped_column(String)


# ----------------------------------------------------------------------- scenarios
class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String)
    base_period: Mapped[str] = mapped_column(String)
    levers_json: Mapped[str] = mapped_column(String)
    result_tco2e: Mapped[float] = mapped_column(Float)
    baseline_tco2e: Mapped[float] = mapped_column(Float)
    capex: Mapped[float] = mapped_column(Float)
    annual_saving: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="draft")


# ------------------------------------------------------------------ finance/targets
class CarbonBudget(Base):
    __tablename__ = "carbon_budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    year: Mapped[int] = mapped_column(Integer)
    budget_tco2e: Mapped[float] = mapped_column(Float)
    actual_tco2e: Mapped[float] = mapped_column(Float)


class ReductionLever(Base):
    __tablename__ = "reduction_levers"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    potential_tco2e: Mapped[float] = mapped_column(Float)
    capex: Mapped[float] = mapped_column(Float)
    opex_delta: Mapped[float] = mapped_column(Float)
    payback_years: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String)


class Offset(Base):
    __tablename__ = "offsets"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    project_name: Mapped[str] = mapped_column(String)
    registry: Mapped[str] = mapped_column(String)
    vintage: Mapped[int] = mapped_column(Integer)
    tonnes: Mapped[float] = mapped_column(Float)
    price_per_tonne: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)
    retirement_evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_documents.id"), nullable=True)
