# 🏢 Real Estate Appraiser Engine

_A modular, investment-grade automated valuation engine for income-producing real estate._

This repository contains a **Python-based appraisal engine** that ingests listing URLs and supporting data, then produces a structured, multi-approach valuation for residential and small commercial properties.

The engine is designed from an **investment / underwriting perspective** rather than a homeowner perspective. It focuses on:

- Income-producing potential  
- DSCR loan sizing  
- Cap rate alignment  
- Sales comparison to local market  
- Rent control and jurisdiction risk  
- Narrative-grade reporting and export

---

## 🎯 Key Capabilities

### 1. Multi-Source Listing Parsing

The engine integrates with multiple major listing platforms via lightweight parsers:

- **Zillow**
- **Redfin**
- **Realtor.com**
- **Homes.com**
- **Century21.com**
- **LoopNet** (for small commercial / mixed-use)
- **Apartments.com** (for rent comps)

Each parser normalizes basic listing attributes into a common `listing_core` structure (price, beds, baths, square footage, lot size, year built, etc.).

---

### 2. Integrated Appraisal Approaches

The engine orchestrates several traditional valuation approaches.

#### Income Approach (NOI / Investment View)

- Converts rent comps into a **market rent estimate**
- Builds **Gross Potential Income (GPI)** and **Effective Gross Income (EGI)**
- Applies **expense ratio** and expense assumptions
- Produces **NOI (current)** and optional **stabilized NOI**

This is handled by the `IncomeApproach` model, which can be tuned for:

- Unit count and mix  
- Market vacancy rates  
- Operating expense ratios  
- Reserve estimates  

---

#### Sales Comparison Approach

When you provide a list of sales comparables, the `SalesCompModel`:

- Normalizes comp data (price, square footage, distance, etc.)
- Derives **price-per-square-foot (PPSF)** statistics  
- Filters or downweights outliers  
- Produces a **comp-derived value range / central estimate**  
- Exposes comp statistics for downstream logic (e.g., confidence scoring)

---

#### Cap Rate Model

The `CapRateModel` uses:

- Property type (SFR, 2–4 unit, 5+ unit, mixed-use, retail, office, industrial)
- Submarket classification (prime / core / stable / transitional / distressed)
- Optional risk score and rent control flags  

to produce:

- A **base cap rate**  
- Risk and rent-control adjustments  
- A **final reconciled cap rate** used in valuation and pricing checks.

---

#### DSCR Loan Model

The `DSCRLoanModel` sizes debt against:

- Annual NOI  
- Target minimum DSCR (e.g., 1.20x)  
- Maximum LTV (e.g., 75%)  
- Interest rate and amortization term  

It produces:

- Maximum supported **loan amount**  
- Maximum supported **purchase price** (from a lender’s perspective)  
- A true/false flag for **meeting the DSCR threshold**  

---

### 3. Market Confidence Score

Beyond just “what is it worth?”, the engine answers:

> “How much confidence should we have in this valuation, based on available data?”

The **Market Confidence module** considers:

- The number of valid comparables
- Average distance of comps from the subject
- Spread between low/median/high PPSF
- Comp variance relative to a central trend

It outputs:

- A **score** (1.0–5.0)  
- A **level** – `high`, `medium`, or `low`  
- Supporting statistics (comp count, average distance, PPSF spread, etc.)

This score is used to lightly adjust the final BUY/WATCH/PASS rating, without overpowering the core underwriting metrics.

---

### 4. Recommendation Engine (BUY / WATCH / PASS)

The `RecommendationEngine` fuses:

- Cap rate strength  
- DSCR compliance and loan sizing  
- Cash-on-cash return (if provided)  
- Sales comparison performance  
- Market confidence level  
- Risk score and jurisdictional flags  

into a single:

- **Final recommendation**: `"BUY"`, `"WATCH"`, or `"PASS"`  
- **Final score** and **base score**  
- Component scores for transparency

This gives you a fast institutional-style signal while still surfacing the underlying drivers.

---

### 5. Narrative Builder

The `NarrativeBuilder` converts all quantitative outputs into a **human-readable summary** suitable for:

- Investment memos  
- Lender packages  
- Internal underwriting notes  
- Broker opinion-of-value supplements  

It produces:

- A `full_text` narrative (multi-paragraph)  
- Breakdowns by section:

  - Subject property overview  
  - Income and NOI summary  
  - Cap rate reasoning  
  - Valuation (as-is and stabilized)  
  - Sales comparison synthesis  
  - Market confidence explanation  
  - Financing / DSCR perspective  
  - Final recommendation narrative  

This dramatically shortens the time between analysis and communication.

---

### 6. HTML & PDF Report Generation

The `report_generator` module can take the full appraisal result and generate:

- A **styled HTML report**, with sections and tables  
- A **PDF report** (if `WeasyPrint` or a compatible backend is installed)

The report includes:

- Header with property address and listing price  
- Subject property table (beds, baths, square footage, lot size, year built)  
- Income and NOI table  
- Cap rate and valuation table  
- Sales comparison and Market Confidence summary  
- Financing and DSCR table  
- Full narrative section  

This is ideal for:

- Exporting to investors  
- Attaching to emails  
- Persisting in your internal deal database  

---

## 🧱 Architecture & Module Overview

The engine is structured to keep parsers, tools, models, and presentation cleanly separated.

```text
real-estate-appraiser/
│
├── engine/
│   └── appraiser_engine.py         # Orchestration / coordinator
│
├── services/                       # External data ingestion (scraping / parsing)
│   ├── zillow_parser.py
│   ├── redfin_parser.py
│   ├── realtor_parser.py
│   ├── homesdotcom_parser.py
│   ├── century21_parser.py
│   ├── loopnet_parser.py
│   └── apartments_parser.py
│
├── tools/                          # Local utilities and enriched context
│   ├── address_normalizer.py       # Standardizes addresses (street, city, ZIP)
│   ├── apn_lookup.py               # APN + assessor data integration
│   ├── zoning_lookup.py            # Zoning + overlays integration
│   └── rental_comp_aggregator.py   # Aggregates and summarizes rent comps
│
├── models/                         # Core underwriting & valuation logic
│   ├── income_approach.py          # NOI modeling
│   ├── cap_rate_model.py           # Cap rate determination
│   ├── dscr_loan_model.py          # DSCR and loan sizing
│   ├── sales_comp_model.py         # Sales comparison normalization & stats
│   ├── recommendation_engine.py    # BUY/WATCH/PASS decision & scoring
│   └── narrative_builder.py        # Narrative synthesis
│
├── reports/
│   └── report_generator.py         # HTML/PDF report output
│
└── README.md
