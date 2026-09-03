# Nexgile-DecarbX — 3 Hour Build Spec

You are building a working demo of an enterprise carbon intelligence platform for a placement drive evaluation. **Read this entire file before writing any code.**

---

## 0. Prime directive

There is a hard 3 hour limit. A running app with 5 excellent screens beats a broken app with 20 stubs.

The single most important feature is **LINEAGE**: any emission number on the dashboard must be clickable and expand into the full audit trail (source document → activity data → unit conversion → emission factor + version → formula → result → approval + timestamp). This is what the requirements document emphasizes more than anything else. If you run out of time, sacrifice anything except lineage.

**Git commit after every phase.** If Phase 5 breaks the build, Phase 4 must still be demoable.

---

## 1. Hard constraints — do not deviate

| Rule | Reason |
|---|---|
| SQLite via SQLAlchemy. No PostgreSQL. | Zero setup time |
| No Docker, no Redis, no Celery, no S3 | Infra eats the clock |
| No LLM calls, no OCR, no external APIs | Cannot fail during a live demo |
| Background jobs = FastAPI `BackgroundTasks` only | Good enough, zero deps |
| Auth = a header dropdown that switches role. No login page, no JWT. | Requirements doc explicitly says "no security standards" |
| Two frontends. React = internal app. Angular = supplier portal. Never both for the same screen. | The client asked for React + Angular. This is the only sane reading |
| File uploads land in `./storage/` on disk | Object storage is a deploy concern, not a demo concern |
| Every seeded number must be deterministic | Demo must look identical every run |

## 2. Stack

```
backend/   Python 3.11, FastAPI, SQLAlchemy 2.x, Pydantic v2, pandas, uvicorn
frontend/  React 18 + Vite + TypeScript, TailwindCSS, Recharts, React Router, TanStack Query
portal/    Angular 17 standalone components + TypeScript, plain CSS, HttpClient
db/        SQLite file at backend/decarbx.db
```

Backend `:8000`. React internal app `:5173`. Angular supplier portal `:4200`. Both frontends proxy `/api` to the backend.

**Why two frameworks.** This is a multi-party platform. Internal enterprise users (CSO, procurement, finance, auditors) and external suppliers are separate audiences with separate deployment and trust boundaries, so they get separate applications sharing one API. That is the justification to give when asked. Do not build any screen twice.

**Angular scaffold is slow.** Run `ng new portal --standalone --routing --style=css --skip-tests` in the background during Phase 0 while you work on the backend. Do not sit and watch it. Use standalone components only, no NgModules, no NgRx, no Angular Material. Three components total.

---

## 3. Repository layout

```
decarbx/
├── CLAUDE.md
├── README.md
├── run.sh                      # starts both servers
├── backend/
│   ├── main.py                 # FastAPI app, CORS, router mounting
│   ├── database.py             # engine, SessionLocal, get_db
│   ├── models.py               # ALL SQLAlchemy models in one file
│   ├── schemas.py              # ALL Pydantic schemas in one file
│   ├── seed.py                 # deterministic seed, run once at startup if db empty
│   ├── engine/
│   │   ├── factors.py          # factor resolution + versioning
│   │   ├── units.py            # unit conversion table
│   │   ├── calculator.py       # THE calculation engine
│   │   ├── lineage.py          # builds the audit trail graph
│   │   ├── analytics.py        # pareto, z-score anomalies, forecast
│   │   ├── scenarios.py        # what-if, in-memory only
│   │   ├── pcf.py              # BOM rollup
│   │   └── compliance.py       # readiness scoring
│   └── routers/
│       ├── org.py  activities.py  factors.py  calculations.py
│       ├── emissions.py  suppliers.py  products.py
│       ├── scenarios.py  analytics.py  compliance.py  finance.py
├── frontend/                   # React — internal enterprise app
│   └── src/
│       ├── App.tsx  api.ts  types.ts
│       ├── components/  Shell.tsx RoleSwitcher.tsx KpiCard.tsx LineagePanel.tsx DataQualityBadge.tsx
│       └── pages/  Dashboard Accounting Lineage Factors Suppliers Products Scenarios Compliance Finance
└── portal/                     # Angular — external supplier portal
    └── src/app/
        ├── api.service.ts
        ├── invite/             # token landing, supplier identity, deadline
        ├── submission/         # guided questionnaire form + evidence upload
        └── status/             # submission state, validation result, scorecard
```

