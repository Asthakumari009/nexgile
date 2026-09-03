"""Product carbon-footprint read models built from the seeded BOM and factor library."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import BomItem, EmissionFactor, Product

router = APIRouter(prefix="/api/v1/products", tags=["products"])


def _product_out(product: Product) -> dict:
    return {"id": product.id, "sku": product.sku, "name": product.name,
            "category": product.category, "functional_unit": product.functional_unit,
            "boundary": product.boundary, "status": product.status}


def _items(db: Session, product_id: int) -> list[BomItem]:
    return list(db.scalars(select(BomItem).where(BomItem.product_id == product_id).order_by(BomItem.id)))


def _item_out(item: BomItem, factors: dict[int, EmissionFactor]) -> dict:
    factor = factors.get(item.factor_id)
    kgco2e = item.mass_kg * item.quantity * factor.value_kgco2e if factor else 0.0
    return {"id": item.id, "parent_bom_item_id": item.parent_bom_item_id,
            "component_name": item.component_name, "material": item.material,
            "mass_kg": item.mass_kg, "quantity": item.quantity,
            "factor": {"id": factor.id, "code": factor.code, "version": factor.version,
                       "value_kgco2e": factor.value_kgco2e} if factor else None,
            "kgco2e": round(kgco2e, 3)}


def _pcf(db: Session, product: Product) -> dict:
    """A transparent proxy PCF, never an inventory emission or compliance claim."""
    factors = {f.id: f for f in db.scalars(select(EmissionFactor))}
    stages: dict[str, float] = defaultdict(float)
    for item in _items(db, product.id):
        factor = factors.get(item.factor_id)
        if factor is None:
            continue
        stage = "packaging" if "packaging" in item.component_name.lower() else "raw_material"
        stages[stage] += item.mass_kg * item.quantity * factor.value_kgco2e
    material = stages["raw_material"] + stages["packaging"]
    stages["manufacturing"] = material * 0.12
    stages["distribution"] = material * 0.04
    if product.boundary == "cradle_to_grave":
        stages["end_of_life"] = material * 0.03
    ordered = ["raw_material", "manufacturing", "packaging", "distribution", "end_of_life"]
    stage_rows = [{"stage": stage, "kgco2e": round(stages[stage], 3),
                   "method": "BOM x versioned factor" if stage in ("raw_material", "packaging") else "screening proxy"}
                  for stage in ordered if stages[stage] > 0]
    return {"product": _product_out(product), "stages": stage_rows,
            "total_kgco2e": round(sum(row["kgco2e"] for row in stage_rows), 3),
            "uncertainty_pct": 20.0, "verification_status": "unverified",
            "assumptions": ["Raw materials and packaging use the recorded BOM mass, quantity and factor version.",
                            "Manufacturing, distribution and end-of-life stages are screening proxies, not measured primary data.",
                            "This product footprint is separate from approved corporate inventory actuals."]}


@router.get("")
def list_products(db: Session = Depends(get_db)) -> dict:
    products = list(db.scalars(select(Product).order_by(Product.sku)))
    return {"rows": [{**_product_out(product), "pcf_kgco2e": _pcf(db, product)["total_kgco2e"]} for product in products]}


def _get_product(product_id: int, db: Session) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, f"No product with id {product_id}")
    return product


@router.get("/{product_id}/bom")
def bom(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = _get_product(product_id, db)
    factors = {f.id: f for f in db.scalars(select(EmissionFactor))}
    return {"product": _product_out(product), "rows": [_item_out(item, factors) for item in _items(db, product.id)]}


@router.get("/{product_id}/pcf")
def pcf(product_id: int, db: Session = Depends(get_db)) -> dict:
    return _pcf(db, _get_product(product_id, db))


@router.get("/{product_id}/alternatives")
def alternatives(product_id: int, db: Session = Depends(get_db)) -> dict:
    product = _get_product(product_id, db)
    virgin = db.scalar(select(EmissionFactor).where(EmissionFactor.code == "EF-ALU-V-01"))
    recycled = db.scalar(select(EmissionFactor).where(EmissionFactor.code == "EF-ALU-R-01"))
    if virgin is None or recycled is None:
        raise HTTPException(500, "Aluminium comparison factors are unavailable")
    candidates = [item for item in _items(db, product.id) if item.factor_id == virgin.id]
    current = sum(item.mass_kg * item.quantity * virgin.value_kgco2e for item in candidates)
    alternative = sum(item.mass_kg * item.quantity * recycled.value_kgco2e for item in candidates)
    return {"product": _product_out(product), "candidate_count": len(candidates),
            "current_kgco2e": round(current, 3), "alternative_kgco2e": round(alternative, 3),
            "delta_kgco2e": round(alternative - current, 3),
            "reduction_pct": round(100 * (current - alternative) / current, 1) if current else 0.0,
            "current_factor": {"code": virgin.code, "value_kgco2e": virgin.value_kgco2e},
            "alternative_factor": {"code": recycled.code, "value_kgco2e": recycled.value_kgco2e},
            "note": "Material comparison only. It does not modify the published PCF or approved inventory actuals."}
