"""
appraiser_engine.py

Top-level integration engine that orchestrates:
- Listing parsers (Zillow, Redfin, Realtor, Homes.com, Century21, LoopNet)
- Address normalization
- APN / assessor data (optional, if provided)
- Zoning lookup (optional, if provided)
- Rental comp aggregation (Apartments.com + manual comps)
- Income approach (external model, assumed available)
- Cap rate model
- DSCR loan model
- Recommendation engine

This module is designed to produce a single structured "Appraisal Report"
for a subject property in Los Angeles (or elsewhere in CA with similar logic).

NOTE:
This engine assumes that the following modules/classes already exist
in your repository:

- services.zillow_parser.ZillowParser
- services.redfin_parser.RedfinParser
- services.realtor_parser.RealtorParser
- services.homesdotcom_parser.HomesDotComParser
- services.century21_parser.Century21Parser
- services.loopnet_parser.LoopNetParser
- services.apartments_parser.ApartmentsParser

- tools.address_normalizer.AddressNormalizer
- tools.apn_lookup.APNLookup
- tools.zoning_lookup.ZoningLookup
- tools.rental_comp_aggregator.RentalCompAggregator

- models.income_approach.IncomeApproach           (NOI / income modeling)
- models.cap_rate_model.CapRateModel
- models.dscr_loan_model.DSCRLoanModel
- models.recommendation_engine.RecommendationEngine
- models.risk_scoring.RiskScoring                  (if implemented)
- models.value_add_model.ValueAddModel             (if implemented)

You can adjust imports if your actual filenames differ.
"""

from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

# ---- Listing parsers ----
from services.zillow_parser import ZillowParser
from services.redfin_parser import RedfinParser
from services.realtor_parser import RealtorParser
from services.homesdotcom_parser import HomesDotComParser
from services.century21_parser import Century21Parser
from services.loopnet_parser import LoopNetParser
from services.apartments_parser import ApartmentsParser

# ---- Tools ----
from tools.address_normalizer import AddressNormalizer
from tools.apn_lookup import APNLookup
from tools.zoning_lookup import ZoningLookup
from tools.rental_comp_aggregator import RentalCompAggregator

# ---- Core models ----
from models.income_approach import IncomeApproach
from models.cap_rate_model import CapRateModel
from models.dscr_loan_model import DSCRLoanModel
from models.recommendation_engine import RecommendationEngine
# Optional, if present:
# from models.risk_scoring import RiskScoring
# from models.value_add_model import ValueAddModel


