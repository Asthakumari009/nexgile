"""Factor resolution and versioning.

A factor "family" is identified by (scope, category, region, method). Versions within a
family never overwrite each other - a new version is a new row and the old row's valid_to
is closed. Resolution therefore picks the version whose validity window contains the
activity's period_start. That is what makes the "factor updated -> N calculations
affected" banner honest rather than decorative.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ActivityData, EmissionFactor


class FactorResolutionError(LookupError):
    pass


# Coarse activity_type -> fine-grained factor category. Where one activity_type can burn
# more than one fuel, the fuel keyword in the description disambiguates.
_DIRECT: dict[str, str] = {
    "stationary_combustion": "natural_gas",
    "fugitive": "refrigerant_r410a",
    "purchased_electricity": "grid_electricity",
    "purchased_goods_spend": "purchased_goods_spend",
    "business_travel": "business_travel",
    "upstream_transport": "upstream_transport",
    "employee_commuting": "employee_commuting",
    "waste": "waste",
}

_FUEL_KEYWORDS: list[tuple[str, str]] = [
    ("diesel", "diesel"),
    ("petrol", "petrol"),
    ("aluminium, recycled", "aluminium_recycled"),
    ("aluminium, virgin", "aluminium_virgin"),
    ("steel", "steel"),
    ("polypropylene", "polypropylene"),
]


def category_for(activity: ActivityData) -> str:
    """Deterministic activity -> factor category."""
    if activity.activity_type in _DIRECT:
        return _DIRECT[activity.activity_type]

    desc = (activity.description or "").lower()
    for keyword, category in _FUEL_KEYWORDS:
        if keyword in desc:
            return category

    raise FactorResolutionError(
        f"Cannot derive a factor category for activity #{activity.id} "
        f"(type={activity.activity_type!r}, description={activity.description!r})."
    )


def resolve(
    db: Session,
    *,
    scope: int,
    category: str,
    on: date,
    region: str | None = None,
    method: str | None = None,
) -> EmissionFactor:
    """Pick the factor version valid on `on`. Raises a clear error if none matches."""
    stmt = select(EmissionFactor).where(
        EmissionFactor.scope == scope,
        EmissionFactor.category == category,
        EmissionFactor.valid_from <= on,
        EmissionFactor.valid_to >= on,
        EmissionFactor.method.is_(None) if method is None else EmissionFactor.method == method,
    )
    candidates = list(db.scalars(stmt))

    # A factor with region NULL is global and matches any region.
    if region is not None:
        scoped = [f for f in candidates if f.region in (None, region)]
        # Prefer a region-specific factor over the global fallback.
        exact = [f for f in scoped if f.region == region]
        candidates = exact or scoped

    if not candidates:
        raise FactorResolutionError(
            f"No emission factor found for scope={scope} category={category!r} "
            f"region={region!r} method={method!r} valid on {on.isoformat()}."
        )
    # Deterministic tie-break: newest validity window wins.
    candidates.sort(key=lambda f: (f.valid_from, f.id), reverse=True)
    return candidates[0]


# Holding a contractual instrument is a fact about the site, not about the factor
# library, so market-based eligibility has to be resolved here. If it lived only in the
# seed, every later recalculation would silently hand a REC factor to a site that holds
# no certificate.
REC_FACILITIES = {"Hyderabad Plant"}


def resolve_for_activity(
    db: Session, activity: ActivityData, method: str | None = None
) -> EmissionFactor:
    if method == "market_based" and activity.facility.name not in REC_FACILITIES:
        # No instrument at this site: GHG Protocol falls back to the residual mix,
        # proxied here by the location-based grid factor. Still reported separately.
        method = "location_based"
    return resolve(
        db,
        scope=activity.scope,
        category=category_for(activity),
        on=activity.period_start,
        region=activity.facility.country,
        method=method,
    )


def family_of(factor: EmissionFactor) -> tuple[int, str, str | None, str | None]:
    return (factor.scope, factor.category, factor.region, factor.method)


def versions(db: Session, factor: EmissionFactor) -> list[EmissionFactor]:
    """All versions in this factor's family, oldest first."""
    rows = db.scalars(
        select(EmissionFactor).where(
            EmissionFactor.scope == factor.scope,
            EmissionFactor.category == factor.category,
            EmissionFactor.region.is_(None)
            if factor.region is None
            else EmissionFactor.region == factor.region,
            EmissionFactor.method.is_(None)
            if factor.method is None
            else EmissionFactor.method == factor.method,
        )
    )
    return sorted(rows, key=lambda f: (f.valid_from, f.id))
