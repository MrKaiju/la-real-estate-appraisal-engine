# LA Appraisal Engine: Strategy Blueprint and Roadmap

*Prepared September 2026. Companion to the v0.2.0 codebase on this branch.*

---

## 1. Executive summary

**Thesis.** Generic deal calculators (DealCheck, Mashvisor, PropStream, BiggerPockets) treat Los Angeles like Omaha. They do not know that a 1962 fourplex in LA City is under the RSO, that Prop 13 resets the tax bill at closing, that a $5.5M exit pays a 4% ULA tax on the whole price, or that a pre-1978 building with tuck-under parking probably owes a six-figure soft-story retrofit. Those facts move value by 20 to 40 percent on a typical small-multifamily deal. Nobody sells them to consumers in one place.

**The product.** A consumer-friendly LA underwriting engine that answers two questions in under a minute from an address and a price:

1. *"What is this really worth to me, after LA's rules?"* (investor mode)
2. *"What will it actually cost me per month to live here if the other units pay rent, and will a lender let me count that rent?"* (house-hack mode)

**The niche.** Owner-occupant buyers of 2 to 4 unit properties and first-time small-multifamily investors in LA County. This is the only group that can still close in a $975k-median market at 2026 rates, it is underserved by every incumbent, and it is the on-ramp to a larger investor base.

**Proprietary layer.** The LA Regulatory Stack (RSO / AB 1482 / ULA / Prop 13 / soft-story / SB 9 / fire-zone insurance) encoded as a dated, cited, unit-tested rules engine, fused with an explicit LA expense stack and FHA lender tests. That fusion is the moat. The math around it (cap rates, DSCR, comps) is table stakes and now works.

**State of play.** Before this branch the engine could not complete a single run (five independent crashes) and all seven listing scrapers were dead against current anti-bot systems. As of this commit the engine runs end to end from structured input with zero network calls, has 29 passing tests, a Dockerfile, CI, and three consumer-facing API endpoints. Section 9 lays out four phases from here to a paid product.

---

## 2. Where the codebase actually stood (audit, condensed)

A full-file audit was run against every module. Key findings:

| Area | Finding | Status on this branch |
|---|---|---|
| Orchestrator | `IncomeApproach` was called with a constructor that never existed; `DSCR.summary()` lacked `meets_min_dscr`; narrative and report crashed on any `None`. No run could finish. | **Fixed.** Engine completes; income model rewritten with LA expense stack; DSCR returns lender tests; narrative and report None-safe and HTML-escaped. |
| Recommendation | Scored the *assumed* market cap rate, not the deal's yield. DSCR score hard-wired to 1. Every deal was a PASS. | **Fixed.** Scores going-in cap vs market cap spread, real DSCR at max LTV, cash-on-cash, plus a regulatory adjustment. |
| Scrapers | All seven use bare `requests` + static UA against Zillow (PerimeterX), Redfin, Realtor (Kasada), CoStar. Zero of seven return a page today. Engine did not check for failure. | **Demoted.** Structured `subject` input is the primary path; URL fetch is best-effort and its failure is surfaced as a warning, never a crash. |
| Rent control | LA County cutoff wrong (1995 vs 1979 check), ten LA-County cities with their own ordinances mislabelled "no rent control", AB 1482 absent entirely, no ULA, no Prop 13 reset, no soft-story. | **Replaced** by `core/la_regulatory.py` (see section 5). |
| Duplication | Two recommendation engines, two value-add models, two report generators, two sales-comp models, several stubs. | **Deleted** nine dead files; kept the better sibling in each case. |
| Cap rate grid | 2021-era numbers (5+ unit "prime" at 4.0%). | **Recalibrated** to Q2 2026 (LA MF average 5.8%; prime Westside 4.5%, transitional 6.0%+), dated in the output. |
| Packaging | No requirements file, no tests, no CI, no container, pydantic v1 calls. | **Added** pyproject, requirements, pytest suite, GitHub Actions, Dockerfile, `.env.example`. |

