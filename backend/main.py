"""FastAPI app. Routers get mounted here in Phase 2."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import STORAGE_DIR
from routers import emissions
from seed import seed_if_empty

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
    seed_if_empty()
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# Evidence documents are served straight off disk - the lineage panel links here.
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")


app.include_router(emissions.router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "app": "decarbx"}
