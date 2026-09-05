"""
core/la_regulatory.py

The LA Regulatory Stack — the proprietary layer of the engine.

Generic underwriting tools (DealCheck, Mashvisor, PropStream) treat Los Angeles
like any other metro. They do not know that:

  * a 1962 fourplex in LA City is under the RSO and can only raise rents ~1-4%/yr
    (90% of CPI, floor 1%, ceiling 4%, from July 1 2026),
  * the same fourplex in Glendale or Pasadena is under AB 1482 (5% + CPI, LA cap
    8.7% from Aug 1 2026),
  * a $5.5M sale inside LA City pays a 4% "ULA" transfer tax on the WHOLE price,
  * Prop 13 reassesses to purchase price, so the seller's tax bill is irrelevant,
  * a pre-1978 wood-frame building with tuck-under parking probably owes a
    $60k-$200k soft-story retrofit,
  * an R1 lot is SB 9 / ADU eligible and may carry 2-4x unit upside.

This module encodes those rules as pure, deterministic, unit-testable functions.
Every output includes a `basis` string and an `as_of` date so a consumer can see
WHY a flag fired, and so the rules can be re-verified as ordinances change.

None of this is legal advice. Every rule cites the public source it was derived
from and must be verified against ZIMAS / LAHD / the County Assessor for a
specific parcel before money changes hands.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional, Dict, Any, List

RULES_AS_OF = date(2026, 9, 1)

# --------------------------------------------------------------------------
# Constants (all figures verified September 2026, see docs/STRATEGY_BLUEPRINT.md)
# --------------------------------------------------------------------------

# LA City RSO: buildings with 2+ units, certificate of occupancy before Oct 1, 1978.
RSO_CUTOFF_YEAR = 1978
# July 1 2025 - June 30 2026 fixed 3%; from July 1 2026: 90% of CPI, floor 1%, cap 4%.
RSO_ALLOWABLE_INCREASE_CURRENT = 0.03
RSO_FORMULA_FLOOR = 0.01
RSO_FORMULA_CAP = 0.04
RSO_FORMULA_CPI_SHARE = 0.90

# AB 1482 (statewide Tenant Protection Act): 5% + regional CPI, max 10%.
# LA metro figure effective Aug 1 2026 - Jul 31 2027.
AB1482_CAP_LA_CURRENT = 0.087
AB1482_HARD_CAP = 0.10
AB1482_NEW_CONSTRUCTION_EXEMPT_YEARS = 15

# Transfer taxes on SALE (paid by seller in LA custom). Base rates:
LA_CITY_BASE_TRANSFER_TAX = 0.0045
LA_COUNTY_TRANSFER_TAX = 0.0011
# Measure ULA thresholds effective for closings after June 30, 2026.
ULA_TIER1_THRESHOLD = 5_400_000
ULA_TIER1_RATE = 0.04
ULA_TIER2_THRESHOLD = 10_900_000
ULA_TIER2_RATE = 0.055

# Prop 13
PROP13_BASE_RATE = 0.01
PROP13_LA_TYPICAL_ADDONS = 0.0025   # voter-approved bonds / direct assessments, varies by TRA
PROP13_ANNUAL_ESCALATOR_CAP = 0.02

# Soft-story (LA Ordinance 183893): wood-frame, 2+ stories, 4+ units, permitted before 1978,
# with tuck-under parking or otherwise soft ground story. Cost band per 2026 contractor surveys.
SOFT_STORY_MIN_UNITS = 4
SOFT_STORY_COST_PER_UNIT_LOW = 10_000
SOFT_STORY_COST_PER_UNIT_HIGH = 30_000
SOFT_STORY_COST_BUILDING_FLOOR = 60_000

# SB 9 eligible single-family zones in LA City.
SB9_ELIGIBLE_ZONE_PREFIXES = ("R1", "RS", "RE", "RA", "RU", "RZ", "RW", "A1", "A2")
SB9_MIN_RESULTING_LOT_SQFT = 1_200
SB9_MIN_LOT_FOR_SPLIT_SQFT = 2 * SB9_MIN_RESULTING_LOT_SQFT / 0.6  # smaller lot must be >=40%

# Cities inside LA County with their own rent stabilization ordinances (non-exhaustive,
# used only to avoid mis-labelling them "no local rent control").
CITIES_WITH_LOCAL_RENT_CONTROL = {
    "los angeles": "LA City RSO",
    "santa monica": "Santa Monica Rent Control Charter Amendment",
    "west hollywood": "West Hollywood RSO",
    "beverly hills": "Beverly Hills RSO",
    "pasadena": "Pasadena Measure H (2022)",
    "inglewood": "Inglewood RSO",
    "culver city": "Culver City RSO",
    "baldwin park": "Baldwin Park RSO",
    "bell gardens": "Bell Gardens RSO",
    "pomona": "Pomona Rent Stabilization",
    "maywood": "Maywood RSO",
    "unincorporated": "LA County RSO",
}


# --------------------------------------------------------------------------
# Subject description
# --------------------------------------------------------------------------

@dataclass
class LASubject:
    """Minimal parcel facts needed by the regulatory stack."""
    city: Optional[str] = None            # "Los Angeles", "Glendale", "unincorporated", ...
    year_built: Optional[int] = None
    num_units: Optional[int] = None
    property_type: Optional[str] = None   # sfr | condo | 2-4 | 5+ | mixed_use | ...
    zone: Optional[str] = None            # e.g. "R1-1", "RD1.5-1", "R3-1"
    lot_sqft: Optional[float] = None
    stories: Optional[int] = None
    wood_frame: Optional[bool] = None
    tuck_under_parking: Optional[bool] = None
    owner_is_corporate: bool = False      # affects AB 1482 SFR exemption
    in_very_high_fire_hazard_zone: Optional[bool] = None

    @property
    def city_key(self) -> str:
        return (self.city or "").strip().lower()

    @property
    def is_la_city(self) -> bool:
        return self.city_key in ("los angeles", "la", "la city", "city of los angeles")

    @property
    def is_unincorporated(self) -> bool:
        return "unincorporated" in self.city_key

    @property
    def units(self) -> int:
        if self.num_units:
            return int(self.num_units)
        pt = (self.property_type or "").lower()
        if pt in ("sfr", "single_family", "condo", "townhouse"):
            return 1
        if pt == "2-4":
            return 2
        if pt == "5+":
            return 5
        return 1

    @property
    def is_single_unit(self) -> bool:
        pt = (self.property_type or "").lower()
        return self.units <= 1 or pt in ("sfr", "single_family", "condo", "townhouse")


@dataclass
class Finding:
    key: str
    applies: Optional[bool]
    headline: str
    detail: str
    basis: str
    severity: str = "info"     # info | caution | risk | opportunity
    numbers: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def rent_regulation(subject: LASubject, as_of: date = RULES_AS_OF) -> Finding:
    """
    Which rent cap governs the subject, and what is the allowable annual increase?
    Priority: local RSO (stricter) > AB 1482 > exempt.
    """
    yb = subject.year_built
    building_age = (as_of.year - yb) if yb else None

    # ---- LA City RSO ----
    if subject.is_la_city:
        if subject.is_single_unit:
            # SFR / condo exempt from RSO. Falls to AB 1482 unless owner is an individual
            # and proper notice is given.
            return _ab1482(subject, building_age, note="Single unit: exempt from LA City RSO.")
        if yb is None:
            return Finding(
                key="rent_regulation", applies=None, severity="caution",
                headline="Rent control status unknown (year built missing)",
                detail="LA City multi-unit; RSO applies if certificate of occupancy pre-dates Oct 1 1978.",
                basis="LAMC 151.02",
            )
        if yb < RSO_CUTOFF_YEAR or (yb == RSO_CUTOFF_YEAR):
            return Finding(
                key="rent_regulation", applies=True, severity="risk",
                headline="LA City RSO applies",
                detail=(
                    f"Built {yb}, {subject.units} units inside LA City. Annual increase fixed at "
                    f"{RSO_ALLOWABLE_INCREASE_CURRENT:.0%} through Jun 30 2026, then 90% of CPI with a "
                    f"{RSO_FORMULA_FLOOR:.0%} floor and {RSO_FORMULA_CAP:.0%} ceiling. Vacancy decontrol "
                    "still allows reset to market on turnover. Relocation assistance and just-cause "
                    "eviction rules apply. Budget RSO registration and SCEP fees per unit."
                ),
                basis="LAMC 151.00 et seq.; Ordinance eff. Jan 24 2026 (formula eff. Jul 1 2026)",
                numbers={
                    "regime": "LA_CITY_RSO",
                    "allowable_increase_current": RSO_ALLOWABLE_INCREASE_CURRENT,
                    "formula_cpi_share": RSO_FORMULA_CPI_SHARE,
                    "formula_floor": RSO_FORMULA_FLOOR,
                    "formula_cap": RSO_FORMULA_CAP,
                    "underwriting_rent_growth": 0.025,
                },
            )
        return _ab1482(subject, building_age, note="Post-1978 LA City building: RSO exempt.")

    # ---- Unincorporated LA County RSO ----
    if subject.is_unincorporated and not subject.is_single_unit and yb and yb <= 1995:
        return Finding(
            key="rent_regulation", applies=True, severity="risk",
            headline="LA County RSO applies (unincorporated area)",
            detail="Pre-1995 multi-unit in unincorporated LA County. County caps increases at "
                   "60% of CPI (3% max) for fully covered units; luxury-unit tiers differ.",
            basis="LA County Code Ch. 8.52 (as amended 2024)",
            numbers={"regime": "LA_COUNTY_RSO", "underwriting_rent_growth": 0.02},
        )

    # ---- Other incorporated cities with their own ordinance ----
    local = CITIES_WITH_LOCAL_RENT_CONTROL.get(subject.city_key)
    if local and not subject.is_single_unit:
        return Finding(
            key="rent_regulation", applies=True, severity="risk",
            headline=f"Local rent control: {local}",
            detail="City has its own ordinance which is stricter than AB 1482. Verify the "
                   "specific cap and covered-building definition with the city housing department.",
            basis=local,
            numbers={"regime": "LOCAL_RSO", "underwriting_rent_growth": 0.025},
        )

    return _ab1482(subject, building_age)


def _ab1482(subject: LASubject, building_age: Optional[int], note: str = "") -> Finding:
    if building_age is not None and building_age < AB1482_NEW_CONSTRUCTION_EXEMPT_YEARS:
        return Finding(
            key="rent_regulation", applies=False, severity="opportunity",
            headline="No rent cap (new construction exemption)",
            detail=f"{note} Building is under {AB1482_NEW_CONSTRUCTION_EXEMPT_YEARS} years old, exempt "
                   "from AB 1482 on a rolling basis.",
            basis="Civ. Code 1947.12(d)(4)",
            numbers={"regime": "EXEMPT_NEW_CONSTRUCTION", "underwriting_rent_growth": 0.03},
        )
    if subject.is_single_unit and not subject.owner_is_corporate:
        return Finding(
            key="rent_regulation", applies=False, severity="opportunity",
            headline="AB 1482 exempt (single unit, individual owner, with notice)",
            detail=f"{note} SFR/condo owned by a natural person is exempt from the AB 1482 cap if the "
                   "lease contains the statutory exemption notice. Just-cause rules may still apply "
                   "locally.",
            basis="Civ. Code 1947.12(d)(5)",
            numbers={"regime": "EXEMPT_SFR", "underwriting_rent_growth": 0.03},
        )
    return Finding(
        key="rent_regulation", applies=True, severity="caution",
        headline=f"AB 1482 statewide cap applies ({AB1482_CAP_LA_CURRENT:.1%} in LA metro)",
        detail=f"{note} Annual increase limited to 5% + regional CPI, hard cap 10%. Just-cause "
               "eviction after 12 months. No vacancy control.",
        basis="Civ. Code 1947.12; LA-area CPI figure eff. Aug 1 2026",
        numbers={
            "regime": "AB1482",
            "allowable_increase_current": AB1482_CAP_LA_CURRENT,
            "hard_cap": AB1482_HARD_CAP,
            "underwriting_rent_growth": 0.03,
        },
    )


def transfer_tax_on_exit(subject: LASubject, sale_price: float) -> Finding:
    """Seller-side documentary transfer tax including Measure ULA inside LA City."""
    county = sale_price * LA_COUNTY_TRANSFER_TAX
    city = 0.0
    ula = 0.0
    ula_rate = 0.0
    if subject.is_la_city:
        city = sale_price * LA_CITY_BASE_TRANSFER_TAX
        if sale_price >= ULA_TIER2_THRESHOLD:
            ula_rate = ULA_TIER2_RATE
        elif sale_price > ULA_TIER1_THRESHOLD:
            ula_rate = ULA_TIER1_RATE
        ula = sale_price * ula_rate
    else:
        # Culver City, Santa Monica, etc. have their own tiered transfer taxes; flag only.
        pass
    total = county + city + ula
    sev = "risk" if ula > 0 else "info"
    headline = ("Measure ULA transfer tax applies on exit" if ula > 0
                else "Standard transfer tax on exit")
    detail = (
        f"At a ${sale_price:,.0f} sale: county {LA_COUNTY_TRANSFER_TAX:.2%}"
        + (f", LA City {LA_CITY_BASE_TRANSFER_TAX:.2%}" if subject.is_la_city else "")
        + (f", ULA {ula_rate:.1%} on the FULL price" if ula else "")
        + f". Total ${total:,.0f} ({total / sale_price:.2%}). "
    )
    if subject.is_la_city and ula == 0 and sale_price > ULA_TIER1_THRESHOLD * 0.85:
        detail += (f"Sale is within 15% of the ${ULA_TIER1_THRESHOLD:,.0f} ULA threshold; appreciation "
                   "could push the exit into the 4% tier.")
        sev = "caution"
    return Finding(
        key="transfer_tax", applies=ula > 0, severity=sev, headline=headline, detail=detail,
        basis="LAMC 21.9.2 (Measure ULA, thresholds eff. Jul 1 2026); R&T Code 11911",
        numbers={"county": round(county), "city": round(city), "ula": round(ula),
                 "ula_rate": ula_rate, "total": round(total), "effective_rate": round(total / sale_price, 5)},
    )


def property_tax_after_purchase(purchase_price: float, tra_addon_rate: float = PROP13_LA_TYPICAL_ADDONS) -> Finding:
    """Prop 13 reassessment: the buyer's bill is set by purchase price, not the seller's bill."""
    rate = PROP13_BASE_RATE + tra_addon_rate
    annual = purchase_price * rate
    return Finding(
        key="property_tax", applies=True, severity="info",
        headline=f"Prop 13 reassessment: ~${annual:,.0f}/yr ({rate:.3%})",
        detail="Assessed value resets to purchase price at close of escrow. Ignore the seller's "
               "current tax bill. Assessed value then grows at most 2%/yr, which is a hidden "
               "inflation hedge for long holds. Add-on rate varies by Tax Rate Area; 1.10%-1.25% "
               "is typical in LA County. Mello-Roos districts can push higher.",
        basis="Cal. Const. Art. XIII A",
        numbers={"annual_tax": round(annual), "effective_rate": rate,
                 "escalator_cap": PROP13_ANNUAL_ESCALATOR_CAP},
    )


def soft_story_exposure(subject: LASubject) -> Finding:
    """LA City mandatory soft-story retrofit ordinance risk."""
    if not subject.is_la_city:
        return Finding(key="soft_story", applies=False, severity="info",
                       headline="Soft-story ordinance: LA City only",
                       detail="Other cities (Santa Monica, West Hollywood, Pasadena, Beverly Hills, Culver City) "
                              "have their own programs; verify locally.",
                       basis="LA Ordinance 183893")
    yb = subject.year_built
    if subject.units < SOFT_STORY_MIN_UNITS or (yb and yb >= RSO_CUTOFF_YEAR):
        return Finding(key="soft_story", applies=False, severity="info",
                       headline="Not in soft-story program scope",
                       detail="Program targets wood-frame buildings permitted before 1978 with 4+ units "
                              "and 2+ stories.",
                       basis="LA Ordinance 183893")
    signals = [subject.wood_frame, subject.tuck_under_parking, (subject.stories or 0) >= 2]
    known = [s for s in signals if s is not None]
    likely = all(known) if known else None
    low = max(SOFT_STORY_COST_BUILDING_FLOOR, subject.units * SOFT_STORY_COST_PER_UNIT_LOW)
    high = max(low, subject.units * SOFT_STORY_COST_PER_UNIT_HIGH)
    if likely is False:
        return Finding(key="soft_story", applies=False, severity="info",
                       headline="Soft-story retrofit unlikely to be required",
                       detail="Building characteristics do not match the soft-story profile.",
                       basis="LA Ordinance 183893")
    return Finding(
        key="soft_story", applies=likely, severity="risk" if likely else "caution",
        headline="Possible mandatory soft-story retrofit",
        detail=(f"Pre-1978, {subject.units}-unit LA City building. If wood-frame with tuck-under parking, "
                f"a retrofit is mandatory. Budget ${low:,.0f}-${high:,.0f} unless a Certificate of "
                "Compliance is on file with LADBS. Up to 50% of cost may be passed through to tenants "
                "over 10 years (max $38/unit/month)."),
        basis="LA Ordinance 183893; LAMC 151.07 cost recovery",
        numbers={"cost_low": low, "cost_high": high},
    )


def density_upside(subject: LASubject) -> Finding:
    """SB 9 / ADU / JADU unit-count upside for single-family zoned lots."""
    zone = (subject.zone or "").upper().replace(" ", "")
    lot = subject.lot_sqft or 0
    if not zone:
        return Finding(key="density_upside", applies=None, severity="info",
                       headline="Density upside unknown (zone missing)",
                       detail="Provide the ZIMAS zone string to evaluate SB 9 and ADU potential.",
                       basis="Gov. Code 65852.21, 66411.7; 65852.2")
    sb9_zone = zone.startswith(SB9_ELIGIBLE_ZONE_PREFIXES) and not zone.startswith("RD")
    if not sb9_zone:
        # Multifamily zone: ADU conversion of non-livable space + up to 2 detached ADUs.
        return Finding(
            key="density_upside", applies=True, severity="opportunity",
            headline="Multifamily lot: ADU conversion + 2 detached ADUs allowed by-right",
            detail="State law allows converting up to 25% of existing units' worth of non-livable space "
                   "(storage, garages) into ADUs plus two detached ADUs, ministerial approval. Density "
                   "bonus and TOC incentives may apply near transit.",
            basis="Gov. Code 65852.2(e)(1)(C)-(D)",
            numbers={"max_new_units_estimate": 2 + max(1, subject.units // 4)},
        )
    can_split = lot >= SB9_MIN_LOT_FOR_SPLIT_SQFT if lot else None
    max_units = 4 if can_split else 4  # 2 primary + ADU + JADU without split; 2+2 with split
    detail = (
        f"Zone {zone} is SB 9 eligible. Without a lot split: 2 primary units + ADU + JADU (up to 4 units). "
    )
    if can_split:
        detail += (f"Lot ({lot:,.0f} sf) supports a ministerial SB 9 lot split (each lot >= "
                   f"{SB9_MIN_RESULTING_LOT_SQFT:,} sf, 40/60 max ratio) creating two sellable parcels "
                   "with 2 units each. Owner-occupancy affidavit (3 yrs) required for the split.")
    elif can_split is False:
        detail += "Lot is too small for an SB 9 split; ADU/JADU path only."
    detail += " Historic (HPOZ) and very-high-fire-hazard overlays can limit eligibility."
    return Finding(
        key="density_upside", applies=True, severity="opportunity",
        headline=f"SB 9 / ADU eligible: up to {max_units} units on a single-family lot",
        detail=detail,
        basis="Gov. Code 65852.21, 66411.7 (SB 9); 65852.2 (ADU); LA City SB 9 Implementation Memo",
        numbers={"max_units": max_units, "lot_split_eligible": can_split},
    )


def insurance_exposure(subject: LASubject) -> Finding:
    if subject.in_very_high_fire_hazard_zone:
        return Finding(
            key="insurance", applies=True, severity="risk",
            headline="Very High Fire Hazard Severity Zone: expect FAIR Plan pricing",
            detail="Admitted carriers are largely non-renewing in VHFHSZ. Underwrite FAIR Plan dwelling "
                   "coverage (29% average rate increase approved for Oct 2026) plus a DIC wrap. Budget "
                   "0.8%-1.5% of replacement cost annually versus 0.3%-0.5% elsewhere.",
            basis="CAL FIRE FHSZ maps (2025 update); CDI FAIR Plan rate order 2026",
            numbers={"insurance_rate_of_value_low": 0.008, "insurance_rate_of_value_high": 0.015},
        )
    return Finding(
        key="insurance", applies=False, severity="info",
        headline="Standard insurance market",
        detail="Not flagged as a very-high fire hazard zone. Still verify with the CAL FIRE map; "
               "LA-wide premiums have risen 20-40% since 2023.",
        basis="CAL FIRE FHSZ maps",
        numbers={"insurance_rate_of_value_low": 0.003, "insurance_rate_of_value_high": 0.005},
    )


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------

def evaluate(subject: LASubject, purchase_price: Optional[float] = None,
             exit_price: Optional[float] = None) -> Dict[str, Any]:
    """Run the full LA regulatory stack and return a JSON-serialisable dict."""
    findings: List[Finding] = [
        rent_regulation(subject),
        soft_story_exposure(subject),
        density_upside(subject),
        insurance_exposure(subject),
    ]
    if purchase_price:
        findings.append(property_tax_after_purchase(purchase_price))
        findings.append(transfer_tax_on_exit(subject, exit_price or purchase_price))

    risks = [f for f in findings if f.severity == "risk" and f.applies]
    opps = [f for f in findings if f.severity == "opportunity" and f.applies]
    rent_growth = next((f.numbers.get("underwriting_rent_growth") for f in findings
                        if f.key == "rent_regulation"), 0.03)

    return {
        "as_of": RULES_AS_OF.isoformat(),
        "subject": asdict(subject),
        "findings": [asdict(f) for f in findings],
        "summary": {
            "risk_flags": [f.headline for f in risks],
            "opportunity_flags": [f.headline for f in opps],
            "underwriting_rent_growth": rent_growth,
            "regime": next((f.numbers.get("regime") for f in findings if f.key == "rent_regulation"), None),
        },
        "disclaimer": "Rules engine output, not legal advice. Verify with ZIMAS, LAHD and the County Assessor.",
    }