What was genuinely worth keeping: the sales-comp model (filter, similarity score, PPSF/PPU blend), the DSCR amortization math, the rent-comp aggregator, the market-confidence idea, and the clean module boundaries.

---

## 3. Market reality, September 2026

**Prices and rates.** LA median sale price ~$975k (Feb 2026). DSCR investor loans 6.0% to 8.75% depending on credit and DSCR. FHA owner-occupant 2 to 4 unit purchases at 3.5% down are the only low-cash entry, with 2026 FHA limits up to ~$2.4M for a fourplex in LA County.

**Multifamily.** Q2 2026 LA average cap rate 5.8% (up 30 bps YoY), $280,591 per unit, 5.5% vacancy, $2,310 average asking rent (studio $1,700, 1BR $2,087, 2BR $2,669, 3BR $3,230). Prime Westside trades 3.5% to 4.5%; South LA and transitional submarkets 5.75% to 6.5%.

**Regulation moving against small owners.**
- LA City RSO formula cut on Jan 24 2026: from July 1 2026, 90% of CPI, floor 1%, ceiling 4% (was 3% floor / 8% ceiling). Utility adders eliminated.
- AB 1482 cap for LA metro: 8.7% effective Aug 1 2026.
- Measure ULA thresholds indexed to $5.4M (4%) and $10.9M (5.5%) for closings after June 30 2026; the city council declined to amend it in January 2026 and the fight is going statewide.
- Soft-story retrofit: $60k to $200k per building; up to 50% pass-through over ten years.
- Insurance: FAIR Plan 29.1% average dwelling rate increase approved for October 2026; investors bought ~40% of fire-zone lots sold in Palisades and Altadena.

**Consequence.** Small and mid-size landlords are exiting LA "quietly, without ever formally listing" (The Real Deal, May 2026). Every exit is a buyer who needs LA-specific underwriting, and most of those buyers are the exact first-time and house-hack cohort this product targets.

**Competitors and pricing.**

| Product | Price | LA-aware? | Consumer-friendly? |
|---|---|---|---|
| DealCheck | Free / $10 / $20 mo | No | Yes |
| Mashvisor | $40+ mo | No (STR focus) | Yes |
| PropStream | $99 mo | No | No (wholesaler tool) |
| Reventure | $39 mo | ZIP forecasts only | Yes |
| RentCast | $12+ mo, API | Data only | Developer tool |
| Ownwell | 25 to 35% contingency | Tax appeals only | Yes, proves consumers pay for property-level savings |
| Institutional AI underwriting (2026 funding wave) | Enterprise | Partially | No |

Nobody sits in the "LA-aware and consumer-friendly" cell. That is the position.

**Data access.** Zillow's public API is gone; Bridge Interactive needs MLS membership and ~$500/month. Scraping the portals violates their terms and is technically dead. The durable sources are:

- Licensed property APIs: RentCast (records, AVM, rent estimate, comps; free tier then usage-priced), ATTOM (~$500+/mo, custom), BatchData ($1,000/mo for 100k records).
- Free public data: LA County Assessor parcel roll and ArcGIS REST (APN, situs, use code, year built, units, sq ft; owner names withheld by Gov. Code 7928.205), LA City GeoHub zoning layer, ZIMAS, CAL FIRE FHSZ, FEMA flood, HUD FMR/SAFMR API (Bearer token, ZIP-level), Zillow Research ZHVI/ZORI CSVs (free with attribution), Redfin Data Center CSVs.
- The user. A buyer pasting the rent roll from the listing is faster and more accurate than any scraper.

**Regulatory posture.** The federal AVM Quality Control rule (effective Oct 1 2025) binds mortgage originators and secondary-market issuers using AVMs for credit decisions on principal dwellings. It does not bind a consumer decision tool that is not used in a credit decision, but it sets the bar for what "quality control" looks like: dated rules, random-sample testing, no data manipulation, nondiscrimination. The engine should adopt that discipline voluntarily and never call its output an "appraisal" in the USPAP sense.

---

## 4. Positioning, product, and wedge

### 4.1 One-line positioning

*The only deal analyzer that knows Los Angeles.*

### 4.2 Personas, in priority order

1. **The house hacker.** 26 to 40, renting at $2,500 to $4,000, has $50k to $150k, wants to buy a duplex or triplex with FHA and live in one unit. Question: *net monthly cost and will the lender count the rent?* No incumbent computes the FHA self-sufficiency test. Our test run shows why it matters: a $1.45M South LA fourplex at 6.5% fails the test at 0.62x and is BLOCKED before the buyer wastes a month.
2. **The first-time small investor.** Buying a 2 to 8 unit building with a DSCR loan. Question: *is this cash-flow positive after Prop 13 and RSO, and how much can I actually borrow?* Our test run: asking $1.45M, DSCR-supported price $769k. That single number is worth the subscription.
3. **The RSO seller's agent and the buyer's agent.** Need a one-page, defensible PDF that explains RSO, ULA exposure, and soft-story to a nervous client. Lead-gen and white-label channel.
4. **Small lenders and mortgage brokers.** Pre-screen 2 to 4 unit borrowers; API customers later.

### 4.3 Core product surfaces

- **Deal Check page.** Address + price + rents in, one screen out: verdict, net monthly cost (house-hack) or cash-on-cash and DSCR-supported price (investor), the LA regulatory flags with plain-English explanations, and a shareable PDF.
- **Regulatory Screen** as a stand-alone free tool (SEO magnet: "is my building under RSO", "ULA calculator", "SB 9 eligibility"). Already exposed at `POST /regulatory`.
- **House-Hack Calculator** as a stand-alone free tool. Already exposed at `POST /house-hack`.
- **Watchlist and alerts** (paid): re-run a saved deal when rates, rents, or ordinances change.
- **API** (B2B): the same engine for brokerages and lenders.

### 4.4 Proprietary elements (what a competitor cannot copy in a weekend)

1. **LA Regulatory Stack** with citations, effective dates, and tests. Ordinances change; a maintained, versioned rules engine is a moat that compounds.
2. **Submarket cap-rate and rent surfaces** derived from closed transactions and public assessor transfers, refreshed quarterly (Phase 2). Today the grid is calibrated by hand; the pipeline to derive it from data is the asset.
3. **Outcome loop.** Every deal a user runs, plus whether it closed and at what price, becomes calibration data nobody else has for LA small-multifamily.
4. **Honesty as brand.** The engine's numbers are deliberately conservative (Prop 13 at purchase price, reserves, real insurance). Competitors flatter deals to keep users engaged. Ours tells a first-time buyer the truth, which is what earns referrals from agents and lenders.

---

## 5. Target architecture

```
                         ┌─────────────────────────────────────────┐
                         │             Web app (Next.js)            │
                         │  Deal Check · House-Hack · Reg Screen    │
                         │  Auth · Billing (Stripe) · Saved deals   │
                         └───────────────┬─────────────────────────┘
                                         │ HTTPS / JSON
                         ┌───────────────▼─────────────────────────┐
                         │        FastAPI service (api/)            │
                         │  /appraise  /house-hack  /regulatory     │
                         │  /appraise/report.html  (PDF later)      │
                         └───────────────┬─────────────────────────┘
                                         │
        ┌────────────────────────────────┼──────────────────────────────────┐
        │                                │                                  │
┌───────▼────────┐             ┌─────────▼──────────┐             ┌─────────▼─────────┐
│ core/          │             │ engine/ + models/  │             │ data_sources/     │
│ la_regulatory  │             │ income (LA opex)   │             │ RentCast adapter  │
│ house_hack     │             │ cap rate grid      │             │ LA County parcels │
│ (pure rules,   │             │ DSCR sizing        │             │ GeoHub zoning     │
│  cited, dated) │             │ sales comps        │             │ CAL FIRE / FEMA   │
│                │             │ recommendation     │             │ HUD FMR / SAFMR   │
└────────────────┘             │ narrative / report │             │ Zillow/Redfin CSV │
                               └────────────────────┘             └───────────────────┘
                                         │
                         ┌───────────────▼─────────────────────────┐
                         │  Postgres (deals, users, rules versions) │
                         │  Redis (cache of enrichment lookups)     │
                         │  Object store (PDF reports)              │
                         └─────────────────────────────────────────┘
```

Principles:

- **Structured input first.** The engine must give a complete, honest answer from what the buyer can type in 60 seconds. Enrichment (parcel, zoning, AVM, rent estimate) fills gaps and improves confidence; it never blocks.
- **Pure rules, impure adapters.** `core/` has no I/O and is fully unit-tested. `data_sources/` wraps external APIs with caching, timeouts, and graceful degradation.
- **Every number has a basis.** Rules carry `basis` and `as_of`; the cap-rate grid carries `calibration_as_of`; reports carry the engine version. This is what lets the product survive an ordinance change and a skeptical lender.
- **No scraping of portals.** Listing scrapers stay in the repo as optional, best-effort adapters for personal use, behind a warning, and are not part of the commercial product.

---

## 6. Data strategy and cost

| Need | Source | Cost | Phase |
|---|---|---|---|
| Parcel facts (year built, units, sq ft, use code, TRA) | LA County Assessor ArcGIS REST + annual roll (GeoHub) | Free | 1 |
| Zoning, overlays (HPOZ, TOC, hillside, VHFHSZ) | LA City GeoHub layers; county planning layers; CAL FIRE FHSZ | Free | 1 |
| Jurisdiction (city vs unincorporated) | LA County city-boundary polygon, point-in-polygon | Free | 1 |
| Rent estimate and rent comps | RentCast API (fallback: HUD SAFMR by ZIP, Zillow ZORI by ZIP) | Free tier, then ~$0.05 to $0.10 per lookup | 1 |
| AVM and sale comps | RentCast AVM + comps (fallback: user-entered comps) | Same | 1 |
| Market indices and forecasts | Zillow Research ZHVI/ZORI, Redfin Data Center CSVs | Free with attribution | 2 |
| Closed multifamily transactions for cap-rate calibration | Assessor transfer records joined to rent data; broker survey overlay | Free + analyst time | 2 |
| Mortgage rates | FRED (30-yr fixed), lender rate sheets for DSCR | Free | 2 |
| Listing intake | User pastes listing URL: we extract only schema.org JSON-LD when present; otherwise user types facts | Free | 2 |
| Owner/skip-trace | Not needed for the consumer product; avoid the privacy exposure | n/a | never |

Estimated variable cost per full analysis at scale: **$0.10 to $0.25**, dominated by RentCast calls, with caching by APN cutting repeat lookups to zero.

---

## 7. Business model

**Pricing (proposed).**

| Tier | Price | What |
|---|---|---|
| Free | $0 | 3 Deal Checks per month, Regulatory Screen and House-Hack Calculator unlimited, watermark on PDF |
| Buyer | $19/mo or $149/yr | Unlimited checks, clean PDF, saved deals, rate/rent alerts |
| Pro (agents, small investors) | $49/mo | Client-branded PDFs, bulk address import, comps workspace, priority data refresh |
| API | From $299/mo | Per-call engine access for brokerages, lenders, and proptech partners |

**Unit economics sketch.** At $0.25 variable cost per analysis and 20 analyses per paying user per month, gross margin exceeds 70% at the Buyer tier and 90% at Pro. A 2% free-to-paid conversion (the real-estate web benchmark) on 10,000 monthly free users yields ~200 paying users, ~$5k MRR, which covers data and hosting; the B2B API and agent tier are where revenue scales.

**Why people pay.** One avoided bad purchase or one correctly sized offer is worth 1,000x the subscription. The House-Hack BLOCKED verdict and the DSCR-supported price are the two "aha" moments; the product should surface them within the free tier and gate the depth (PDF, alerts, comps workspace).

---

## 8. Go-to-market

1. **SEO tools as the funnel.** Free RSO checker, ULA calculator, SB 9 eligibility, "FHA self-sufficiency test calculator LA". These are high-intent, low-competition queries with fresh 2026 rule changes people are actively searching.
2. **Agent channel.** Buyer's agents on 2 to 4 unit deals need the PDF to close nervous first-time investors. Offer white-label Pro with their branding; each PDF is a referral.
3. **Lender channel.** FHA and DSCR brokers pre-screen borrowers; the self-sufficiency test alone saves them dead files.
4. **Content.** Quarterly "LA small-multifamily cap-rate map" from our own calibration data; ordinance-change explainers on the day they pass. The rules engine's changelog *is* the content calendar.
5. **Community.** BiggerPockets LA forums, AAGLA and local investor meetups, Reddit r/LosAngelesRealEstate.

---

## 9. Roadmap by phase

### Phase 0: Foundation (done on this branch)

- Engine runs end to end from structured input with no network.
- LA Regulatory Stack v1 with tests (RSO, County RSO, ten local ordinances, AB 1482, ULA, Prop 13, soft-story, SB 9 and ADU, fire-zone insurance).
- House-hack module with FHA 75% rent credit, self-sufficiency test, 2026 limits.
- Explicit LA expense stack, DSCR lender tests, going-in-cap scoring, regulatory-adjusted recommendation.
- API: `/appraise`, `/appraise/report.html`, `/house-hack`, `/regulatory`, `/health`.
- Packaging: pyproject, requirements, 29 tests, CI workflow, Dockerfile, `.env.example`.

### Phase 1: Real data, real deploy (3 to 4 weeks)

Deliverables:
- `data_sources/rentcast.py` adapter: property record, rent estimate, AVM, comps; disk/Redis cache keyed by APN.
- `data_sources/la_county_parcels.py` (ArcGIS REST by APN or address) and `data_sources/la_geohub_zoning.py` (point-in-polygon for zone, HPOZ, TOC, hillside, VHFHSZ) and a jurisdiction resolver from city-boundary polygons.
- `data_sources/hud_fmr.py` fixed to the real HUD USER API (Bearer token, SAFMR by ZIP).
- Enrichment step in the engine: user input > enrichment > defaults, with per-field provenance in the output.
- Persistence: Postgres for users, saved deals, rule versions; Alembic migrations.
- Deploy: container to Fly.io or Render (single region, ~$25/mo), managed Postgres, Sentry, uptime check. GitHub Actions builds and deploys `main` on green tests.
- PDF via WeasyPrint in the container image.

Exit criteria: a real LA address plus price produces a complete report with enrichment provenance in under 5 seconds, p95, from the public URL.

### Phase 2: Consumer product (4 to 6 weeks)

- Next.js front end: Deal Check, House-Hack, Regulatory Screen pages; magic-link auth; Stripe; saved deals; shareable report links.
- Listing intake via schema.org JSON-LD extraction from a pasted URL (no scraping beyond the page the user gives us) with a "confirm these facts" step.
- Cap-rate and rent surface v1: derive submarket cap-rate midpoints from assessor transfers + RentCast rents, refreshed quarterly; replace hand-typed grid; publish the map as content.
- Alerts: re-run saved deals on rate moves (FRED) and on rules-engine version bumps.
- Analytics on verdict distribution and conversion.

Exit criteria: first 100 paying users; PDF share-to-signup loop measured.

### Phase 3: Moat and B2B (6 to 8 weeks)

- Outcome loop: users mark deals closed/passed with price; calibration dashboard; quarterly accuracy report (AVM-rule discipline applied voluntarily).
- API tier with keys, quotas, usage billing; white-label PDF for agents and lenders.
- Regulatory Stack v2: relocation-assistance cost model, LA Just Cause Ordinance, Ellis Act timeline, SCEP and RSO fee schedule, Mello-Roos detection by TRA, methane and liquefaction zones, Culver City and Santa Monica transfer-tax tiers.
- Portfolio view for small investors (3 to 20 doors).

Exit criteria: two B2B API customers; rules engine changelog published on a cadence.

### Phase 4: Expand the surface, not the geography (ongoing)

- Value-add and SB 9 pro forma (construction cost per sq ft, ADU rent, lot-split resale) using the existing `value_add_model`.
- Section 8 / voucher scenario using SAFMR (the existing `income_scenarios` idea).
- Insurance quote integration and retrofit contractor referrals (affiliate revenue).
- Only after LA is dominant: Orange County, then San Diego, each as a new rules pack under `core/`, not a rewrite.

---

## 10. Deployment plan, top down

**What runs today.**

```bash
pip install -r requirements-dev.txt
pytest -q                         # 29 tests
uvicorn api.main:app --reload     # http://127.0.0.1:8000/docs
docker build -t la-appraisal . && docker run -p 8000:8000 la-appraisal
```

**Production target (Phase 1).**

| Layer | Choice | Why |
|---|---|---|
| Runtime | Docker image from this repo's Dockerfile | Reproducible, WeasyPrint-capable |
| Host | Fly.io (or Render) in `lax` region | Cheap, close to users, zero-ops Postgres and Redis |
| DB | Managed Postgres, Redis for enrichment cache | Saved deals, rules versions, caching |
| CI/CD | GitHub Actions: test → build → deploy on `main` | Already scaffolded in `.github/workflows/ci.yml` |
| Secrets | Fly secrets from `.env.example` keys | Never in the repo |
| Observability | Sentry + Fly metrics + `/health` uptime check | Enough for Phase 1 |
| Domain/TLS | Fly certificates | Automatic |

**What the deployment needs from the founder (cannot be done from this session).**

1. Choose and create the hosting account (Fly.io or Render) and hand over a deploy token as a GitHub secret.
2. RentCast API key (free tier to start) and HUD USER token.
3. A domain.
4. Stripe account (Phase 2).

Everything else in Phase 1 is code, and the code path is unblocked.

---

## 11. Risks and compliance

- **Not an appraisal.** Never use the word "appraisal" in the consumer UI or PDF title without "automated" and a USPAP disclaimer; the report already carries one. Rename the public product (working name: *LA Deal Check*).
- **Not legal advice.** Every regulatory finding carries a basis citation and a verify-with-ZIMAS/LAHD instruction. Keep it that way; it is also what makes the output credible.
- **Fair housing.** No demographic inputs anywhere in the models; submarket classes are yield-based, not neighborhood-name-based. Document this for the AVM-rule discipline.
- **Data licensing.** Zillow Research and Redfin Data Center require attribution; RentCast prohibits redistribution of raw records (cache, do not resell). No portal scraping in the commercial product.
- **Rules drift.** RSO formula, AB 1482 CPI, ULA thresholds, and FHA limits change on fixed calendars (July 1, August 1, July 1, January 1). Put those four dates on a recurring calendar and bump `RULES_AS_OF` with each verified update.
- **Calibration risk.** The cap-rate grid is hand-calibrated until Phase 2; the output labels it as such. Do not market accuracy claims before the outcome loop exists.
- **Privacy.** Do not build owner-lookup or skip-tracing; it adds CCPA exposure and is not needed for the buyer persona.

---

## 12. Decisions needed

1. **Confirm the wedge**: house hackers and first-time small-multifamily buyers in LA County, consumer-first, B2B second.
2. **Name and domain** for the consumer product.
3. **Host**: Fly.io (recommended) or Render.
4. **Data budget**: start on RentCast free tier, authorize up to ~$150/month at 1,000 analyses/month.
5. **Front-end stack**: Next.js recommended; confirm or substitute.

With those five answers Phase 1 can start immediately.
