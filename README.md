# LA Real Estate Appraisal Engine  
A modular, automated real estate appraisal and investment analysis engine designed for Los Angeles County.  
This system integrates listing parsers, rental comparables, zoning/APN tools, and underwriting models to produce institutional-quality property evaluations and investment recommendations.

---

# **Overview**
This repository provides a **full-stack appraisal pipeline** capable of:

- Parsing real estate listings (Zillow, Redfin, Realtor.com, Homes.com, Century21, LoopNet)  
- Normalizing address and parcel data  
- Interpreting zoning and land-use rules  
- Aggregating rental comparables (Apartments.com + manual comps)  
- Running complete income analysis (GSI, OPEX, NOI)  
- Selecting risk-adjusted market cap rates  
- Performing DSCR-based loan sizing  
- Producing valuations (as-is and stabilized)  
- Generating a final **Buy / Watch / Pass** recommendation with full reasoning  

The system is optimized for Los Angeles–specific workflows (RSO, zoning overlays, parcel-level risk factors) but can be expanded nationwide.

---

# **Key Features**

### **1. Multi-Site Listing Parsing**
Automatically detects the listing source and applies the correct parser:

- Zillow  
- Redfin  
- Realtor.com  
- Homes.com  
- Century21  
- LoopNet  

Each parser outputs standardized property data:  
price, address, beds, baths, sqft, lot size, year built, property type, number of units, etc.

---

### **2. Professional-Grade Data Tools**
Included inside the `tools/` folder:

- **AddressNormalizer** — converts raw listing addresses into standardized formats  
- **APNLookup** — connects APNs to assessor data (HTML input optional)  
- **ZoningLookup** — interprets zoning codes and optional ZIMAS HTML  
- **RentalCompAggregator** — merges Apartments.com data + manual rentals for market rent  
- **Manual comp integration** support  

---

### **3. Underwriting Models**
Provided inside `models/`:

- **IncomeApproach**  
  Computes GSI, vacancy, operating expenses, NOI, stabilized NOI  

- **CapRateModel**  
  Produces a base + risk-adjusted + rent-control-adjusted cap rate  

- **DSCRLoanModel**  
  Performs DSCR sizing, LTV limits, binding loan amount, monthly P&I, DSCR, and LTV  

- **RecommendationEngine**  
  Produces structured “Buy / Watch / Pass” with reasoning and diagnostics  

Supports optional future models:

- RiskScoring  
- ValueAddModel  

---

### **4. Full Integration Engine**
Located in:

