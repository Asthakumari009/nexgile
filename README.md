# Nexgile-DecarbX

Enterprise carbon intelligence platform — Scope 1/2/3 accounting with **audit-grade lineage**.

Any reported emission figure traces back through the exact chain that produced it:
calculation formula → unit conversion → versioned emission factor → activity record →
source document → approval. Nothing in that chain is recomputed for display; it is
reconstructed from what the calculation engine recorded at the time.

> **Build status:** Phases 0–1 complete and verified. Phase 2 in progress — the lineage
> endpoint is done; the remaining routers and both UIs are not. See `HANDOFF.md` for the
> current state and `CLAUDE.md` for the full spec. **The two frontends are currently
> scaffolding that health-checks the API, not finished screens.**

---

## Quick start

```bash
./run.sh
```

Starts all three servers. On first run the backend seeds a deterministic SQLite database
(~800 activity rows, 24 months) and writes evidence PDFs to `./storage/`.

| Service | URL | What it is |
|---|---|---|
| Backend API | http://localhost:8000 | FastAPI — interactive docs at `/docs` |
| Internal app | http://localhost:5173 | React — enterprise users (CSO, procurement, finance, audit) |
| Supplier portal | http://localhost:4200 | Angular — external suppliers |

Manual setup, if you would rather not use `run.sh`:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
cd backend && ../.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev     # :5173
cd portal   && npm install && npm start       # :4200
```

## Verify the engine

```bash
cd backend && ../.venv/Scripts/python.exe verify_phase1.py
```

Rebuilds the database from scratch, prints totals per scope, and asserts twelve
invariants — that a calculation is reproducible by hand, that units were converted rather
than assumed, that factor versioning selects by validity window, that one consolidation
basis governs the inventory, that every evidence PDF states the exact quantity its
calculation consumed and still matches its stored sha256, and more. If this passes, the
numbers are trustworthy.

---

## Architecture

```
                    ┌──────────────────────┐   ┌──────────────────────┐
                    │  React :5173         │   │  Angular :4200       │
                    │  internal enterprise │   │  supplier portal     │
                    │  app                 │   │  (external, plain)   │
                    └──────────┬───────────┘   └──────────┬───────────┘
                               │  /api, /storage          │
                               └────────────┬─────────────┘
                                            ▼
                            ┌───────────────────────────────┐
                            │       FastAPI :8000           │
                            │  routers/  emissions ...      │
                            ├───────────────────────────────┤
                            │  engine/                      │
                            │   factors    version + region │
                            │   units      never assume     │
                            │   calculator THE chain        │
                            │   lineage    audit trail      │
                            ├───────────────────────────────┤
                            │  SQLAlchemy 2.x → SQLite      │
                            └───────────────┬───────────────┘
                                            ▼
                      activity_data → calculations → emissions
                            │              │
                            ▼              ▼
                   evidence_documents  emission_factors (versioned)
                            │
                            ▼
                       ./storage/*.pdf
```

**Why two frontends.** This is a multi-party platform. Internal enterprise users and
external suppliers are different audiences with different trust and deployment
boundaries, so they get separate applications sharing one API. No screen is built twice.

**The calculation chain.** `activity_data` is what was measured. `calculations` records
every step of converting that into CO2e — the multiplier used, the converted quantity,
the factor value and version, the human-readable formula, the uncertainty, the
consolidation share. `emissions` is the read model the dashboard queries, written only by
the calculator. A factor version bump never mutates an approved calculation; it creates a
new version, marks the old one superseded, and removes the stale emission row so totals
cannot double-count.

---

## Deployment

Backend on Render, each frontend as its own Vercel project.

**Backend (Render).** `render.yaml` at the repo root is a blueprint — point Render at the
repo and it picks it up, or create a Web Service manually with:

| Field | Value |
|---|---|
| Root Directory | **leave blank** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/v1/health` |

Everything is relative to the repo root, so **Root Directory must be empty**. A root
`requirements.txt` shims to `backend/requirements.txt`, and `--app-dir` puts `backend/`
on the import path. The app resolves its own paths from `__file__`, so the working
directory does not matter. If Root Directory is set to `backend`, the build fails with
`Could not open requirements file`.

**Frontends (Vercel).** Create two projects from the same repo, with **Root Directory**
set to `frontend` and `portal` respectively. Each has its own `vercel.json`.

⚠️ **One required edit before deploying.** Both `frontend/vercel.json` and
`portal/vercel.json` contain the placeholder `REPLACE-WITH-YOUR-RENDER-URL.onrender.com`.
Replace it with your actual Render URL in both files. Those rewrites proxy `/api` and
`/storage` to the backend, which keeps the frontends same-origin and means no CORS
configuration is needed. If you instead call the API cross-origin, `main.py` already
allows any `*.vercel.app` origin, and `ALLOWED_ORIGINS` accepts a comma-separated list.

**Render free tier note.** The filesystem is ephemeral, so `decarbx.db` and `./storage/`
are rebuilt on every restart and cold start. Because the seed is fully deterministic this
is harmless — you get byte-identical data every time — but the first request after a
cold start pays the seeding cost. A persistent disk or Postgres removes this.

---

## Scope and honest limitations

This is a time-boxed demonstration build, not a production system. Stating plainly what
is and is not real:

**Implemented and working**

- Deterministic seed: 4 facilities, 2 entities, 24 months, ~800 activity rows, ~900 calculations
- Calculation engine with versioned factor resolution, explicit unit conversion, uncertainty propagation and consolidation allocation
- Scope 2 dual reporting — location-based and market-based side by side
- Factor versioning with supersede-not-overwrite semantics
- Full lineage endpoint, verified against every interesting case including superseded factors, unapproved drafts and missing evidence
- Evidence PDFs generated from the seeded quantities and sha256-verified, so the document states the number the calculation consumed

**Not built**

- Both UIs are scaffolding at present. The React internal app and the Angular supplier portal health-check the API and render nothing else yet.
- Remaining Phase 2 routers: org, activities, factors, calculations, emissions summary, analytics, suppliers, products, scenarios, compliance, finance, supplier portal
- CSV import, approval workflow UI, anomaly and forecast analytics, PCF and BOM rollup, scenario modelling, compliance readiness, carbon finance

**Deliberately out of scope**

- No authentication. Role switching will be a header dropdown. The source requirements document explicitly excludes security standards.
- No OCR, no LLM calls, no external API calls anywhere — nothing that can fail during a live demo.
- SQLite, not Postgres. No Docker, Redis, Celery, or object storage. Background work uses FastAPI `BackgroundTasks`.
- No multi-tenant isolation.
- The supplier portal's language switcher will be a hardcoded dictionary of three languages to demonstrate the requirement, not real i18n.

**Emission factors are publicly-cited approximations used for demonstration, not a
licensed factor library.** Values are labelled with plausible sources (DEFRA 2024, CEA
India, IPCC AR5, ecoinvent proxies) and are of the right order of magnitude, but they are
not licensed data and must not be used for actual reporting. The `ecoinvent 3.9 (proxy)`
and `EEIO proxy` labels are marked as proxies for exactly this reason.

**A production build would need** PostgreSQL with proper migrations, Celery or equivalent
for long-running imports, object storage for evidence, real ERP and utility connectors,
a licensed emission factor library with scheduled updates, tenant isolation, an actual
authentication and authorisation model, and independent third-party verification of the
methodology.

---

## Current API

```
GET  /api/v1/health
GET  /api/v1/emissions/{id}/lineage      the key endpoint
GET  /storage/{filename}                 evidence documents
GET  /docs                               interactive API docs
```

Try the lineage endpoint against a seeded emission:

```bash
curl http://localhost:8000/api/v1/emissions/37/lineage
```

Emission 37 is Hyderabad Plant purchased electricity for Jul 2025. The chain runs from
1,122.7 tCO2e down to `TSSPDCL_Invoice_Jul2025.pdf`, whose stated consumption matches the
activity quantity exactly. Emission 316 is the deliberate Pune gas anomaly; its meter
reading PDF closes from opening to closing to precisely the recorded consumption.
