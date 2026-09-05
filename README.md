# LA Appraisal Engine

*A Los Angeles-specific underwriting engine for small residential and multifamily property, with a consumer-friendly API.*

Generic deal calculators treat LA like any other metro. This engine knows that a 1962 fourplex in LA City is under the RSO, that Prop 13 resets the tax bill at closing, that a $5.5M exit pays Measure ULA on the whole price, that a pre-1978 building with tuck-under parking probably owes a soft-story retrofit, and that an R1 lot is SB 9 eligible. It fuses those rules with an explicit LA expense stack, DSCR loan sizing, sales comps, and FHA house-hack lender tests.

Strategy, market analysis, and the phased roadmap live in [`docs/STRATEGY_BLUEPRINT.md`](docs/STRATEGY_BLUEPRINT.md).

## Quick start

```bash
pip install -r requirements-dev.txt
pytest -q
uvicorn api.main:app --reload      # docs at http://127.0.0.1:8000/docs
```

Run the bundled fourplex example:

```bash
python -c "
import json; from engine.appraiser_engine import AppraiserEngine
cfg = json.load(open('examples/example_fourplex_structured.json'))
out = AppraiserEngine().run_full_appraisal(cfg)
print(out['narrative']['full_text'])"
```

Docker and deploy:

```bash
docker build -t la-appraisal-engine .
docker run -p 8000:8000 la-appraisal-engine
# Fly.io (first time): fly launch --no-deploy --copy-config && fly volumes create data --region lax --size 1
fly secrets set RENTCAST_API_KEY=... HUD_USER_API_TOKEN=... API_KEY=... && fly deploy
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /appraise` | Full underwriting from a structured `subject` (address, price, units, rents, year built, zone). Returns income value, DSCR sizing, regulatory findings, optional sales comps, optional house-hack view, narrative, and BUY / WATCH / PASS. |
| `POST /appraise/report.html` | Same, rendered as a printable HTML report. |
| `POST /deals`, `GET /deals`, `GET /deals/{id}` | Run and persist a deal (SQLite by default, Postgres via `DATABASE_URL`). Gated by `X-Api-Key` when `API_KEY` is set. |
| `POST /house-hack` | Owner-occupant 1 to 4 unit math: FHA 3.5% down, 75% rent credit, self-sufficiency test, net monthly housing cost. |
| `POST /regulatory` | The LA Regulatory Stack on its own: RSO / AB 1482 regime, ULA transfer tax, Prop 13 tax, soft-story exposure, SB 9 and ADU upside, fire-zone insurance. |
| `GET /health` | Liveness plus the rules-engine `as_of` date. |

Minimal request:

```json
{
  "subject": {
    "address_full": "1234 W 41st Pl, Los Angeles, CA 90037",
    "city": "Los Angeles", "price": 1450000, "year_built": 1962,
    "property_type": "2-4", "num_units": 4, "zone": "RD1.5-1",
    "unit_rents": [2400, 2400, 2400, 2400], "current_rents": [1650, 1700, 2300, 2400]
  },
  "house_hack": { "loan_program": "fha", "interest_rate": 0.065 }
}
```

**Enrichment.** Given only an address and price, the engine fills the rest from the LA County Assessor parcel layer (year built, units, sq ft, lot, APN), LA County city boundaries (jurisdiction), LA City GeoHub (zone), CAL FIRE (fire hazard zone), and, when keys are set, RentCast (rent estimate, value AVM, comps) and HUD (Small Area FMR). User-entered values always win; every field's source is returned in `enrichment.provenance` and conflicts are surfaced as warnings. Set `"enrich": false` or `LA_ENGINE_ENRICH=0` to run fully offline. Run `python scripts/smoke_live.py` from a networked machine to verify the public layers before deploying.

Listing URLs (`primary_url`) are accepted as a best-effort convenience only. The major portals block automated fetches; when a fetch fails the engine says so in `warnings` and continues from the structured subject.

## Layout

```
core/            Pure, cited, dated LA rules (la_regulatory.py, house_hack.py) and the enrichment layer
engine/          Orchestration (appraiser_engine.py)
models/          Income approach (LA expense stack), cap rate grid (Q2 2026), DSCR, sales comps,
                 recommendation, narrative, value-add, income scenarios, risk scoring
reports/         HTML / PDF report generator
api/             FastAPI app and pydantic schemas
tools/           Address normaliser, APN lookup, zoning interpreter, rent-comp aggregator
services/        Optional listing parsers (best-effort), property tax estimator
data_sources/    HTTP client with cache; LA County parcels, GeoHub zoning / jurisdiction / CAL FIRE,
                 RentCast, HUD FMR, geocoder adapters (all offline-testable)
tests/           pytest suite (rules, house-hack, engine end-to-end, API, adapters, enrichment, store)
scripts/         smoke_live.py: verifies external layers from a networked machine
fly.toml         Fly.io app definition; .github/workflows/deploy.yml deploys main on green
docs/            Strategy blueprint and roadmap
```

## Disclaimer

Automated underwriting output. Not an appraisal under USPAP and not legal, tax, or investment advice. Every regulatory finding carries its statutory basis and must be verified with ZIMAS, LAHD, and the LA County Assessor for a specific parcel.