Keep models and schemas in single files. Do not build a 40-directory hexagonal architecture. This is a 3 hour build.

---

## 4. Data model

Create these tables exactly. Every emission-producing path must be reconstructible.

**Org hierarchy**
- `organizations` — id, name, base_currency, baseline_year, target_year, target_reduction_pct
- `entities` — id, org_id, name, country, ownership_pct, consolidation_method
- `facilities` — id, entity_id, name, city, country, lat, lon, facility_type, floor_area_m2
- `departments` — id, facility_id, name, cost_center

**Factors and units**
- `emission_factors` — id, code, name, scope, category, unit (denominator), value_kgco2e, source ("DEFRA 2024", "CEA India 2024", "ecoinvent 3.9 (proxy)"), version, valid_from, valid_to, uncertainty_pct, region, method ("location_based" | "market_based" | null), is_active
- `unit_conversions` — id, from_unit, to_unit, multiplier

Factors are **versioned, never edited**. A new version is a new row with the old row's `valid_to` closed. Expose a "Factor updated → N calculations affected" banner using this.

**Evidence**
- `evidence_documents` — id, filename, doc_type ("invoice"|"meter_reading"|"certificate"|"attestation"|"supplier_report"), uploaded_by, uploaded_at, sha256, file_path, page_ref, notes

**Activity + calculation (the core chain)**
- `activity_data` — id, facility_id, department_id, scope (1|2|3), ghg_category (int 1-15 for scope 3, null otherwise), activity_type ("stationary_combustion","mobile_combustion","fugitive","process","purchased_electricity","purchased_goods_spend","business_travel","upstream_transport","waste","employee_commuting","use_phase","end_of_life"), description, quantity, unit, period_start, period_end, data_source ("meter"|"invoice"|"erp"|"supplier_primary"|"estimate"), data_quality ("primary"|"secondary"|"estimated"), evidence_id, supplier_id (nullable), created_at
- `calculations` — id, activity_id, factor_id, methodology ("location_based","market_based","spend_based","activity_based","supplier_specific","distance_based"), methodology_version, input_quantity, input_unit, conversion_multiplier, converted_quantity, converted_unit, factor_value, formula_text (e.g. `1,782,000 kWh × 0.716 kgCO2e/kWh`), result_kgco2e, uncertainty_pct, allocation_basis, allocation_pct, calc_version (int), status ("draft"|"pending_approval"|"approved"|"superseded"), created_by, created_at, approved_by, approved_at, superseded_by_id
- `emissions` — id, calculation_id, facility_id, entity_id, scope, ghg_category, period_month (YYYY-MM), tco2e, data_quality, confidence ("high"|"medium"|"low")

`emissions` is the read model the dashboard queries. Never write to it directly outside the calculator.

**Suppliers**
- `suppliers` — id, org_id, name, country, lat, lon, tier (1|2|3), parent_supplier_id, category, annual_spend, currency, engagement_status ("not_invited"|"invited"|"in_progress"|"submitted"|"validated"), maturity ("low"|"developing"|"advanced"), score (0-100), scope3_tco2e, carbon_intensity, yoy_change_pct
- `supplier_submissions` — id, supplier_id, period, reported_scope1, reported_scope2, reported_scope3, evidence_id, validation_state ("pending"|"passed"|"failed"), attested (bool), reviewer_note, submitted_at

**Product / PCF**
- `products` — id, org_id, sku, name, category, functional_unit, boundary ("cradle_to_gate"|"cradle_to_grave"), status
- `bom_items` — id, product_id, parent_bom_item_id (self-referencing tree), component_name, material, mass_kg, quantity, supplier_id, factor_id
- `pcf_results` — id, product_id, stage ("raw_material"|"manufacturing"|"packaging"|"distribution"|"use"|"end_of_life"), kgco2e, method, uncertainty_pct, evidence_id, version, verification_status ("unverified"|"internal_review"|"third_party_verified")

**Scenarios**
- `scenarios` — id, org_id, name, base_period, levers_json, result_tco2e, baseline_tco2e, capex, annual_saving, status ("draft"|"modelled")
- Scenarios **never** write to `emissions` or `calculations`. Compute in memory and return. Show a badge on the UI: "Scenario — does not modify approved actuals."