class AppraiserEngine:
    """
    Main orchestration class.

    Usage example (conceptual):

        engine = AppraiserEngine()

        report = engine.run_full_appraisal({
            "primary_url": "https://www.zillow.com/homedetails/...",
            "rental_apartments_url": "https://www.apartments.com/...",
            "apn": "5055-008-012",
            "assessor_html": "<html>...</html>",   # optional, if copied
            "zoning_code": "RD1.5-1-TOC",          # or
            "zimas_html": "<html>...</html>",      # optional
            "financing": {
                "interest_rate": 0.0675,
                "amort_years": 30,
                "min_dscr": 1.20,
                "max_ltv": 0.75,
            },
            "jurisdiction": {
                "is_rent_controlled": True,
                "jurisdiction": "LA City",
                "submarket_class": "stable"
            },
            "manual_rent_comps": [
                {"beds": 2, "baths": 1, "sqft": 850, "rent": 2400, "source": "manual"},
            ],
        })

    The engine returns a structured dict with keys:
        - success
        - subject
        - rental
        - income
        - cap_rate
        - financing
        - valuation
        - recommendation
        - raw_parsed
    """

    # ---------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------

    def run_full_appraisal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-level orchestration.

        config keys (all optional except primary_url):

            "primary_url": str                  # Zillow / Redfin / etc.
            "secondary_urls": List[str]        # future multiparser use

            "rental_apartments_url": str       # Apartments.com URL (optional)
            "manual_rent_comps": List[dict]    # optional manual comps

            "apn": str                         # APN string (optional)
            "assessor_html": str               # raw HTML from LA Assessor (optional)

            "zoning_code": str                 # zoning code string (optional)
            "zimas_html": str                  # raw HTML from ZIMAS (optional)

            "financing": {
                "interest_rate": float,        # e.g., 0.0675
                "amort_years": int,            # e.g., 30
                "min_dscr": float,             # e.g., 1.20
                "max_ltv": float,              # e.g., 0.75
            }

            "jurisdiction": {
                "is_rent_controlled": bool,
                "jurisdiction": str,           # e.g., "LA City"
                "submarket_class": str,        # "prime/core/stable/transitional/distressed"
            }

        Returns a structured appraisal report.
        """
        primary_url = config.get("primary_url")
        if not primary_url:
            return {"success": False, "error": "primary_url is required"}

        # 1) Parse main listing
        listing_data = self._parse_listing(primary_url)

        # 2) Build subject profile (address, APN, zoning)
        subject_profile = self._build_subject_profile(
            listing_data=listing_data,
            apn=config.get("apn"),
            assessor_html=config.get("assessor_html"),
            zoning_code=config.get("zoning_code"),
            zimas_html=config.get("zimas_html"),
        )

        # 3) Rental profile (Apartments.com + manual comps)
        rental_profile = self._build_rental_profile(
            subject_profile=subject_profile,
            apartments_url=config.get("rental_apartments_url"),
            manual_comps=config.get("manual_rent_comps") or [],
        )

        # 4) Income approach (NOI, income summary)
        income_profile = self._build_income_profile(
            subject_profile=subject_profile,
            rental_profile=rental_profile,
        )

        # 5) Cap rate (based on property type, submarket, risk)
        cap_rate_profile = self._build_cap_rate_profile(
            subject_profile=subject_profile,
            jurisdiction=config.get("jurisdiction") or {},
            income_profile=income_profile,
        )

        # 6) Financing (DSCR loan sizing)
        financing_profile = self._build_financing_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
            financing=config.get("financing") or {},
        )

        # 7) Valuation (as-is & stabilized – if your IncomeApproach/ValueAdd models expose it)
        valuation_profile = self._build_valuation_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
        )

        # 8) Recommendation engine (BUY / WATCH / PASS)
        recommendation = self._build_recommendation(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            financing_profile=financing_profile,
            valuation_profile=valuation_profile,
            jurisdiction=config.get("jurisdiction") or {},
        )

        return {
            "success": True,
            "subject": subject_profile,
            "rental": rental_profile,
            "income": income_profile,
            "cap_rate": cap_rate_profile,
            "financing": financing_profile,
            "valuation": valuation_profile,
            "recommendation": recommendation,
            "raw_parsed": {
                "listing": listing_data,
            },
        }

    # ---------------------------------------------------------
    # 1) Listing parsing
    # ---------------------------------------------------------

    def _parse_listing(self, url: str) -> Dict[str, Any]:
        """
        Routes to the appropriate parser based on domain.
        """
        domain = urlparse(url).netloc.lower()

        parser = None

        if "zillow.com" in domain:
            parser = ZillowParser(url)
        elif "redfin.com" in domain:
            parser = RedfinParser(url)
        elif "realtor.com" in domain:
            parser = RealtorParser(url)
        elif "homes.com" in domain:
            parser = HomesDotComParser(url)
        elif "century21.com" in domain:
            parser = Century21Parser(url)
        elif "loopnet.com" in domain:
            parser = LoopNetParser(url)
        else:
            return {"success": False, "error": f"Unsupported listing domain: {domain}"}

        try:
            data = parser.parse()
            data["source_url"] = url
            return data
        except Exception as e:
            return {"success": False, "error": f"Parser failure: {e}"}

    # ---------------------------------------------------------
    # 2) Subject profile: address, APN, zoning
    # ---------------------------------------------------------

    def _build_subject_profile(
        self,
        listing_data: Dict[str, Any],
        apn: Optional[str],
        assessor_html: Optional[str],
        zoning_code: Optional[str],
        zimas_html: Optional[str],
    ) -> Dict[str, Any]:
        """
        Builds a unified subject profile dictionary.
        """
        addr_norm_tool = AddressNormalizer()
        apn_tool = APNLookup()
        zoning_tool = ZoningLookup()

        # Address
        address_full = listing_data.get("address_full") or ""
        addr_norm = addr_norm_tool.normalize(address_full)

        # APN & assessor
        apn_result = None
        if apn:
            apn_result = apn_tool.lookup(apn, assessor_html=assessor_html)

        # Zoning
        zoning_result = zoning_tool.lookup(
            zoning_code=zoning_code,
            zimas_html=zimas_html,
        )

        subject_profile = {
            "address_raw": address_full,
            "address_normalized": addr_norm,
            "apn_info": apn_result,
            "zoning_info": zoning_result,
            "listing_core": {
                "price": listing_data.get("price"),
                "beds": listing_data.get("beds"),
                "baths": listing_data.get("baths"),
                "sqft": listing_data.get("sqft") or listing_data.get("building_sqft"),
                "lot_size": listing_data.get("lot_size") or listing_data.get("lot_sqft"),
                "year_built": listing_data.get("year_built"),
                "property_type_raw": listing_data.get("property_type"),
                "num_units": listing_data.get("num_units"),
                "source": listing_data.get("source"),
                "source_url": listing_data.get("source_url"),
            },
        }

        return subject_profile

    # ---------------------------------------------------------
    # 3) Rental profile
    # ---------------------------------------------------------

    def _build_rental_profile(
        self,
        subject_profile: Dict[str, Any],
        apartments_url: Optional[str],
        manual_comps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Builds rental comp profile using Apartments.com + manual comps.
        """
        subject_beds = subject_profile["listing_core"].get("beds")
        subject_baths = subject_profile["listing_core"].get("baths")
        subject_sqft = subject_profile["listing_core"].get("sqft")

        aggregator = RentalCompAggregator(
            subject_beds=subject_beds,
            subject_baths=subject_baths,
            subject_sqft=subject_sqft,
        )

        apartments_data = None
        if apartments_url:
            try:
                ap_parser = ApartmentsParser(apartments_url)
                apartments_data = ap_parser.parse()
                if apartments_data.get("success"):
                    aggregator.add_comps_from_apartments(apartments_data)
            except Exception:
                apartments_data = {"success": False, "error": "Failed to parse Apartments.com URL"}

        # Manual comps
        if manual_comps:
            aggregator.add_many_manual_comps(manual_comps)

        rent_summary = aggregator.summary()

        return {
            "apartments_url": apartments_url,
            "apartments_data_success": apartments_data.get("success") if apartments_data else None,
            "manual_comp_count": len(manual_comps),
            "rent_summary": rent_summary,
        }

    # ---------------------------------------------------------
    # 4) Income profile (NOI, etc.)
    # ---------------------------------------------------------

    def _build_income_profile(
        self,
        subject_profile: Dict[str, Any],
        rental_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Uses IncomeApproach model to estimate NOI and related metrics.

        This assumes IncomeApproach can accept:
            - subject data (beds, baths, units, sqft, etc.)
            - rent summary (recommended_rent)
        and return a .summary() dict with:
            - noi
            - noi_stabilized
            - expense_ratio
            - gross_potential_income
            - etc.

        Adjust the call if your IncomeApproach implementation differs.
        """
        listing = subject_profile["listing_core"]
        rent_summary = rental_profile["rent_summary"]
        rec_rent = rent_summary["recommended_rent"]["rent_estimate"]

        income_model = IncomeApproach(
            beds=listing.get("beds"),
            baths=listing.get("baths"),
            num_units=listing.get("num_units") or 1,
            sqft=listing.get("sqft"),
            market_rent=rec_rent,
            rent_detail=rent_summary,
        )

        income_summary = income_model.summary()

        return income_summary

    # ---------------------------------------------------------
    # 5) Cap rate profile
    # ---------------------------------------------------------

    def _build_cap_rate_profile(
        self,
        subject_profile: Dict[str, Any],
        jurisdiction: Dict[str, Any],
        income_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Uses CapRateModel to determine base and adjusted cap.
        """
        listing = subject_profile["listing_core"]

        # Rough property type classification for cap rate model
        num_units = listing.get("num_units")
        property_type_raw = (listing.get("property_type_raw") or "").lower()

        if num_units and num_units >= 5:
            cap_prop_type = "5+"
        elif num_units and 2 <= num_units <= 4:
            cap_prop_type = "2-4"
        elif "retail" in property_type_raw:
            cap_prop_type = "retail"
        elif "office" in property_type_raw:
            cap_prop_type = "office"
        elif "industrial" in property_type_raw:
            cap_prop_type = "industrial"
        elif "mixed" in property_type_raw:
            cap_prop_type = "mixed_use"
        else:
            cap_prop_type = "sfr"

        submarket_class = jurisdiction.get("submarket_class", "stable")
        is_rent_controlled = bool(jurisdiction.get("is_rent_controlled"))

        # Optional: if you have a RiskScoring model, you can calculate a risk_score here
        risk_score = jurisdiction.get("risk_score")

        cap_model = CapRateModel(
            property_type=cap_prop_type,
            submarket_class=submarket_class,
            risk_score=risk_score,
            is_rent_controlled=is_rent_controlled,
        )

        cap_summary = cap_model.summary()

        return cap_summary

    # ---------------------------------------------------------
    # 6) Financing / DSCR profile
    # ---------------------------------------------------------

    def _build_financing_profile(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        purchase_price: Optional[float],
        financing: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Uses DSCRLoanModel for loan sizing and DSCR.
        """
        noi = income_profile.get("noi") or income_profile.get("noi_stabilized")
        if not noi or not purchase_price:
            return {
                "inputs": financing,
                "note": "Missing NOI or purchase price; DSCR loan sizing not computed.",
            }

        interest_rate = financing.get("interest_rate", 0.0675)
        amort_years = financing.get("amort_years", 30)
        min_dscr = financing.get("min_dscr", 1.20)
        max_ltv = financing.get("max_ltv", 0.75)

        dscr_model = DSCRLoanModel(
            noi=noi,
            purchase_price=purchase_price,
            interest_rate=interest_rate,
            amort_years=amort_years,
            min_dscr=min_dscr,
            max_ltv=max_ltv,
        )

        dscr_summary = dscr_model.summary()
        return dscr_summary

    # ---------------------------------------------------------
    # 7) Valuation profile
    # ---------------------------------------------------------

    def _build_valuation_profile(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        purchase_price: Optional[float],
    ) -> Dict[str, Any]:
        """
        Simple valuation using cap rate model + NOI.

        If you also have a ValueAddModel, you can extend this to include:
            - stabilized NOI
            - ARV (after-repositioning value)
            - equity creation, etc.
        """
        noi = income_profile.get("noi")
        noi_stabilized = income_profile.get("noi_stabilized") or noi
        cap_rate = cap_rate_profile.get("final_cap_rate")

        as_is_value = None
        stabilized_value = None

        if noi and cap_rate and cap_rate > 0:
            as_is_value = round(noi / cap_rate, 2)
        if noi_stabilized and cap_rate and cap_rate > 0:
            stabilized_value = round(noi_stabilized / cap_rate, 2)

        return {
            "purchase_price": purchase_price,
            "as_is_value": as_is_value,
            "stabilized_value": stabilized_value,
        }

    # ---------------------------------------------------------
    # 8) Recommendation
    # ---------------------------------------------------------

    def _build_recommendation(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        financing_profile: Dict[str, Any],
        valuation_profile: Dict[str, Any],
        jurisdiction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calls RecommendationEngine with the key inputs.
        """
        # If you implement a RiskScoring model, calculate real risk_score here.
        risk_score = jurisdiction.get("risk_score")
        risk_grade = jurisdiction.get("risk_grade")

        cash_on_cash = income_profile.get("cash_on_cash")

        recommender = RecommendationEngine(
            risk_score=risk_score,
            risk_grade=risk_grade,
            dscr_summary=financing_profile,
            cap_rate_summary=cap_rate_profile,
            valuation_summary=valuation_profile,
            cash_on_cash=cash_on_cash,
            jurisdiction_flags={
                "is_rent_controlled": jurisdiction.get("is_rent_controlled", False),
                "jurisdiction": jurisdiction.get("jurisdiction"),
            },
        )

        return recommender.recommend()
