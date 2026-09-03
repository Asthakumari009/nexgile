"""FastAPI app. Routers get mounted here in Phase 2."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import STORAGE_DIR
from routers import emissions
from seed import seed_if_empty

app = FastAPI(title="Nexgile DecarbX", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    seed_if_empty()
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# Evidence documents are served straight off disk - the lineage panel links here.
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")


app.include_router(emissions.router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "app": "decarbx"}