**Finance / targets**
- `carbon_budgets` — id, entity_id, year, budget_tco2e, actual_tco2e
- `reduction_levers` — id, org_id, name, category, potential_tco2e, capex, opex_delta, payback_years, status ("proposed"|"approved"|"in_progress"|"complete"), owner
- `offsets` — id, org_id, project_name, registry, vintage, tonnes, price_per_tonne, status ("purchased"|"retired"), retirement_evidence_id

---

## 5. The calculation engine

`engine/calculator.py` exposes:

```python
def calculate(db, activity: ActivityData, methodology: str, actor: str) -> Calculation
```

Steps, in order, each recorded on the row:

1. **Resolve factor** — match on scope, category, activity_type, region, method, and `valid_from <= period_start <= valid_to`. Raise a clear error if none found.
2. **Convert units** — look up `unit_conversions`, store the multiplier and the converted quantity. Never silently assume units match.
3. **Compute** — `converted_quantity * factor_value * allocation_pct`.
4. **Record formula text** as a human-readable string. This is displayed verbatim in the lineage panel.
5. **Propagate uncertainty** from the factor.
6. **Write calculation** with `calc_version = 1`, `status = "draft"`.
7. **Write emission row** in tCO2e.

Recalculation (when a factor version changes): create a **new** calculation with `calc_version + 1`, mark the old one `superseded`, set `superseded_by_id`, and expose the delta. Never mutate an approved calculation.

Approval: `POST /calculations/{id}/approve` sets status, approver, timestamp. The dashboard has a toggle for "approved only" vs "all".

**Scope 2 dual reporting**: for every `purchased_electricity` activity, produce two calculations, one `location_based` and one `market_based`. Facilities with renewable certificates get a market-based factor near zero. Show both numbers side by side on the dashboard. This directly answers a named requirement and takes 15 extra minutes.

---

## 6. Seed data — deterministic, run at startup if DB is empty

**Org**: "Nexgile Industries Ltd", baseline 2023, target 2030, 42% reduction.

**Entities**: Nexgile India Pvt Ltd (100%, operational control), Nexgile Europe GmbH (75%).

**Facilities**:
| Facility | Entity | Location | Type |
|---|---|---|---|
| Hyderabad Plant | India | Hyderabad, IN | manufacturing |
| Pune Plant | India | Pune, IN | manufacturing |
| Chennai Warehouse | India | Chennai, IN | warehouse |
| Munich Assembly | Europe | Munich, DE | manufacturing |

**Emission factors** (label the source string honestly as demo proxies):

| code | name | scope | unit | kgCO2e | source | version |
|---|---|---|---|---|---|---|
| EF-NG-01 | Natural gas, stationary | 1 | m3 | 2.02 | DEFRA 2024 | v1 |
| EF-DSL-01 | Diesel, mobile | 1 | litre | 2.68 | DEFRA 2024 | v1 |
| EF-PET-01 | Petrol, mobile | 1 | litre | 2.31 | DEFRA 2024 | v1 |
| EF-R410-01 | R-410A fugitive (GWP) | 1 | kg | 2088 | IPCC AR5 | v1 |
| EF-GRID-IN-01 | India grid, location-based | 2 | kWh | 0.727 | CEA 2023 | v1 |
| EF-GRID-IN-02 | India grid, location-based | 2 | kWh | 0.716 | CEA 2024 | v2 |
| EF-GRID-IN-MKT | India grid, market-based (REC) | 2 | kWh | 0.041 | Contractual | v1 |
| EF-GRID-DE-01 | Germany grid, location-based | 2 | kWh | 0.363 | AIB 2024 | v1 |
| EF-STEEL-01 | Steel, primary | 3 | kg | 1.85 | ecoinvent 3.9 (proxy) | v1 |
| EF-ALU-V-01 | Aluminium, virgin | 3 | kg | 16.50 | ecoinvent 3.9 (proxy) | v1 |
| EF-ALU-R-01 | Aluminium, recycled | 3 | kg | 2.30 | ecoinvent 3.9 (proxy) | v1 |
| EF-PP-01 | Polypropylene | 3 | kg | 1.95 | ecoinvent 3.9 (proxy) | v1 |
| EF-SPEND-MFG | Purchased goods, spend-based | 3 | INR | 0.00052 | EEIO proxy | v1 |
| EF-AIR-01 | Air travel, long haul | 3 | passenger-km | 0.150 | DEFRA 2024 | v1 |
| EF-ROAD-01 | Road freight | 3 | tonne-km | 0.107 | DEFRA 2024 | v1 |
| EF-COMMUTE-01 | Employee commuting | 3 | km | 0.130 | DEFRA 2024 | v1 |
| EF-WASTE-LF-01 | Waste to landfill | 3 | kg | 0.450 | DEFRA 2024 | v1 |

