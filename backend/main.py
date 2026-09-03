"""FastAPI app. Routers get mounted here in Phase 2."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, STORAGE_DIR, engine
from routers import activities, analytics, calculations, compliance, emissions, factors, finance, org, products, scenarios, suppliers
from schemas import ResetDemoRequest
from seed import bootstrap_reference_data

app = FastAPI(title="Nexgile DecarbX", version="0.1.0")

# Both frontends proxy /api to this service, in dev via their own dev server and in
# production via a Vercel rewrite, so same-origin is the normal case and CORS is only a
# fallback for hitting the API directly from a deployed frontend.
ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4200").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    bootstrap_reference_data()
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# Evidence documents are served straight off disk - the lineage panel links here.
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")


for _router in (org.router, activities.router, factors.router, calculations.router,
                emissions.router, analytics.router, suppliers.router, products.router,
                scenarios.router, compliance.router, finance.router):
    app.include_router(_router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "app": "decarbx"}


@app.post("/api/v1/admin/reset")
def reset_demo_data(req: ResetDemoRequest) -> dict:
    """Demo-only destructive reset, deliberately guarded by an explicit confirmation."""
    if req.confirmation != "DELETE_DEMO_DATA":
        return {"reset": False, "detail": "Send confirmation DELETE_DEMO_DATA to reset"}
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for path in STORAGE_DIR.iterdir():
        if path.is_file():
            path.unlink()
    bootstrap_reference_data()
    return {"reset": True, "detail": "Operational data cleared; reference factors retained"}
