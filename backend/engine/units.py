"""Unit conversion. Never silently assume the activity unit matches the factor unit."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import UnitConversion

# Seeded into unit_conversions. Identity pairs are implicit (multiplier 1.0).
CONVERSIONS: list[tuple[str, str, float]] = [
    ("MWh", "kWh", 1000.0),
    ("GJ", "kWh", 277.778),
    ("kWh", "MWh", 0.001),
    ("m3", "m3", 1.0),
    ("scm", "m3", 1.0),
    ("litre", "litre", 1.0),
    ("kl", "litre", 1000.0),
    ("tonne", "kg", 1000.0),
    ("kg", "kg", 1.0),
    ("g", "kg", 0.001),
    ("km", "km", 1.0),
    ("mile", "km", 1.609344),
    ("passenger-km", "passenger-km", 1.0),
    ("tonne-km", "tonne-km", 1.0),
    ("INR", "INR", 1.0),
    ("lakh_INR", "INR", 100000.0),
]


class UnitConversionError(ValueError):
    pass


def convert(db: Session, quantity: float, from_unit: str, to_unit: str) -> tuple[float, float]:
    """Return (multiplier, converted_quantity). Raises if no route is defined."""
    if from_unit == to_unit:
        return 1.0, quantity

    row = db.scalar(
        select(UnitConversion).where(
            UnitConversion.from_unit == from_unit, UnitConversion.to_unit == to_unit
        )
    )
    if row is None:
        raise UnitConversionError(
            f"No unit conversion defined for {from_unit!r} -> {to_unit!r}. "
            "Add a row to unit_conversions rather than assuming the units match."
        )
    return row.multiplier, quantity * row.multiplier


def seed_conversions(db: Session) -> None:
    db.add_all(
        UnitConversion(from_unit=f, to_unit=t, multiplier=m) for f, t, m in CONVERSIONS
    )