Note `EF-GRID-IN-01` → `EF-GRID-IN-02` is a deliberate version bump so you can demo the recalculation impact banner.

**Activity data**: 24 months (Jan 2024 – Dec 2025) across all 4 facilities, roughly 700-900 rows. Use a fixed random seed. Bake in:
- Seasonal variation (higher electricity in Indian summer months).
- A **deliberate anomaly**: Pune Plant natural gas in Aug 2025 at ~3.2x its normal value. The anomaly detector must catch this live.
- **Deliberate data gaps**: Munich Assembly has no Scope 3 waste data for Q4 2025, Chennai Warehouse has no refrigerant data. The data-quality panel must surface these.
- A mix of `primary` / `secondary` / `estimated` quality so the confidence badges are not all green.

**Evidence**: generate ~12 small placeholder PDFs or text files in `./storage/` (electricity invoice, gas meter reading, REC certificate, supplier attestation) and link them to activity rows. The lineage panel must show a real, openable document at the bottom of the chain.

**Suppliers**: 12 suppliers, tiers 1-3 with `parent_supplier_id` set so a network graph is possible, spread across India, Germany, China, Vietnam, with lat/lon for the map. Vary engagement_status and score so the scorecard table looks real.

**Products**: 2 SKUs with multi-level BOMs.
- `NX-CTRL-100` Industrial Controller: housing (aluminium 0.8kg) → PCB assembly → (IC, capacitors, PCB substrate), display, packaging.
- `NX-PUMP-250` Pump Unit: steel body 12kg, motor, seals, packaging.

**Reduction levers**: 6 seeded (rooftop solar, PPA, LED retrofit, recycled aluminium substitution, supplier switch, freight mode shift) with capex, potential, payback.

---

## 7. API surface

```
GET  /api/v1/org/tree                              org > entities > facilities
GET  /api/v1/activities?scope=&facility=&period=&quality=
POST /api/v1/activities
POST /api/v1/activities/import           CSV upload, BackgroundTasks, returns job_id
GET  /api/v1/activities/import/{job_id}  {total, processed, succeeded, failed, errors[]}
GET  /api/v1/factors?scope=&active=
GET  /api/v1/factors/{id}/versions
GET  /api/v1/factors/{id}/impact         calculations affected by a version change
POST /api/v1/calculations                run calc for an activity
POST /api/v1/calculations/{id}/approve
POST /api/v1/calculations/recalculate    factor version bump, returns delta report
GET  /api/v1/emissions/summary?group_by=scope|facility|entity|category|month|supplier
GET  /api/v1/emissions/{id}/lineage      ← THE KEY ENDPOINT
GET  /api/v1/analytics/hotspots          pareto, cumulative %
GET  /api/v1/analytics/anomalies         z-score > 2.0
GET  /api/v1/analytics/forecast          linear trend + target trajectory + gap
GET  /api/v1/analytics/data-quality      completeness % by facility and scope
GET  /api/v1/suppliers                   + /{id}/scorecard  + /network
POST /api/v1/suppliers/{id}/invite
POST /api/v1/suppliers/{id}/submissions
GET  /api/v1/products  + /{id}/bom  + /{id}/pcf  + /{id}/alternatives
POST /api/v1/scenarios                   in-memory, never persists to emissions
GET  /api/v1/compliance/readiness        per framework
GET  /api/v1/compliance/{framework}/export
GET  /api/v1/finance/summary             budget, internal price exposure, offsets, lever ROI
```

### Lineage response shape (build this first, everything else hangs off it)

```json
{
  "emission": { "id": 4821, "tco2e": 1244.7, "period": "2025-07", "facility": "Hyderabad Plant", "scope": 2 },
  "chain": [
    { "step": "reported_value",   "label": "Reported emission", "value": "1,244.7 tCO2e", "detail": "Scope 2, location-based, Jul 2025" },
    { "step": "calculation",      "label": "Calculation #4821 v1", "value": "1,782,000 kWh × 0.716 kgCO2e/kWh", "detail": "Methodology: location_based v2024.1 | Allocation: 100% operational control" },
    { "step": "unit_conversion",  "label": "Unit conversion", "value": "1,782 MWh → 1,782,000 kWh", "detail": "multiplier 1000" },
    { "step": "emission_factor",  "label": "EF-GRID-IN-02 v2", "value": "0.716 kgCO2e/kWh", "detail": "CEA India 2024 | valid 2024-01-01 to 2025-12-31 | uncertainty ±5%" },
    { "step": "activity_data",    "label": "Activity record #1193", "value": "1,782 MWh purchased electricity", "detail": "Source: invoice | Quality: primary | Period 2025-07-01 to 2025-07-31" },
    { "step": "evidence",         "label": "TSSPDCL_Invoice_Jul2025.pdf", "value": "sha256 a91f…", "detail": "Uploaded by k.rao 2025-08-04", "url": "/storage/…" },
    { "step": "approval",         "label": "Approved", "value": "s.mehta", "detail": "2025-08-06 11:24 IST" }
  ],
  "assumptions": ["Operational control consolidation", "Grid factor applied at national level, no state-level split available"],
  "uncertainty_pct": 5.0,
  "confidence": "high"
}
```

Render this as a vertical timeline with connector lines. Make it look good. This is the screen the evaluator will remember.

---

## 8. Frontend pages

Persistent shell: left nav, top bar with **role switcher** (CSO / Procurement / CFO / Auditor) and an org+period selector. Role changes which KPI cards and nav items are visible. That single dropdown satisfies the "role-based views" requirement cheaply.

1. **Dashboard** — 4 KPI cards (total tCO2e, intensity per revenue, vs target, data quality %), scope split donut, 24-month trend line with target trajectory overlay, Pareto hotspot bar, top 5 anomalies list, Scope 2 location vs market side by side. **Every number is clickable and opens the lineage drawer.**
2. **Carbon Accounting** — filterable activity table (scope, facility, period, quality), quality badges, CSV upload with progress and an error table, row click → calculation detail → lineage. Approve button.
3. **Emission Factors** — library table, version history, and a "recalculate impact" action showing "37 calculations affected, +2.4% total emissions".
4. **Suppliers** — table with scorecards and rankings, tier network view (nested list or simple SVG graph, do not fight a graph library), map of supplier locations, engagement funnel, carbon-adjusted TCO comparator for two suppliers (price + carbon × internal price).
5. **Products / PCF** — BOM tree, stage-by-stage PCF waterfall, alternative material comparison (virgin vs recycled aluminium showing the delta), ISO 14067-style report panel listing assumptions, uncertainty, boundary, verification status.
6. **Scenarios** — sliders for renewable electricity %, recycled material %, freight mode shift, supplier switch. Live recompute against the baseline, side-by-side chart, plus a prominent "Scenario output. Approved actuals unchanged." badge. Monte Carlo: 1000 iterations sampling factor uncertainty, render a P5/P50/P95 range.
7. **Compliance** — cards for CSRD/ESRS, CBAM, TCFD, EU Taxonomy, SEC, CDP. Each shows a readiness % computed from real data completeness, a checklist of met/unmet datapoints, and an export button producing a disclosure table.
8. **Carbon Finance** — budget vs actual by entity, internal carbon price exposure (emissions × price, adjustable), offset registry with retirement evidence, reduction lever ROI table sorted by cost per tonne (marginal abatement cost curve as a bar chart).

Design: dense enterprise UI. Slate/zinc neutrals, one accent color, tabular numerals for figures, small badges for data quality. Do not use a purple gradient hero. This should look like software a CFO uses.

---

## 8b. Angular supplier portal (`portal/`, port 4200)

Three routes, standalone components, no auth beyond an opaque invite token in the URL. Deliberately plain and light. Suppliers are small vendors on bad connections, so this should look nothing like the internal app.

**`/invite/:token`** — resolves the token to a supplier. Shows supplier name, requesting company, reporting period, deadline countdown, what data is being asked for, and a "Start submission" button. A language dropdown (English / हिन्दी / Deutsch) that swaps a small hardcoded label dictionary. Do not build real i18n. Three languages in a TS object is enough to demonstrate the 25-language requirement.

**`/submit/:token`** — the guided questionnaire, one section at a time with a progress bar:
1. Company details (confirm name, country, sector, employees)
2. Scope 1 (fuel type, quantity, unit)
3. Scope 2 (electricity kWh, renewable share, REC held yes/no)
4. Evidence upload (file input, posts to the backend, shows what was received)
5. Attestation (checkbox: data is accurate to the best of our knowledge, signatory name and role)

Inline validation as they type: negative numbers rejected, units required, an implausible-value warning if kWh per employee is wildly out of range. Show the validation state live, because "validations, attestations, evidence" is a named requirement.

**`/status/:token`** — submission received, validation result (passed / flagged with reasons), current supplier score and maturity band, year-over-year change, and any improvement actions assigned by the buyer.

Backend additions for the portal:

```
GET  /api/v1/portal/{token}                  supplier + questionnaire definition + deadline
POST /api/v1/portal/{token}/submission       creates supplier_submissions, runs validation
POST /api/v1/portal/{token}/evidence         file upload → evidence_documents
GET  /api/v1/portal/{token}/status           validation state + score
```

Seed each supplier with a deterministic token (`sup-{id}-demo`) and print the portal URLs at seed time so you can open one instantly during the demo.

**The connection that matters:** a submission made in the Angular portal must immediately appear in the React app's supplier table, flow into Scope 3 via `supplier_specific` methodology, and show up in the lineage chain with the supplier's uploaded evidence document at the bottom. Demonstrating that round trip live is the entire point of building two frontends.

---

## 9. Build order — commit after each phase

| Phase | Time | Deliverable |
|---|---|---|
| 0 | 0:00–0:10 | Kick off `ng new portal` in the background immediately. While it installs: scaffold backend + React, `run.sh` starting all three, hello world through both proxies |
| 1 | 0:10–0:45 | `models.py`, `seed.py`, `engine/calculator.py` + units + factors. Verify by printing total tCO2e per scope. **Non-negotiable. Do not move on until the totals are right.** |
| 2 | 0:45–1:10 | Routers: org, activities, factors, calculations, emissions summary, **lineage**, portal endpoints |
| 3 | 1:10–1:55 | React shell, role switcher, Dashboard, Accounting table, **LineagePanel**. Commit hard here, this alone is demoable. |
| 4 | 1:55–2:25 | Angular portal: all three routes, upload, validation, attestation. Verify the round trip into the React supplier table. |
| 5 | 2:25–2:50 | React: Suppliers, Products/PCF, Scenarios, anomalies |
| 6 | 2:50–3:00 | Compliance + Finance as static computed cards, README, demo script, final commit |

Phase 4 is now protected. Two working frontends is an explicit requirement, so the Angular portal outranks the Products, Scenarios, and Compliance pages. If you are behind at 1:55, ship Phase 4 anyway and cut Phase 5 down to the Suppliers page only.

If you are behind at 1:10, cut the Angular portal to **two** routes (invite and submit, drop status) rather than dropping it entirely. A thin Angular app satisfies the requirement. A missing one does not.

---

## 10. README must contain

- One-command start: `./run.sh`
- An architecture diagram (ASCII is fine)
- **A "Scope and honest limitations" section.** State plainly what is implemented, what is stubbed, and what a production build would need (Postgres, Celery, real ERP connectors, licensed factor libraries, tenant isolation, OCR). Do not oversell. An evaluator who catches you claiming CBAM compliance you did not build will discount everything else you did.
- Note that emission factors are publicly-cited approximations used for demonstration, not a licensed factor library.

## 11. Demo script (put in README, memorize it)

1. Dashboard: total emissions, split by scope, above target trajectory.
2. Click `1,244.7 tCO2e` → lineage panel opens → walk the chain down to the invoice PDF → open the PDF. **This is the moment that wins.**
3. Emission Factors → CEA 2023 → 2024 version bump → "37 calculations affected, +2.4%" → recalculate → new calculation version created, old one superseded, not overwritten.
4. Analytics → anomaly flag on Pune Aug 2025 natural gas → click through to the underlying record.
5. Suppliers → scorecard → carbon-adjusted TCO: cheaper supplier loses once carbon is priced in.
6. Products → NX-CTRL-100 → swap virgin for recycled aluminium → PCF drops → note this is a scenario and the approved PCF is unchanged.
7. Scenarios → 70% renewable slider → new trajectory meets target → point at the "actuals unchanged" badge.
8. Compliance → CSRD readiness 68%, with the specific missing datapoints listed from real gaps in the data.

---

## 12. Do not build

Microservices. Docker. Kubernetes. Real OCR. LLM integration. Real SAP/Oracle connectors (a mock connector page showing "last sync, 25,832 records, 14 failed" is acceptable and takes 5 minutes). XBRL generation. Multi-language supplier portal. Email sending. WebSockets. A design system. Unit test suites beyond a handful of calculator assertions.
