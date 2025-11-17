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
- Sales comparison model (NEW)
- Recommendation engine

Produces a structured "Appraisal Report" for a subject property.

This engine assumes the following modules already exist:

services/
    zillow_parser.ZillowParser
    redfin_parser.RedfinParser
    realtor_parser.RealtorParser
    homesdotcom_parser.HomesDotComParser
    century21_parser.Century21Parser
    loopnet_parser.LoopNetParser
    apartments_parser.ApartmentsParser

tools/
    address_normalizer.AddressNormalizer
    apn_lookup.APNLookup
    zoning_lookup.ZoningLookup
    rental_comp_aggregator.RentalCompAggregator

models/
    income_approach.IncomeApproach
    cap_rate_model.CapRateModel
    dscr_loan_model.DSCRLoanModel
    recommendation_engine.RecommendationEngine
    sales_comp_model.SalesCompModel          # NEW
    risk_scoring.RiskScoring (optional)
    value_add_model.ValueAddModel (optional)
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
from models.sales_comp_model import SalesCompModel  # NEW IMPORT


class AppraiserEngine:
    """
    Main orchestration class.
    """

    # ---------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------

    def run_full_appraisal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-level orchestration.

        Returns a complete appraisal report.
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

        # 3) Rental profile
        rental_profile = self._build_rental_profile(
            subject_profile=subject_profile,
            apartments_url=config.get("rental_apartments_url"),
            manual_comps=config.get("manual_rent_comps") or [],
        )

        # 4) Income approach
        income_profile = self._build_income_profile(
            subject_profile=subject_profile,
            rental_profile=rental_profile,
        )

        # 5) Cap rate approach
        cap_rate_profile = self._build_cap_rate_profile(
            subject_profile=subject_profile,
            jurisdiction=config.get("jurisdiction") or {},
            income_profile=income_profile,
        )

        # 6) DSCR loan model
        financing_profile = self._build_financing_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
            financing=config.get("financing") or {},
        )

        # 7) Valuation profile
        valuation_profile = self._build_valuation_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
        )

        # 8) Sales Comparison (OPTIONAL)
        sales_comparison_result = None
        if "sales_comps" in config:
            subject_for_comps = subject_profile.get("listing_core", {})
            sales_comparison_result = self._run_sales_comparison(
                subject_profile=subject_for_comps,
                sales_comps=config["sales_comps"],
            )

        # 9) Recommendation
        recommendation = self._build_recommendation(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            financing_profile=financing_profile,
            valuation_profile=valuation_profile,
            jurisdiction=config.get("jurisdiction") or {},
        )

        # Final structured appraisal report
        return {
            "success": True,
            "subject": subject_profile,
            "rental": rental_profile,
            "income": income_profile,
            "cap_rate": cap_rate_profile,
            "financing": financing_profile,
            "valuation": valuation_profile,
            "sales_comparison": sales_comparison_result,   # NEW
            "recommendation": recommendation,
            "raw_parsed": {
                "listing": listing_data,
            },
        }

    # ---------------------------------------------------------
    # 1) Listing parsing
    # ---------------------------------------------------------

    def _parse_listing(self, url: str) -> Dict[str, Any]:
        domain = urlparse(url).netloc.lower()

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
    # 2) Subject profile (Address, APN, Zoning)
    # ---------------------------------------------------------

    def _build_subject_profile(
        self,
        listing_data: Dict[str, Any],
        apn: Optional[str],
        assessor_html: Optional[str],
        zoning_code: Optional[str],
        zimas_html: Optional[str],
    ) -> Dict[str, Any]:

        addr_norm_tool = AddressNormalizer()
        apn_tool = APNLookup()
        zoning_tool = ZoningLookup()

        address_full = listing_data.get("address_full") or ""
        addr_norm = addr_norm_tool.normalize(address_full)

        # APN
        apn_result = None
        if apn:
            apn_result = apn_tool.lookup(apn, assessor_html=assessor_html)

        # Zoning
        zoning_result = zoning_tool.lookup(
            zoning_code=zoning_code,
            zimas_html=zimas_html,
        )

        return {
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

    # ---------------------------------------------------------
    # 3) Rental profile
    # ---------------------------------------------------------

    def _build_rental_profile(
        self,
        subject_profile: Dict[str, Any],
        apartments_url: Optional[str],
        manual_comps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        listing = subject_profile["listing_core"]
        aggregator = RentalCompAggregator(
            subject_beds=listing.get("beds"),
            subject_baths=listing.get("baths"),
            subject_sqft=listing.get("sqft"),
        )

        apartments_data = None
        if apartments_url:
            try:
                parser = ApartmentsParser(apartments_url)
                apartments_data = parser.parse()
                if apartments_data.get("success"):
                    aggregator.add_comps_from_apartments(apartments_data)
            except Exception:
                apartments_data = {"success": False}

        if manual_comps:
            aggregator.add_many_manual_comps(manual_comps)

        return {
            "apartments_url": apartments_url,
            "apartments_data_success": apartments_data.get("success") if apartments_data else None,
            "manual_comp_count": len(manual_comps),
            "rent_summary": aggregator.summary(),
        }

    # ---------------------------------------------------------
    # 4) Income profile
    # ---------------------------------------------------------

    def _build_income_profile(
        self,
        subject_profile: Dict[str, Any],
        rental_profile: Dict[str, Any],
    ) -> Dict[str, Any]:

        listing = subject_profile["listing_core"]
        rent_summary = rental_profile["rent_summary"]
        rec_rent = rent_summary["recommended_rent"]["rent_estimate"]

        model = IncomeApproach(
            beds=listing.get("beds"),
            baths=listing.get("baths"),
            num_units=listing.get("num_units") or 1,
            sqft=listing.get("sqft"),
            market_rent=rec_rent,
            rent_detail=rent_summary,
        )

        return model.summary()

    # ---------------------------------------------------------
    # 5) Cap rate profile
    # ---------------------------------------------------------

    def _build_cap_rate_profile(
        self,
        subject_profile: Dict[str, Any],
        jurisdiction: Dict[str, Any],
        income_profile: Dict[str, Any],
    ) -> Dict[str, Any]:

        listing = subject_profile["listing_core"]
        num_units = listing.get("num_units")
        prop_raw = (listing.get("property_type_raw") or "").lower()

        if num_units and num_units >= 5:
            prop_type = "5+"
        elif num_units and 2 <= num_units <= 4:
            prop_type = "2-4"
        elif "retail" in prop_raw:
            prop_type = "retail"
        elif "office" in prop_raw:
            prop_type = "office"
        elif "industrial" in prop_raw:
            prop_type = "industrial"
        elif "mixed" in prop_raw:
            prop_type = "mixed_use"
        else:
            prop_type = "sfr"

        is_rent_ctrl = jurisdiction.get("is_rent_controlled", False)
        submarket_class = jurisdiction.get("submarket_class", "stable")
        risk_score = jurisdiction.get("risk_score")

        model = CapRateModel(
            property_type=prop_type,
            submarket_class=submarket_class,
            risk_score=risk_score,
            is_rent_controlled=is_rent_ctrl,
        )

        return model.summary()

    # ---------------------------------------------------------
    # 6) DSCR financing profile
    # ---------------------------------------------------------

    def _build_financing_profile(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        purchase_price: Optional[float],
        financing: Dict[str, Any],
    ) -> Dict[str, Any]:

        noi = income_profile.get("noi") or income_profile.get("noi_stabilized")
        if not noi or not purchase_price:
            return {
                "inputs": financing,
                "note": "Missing NOI or purchase price; DSCR not computed."
            }

        model = DSCRLoanModel(
            noi=noi,
            purchase_price=purchase_price,
            interest_rate=financing.get("interest_rate", 0.0675),
            amort_years=financing.get("amort_years", 30),
            min_dscr=financing.get("min_dscr", 1.20),
            max_ltv=financing.get("max_ltv", 0.75),
        )

        return model.summary()

    # ---------------------------------------------------------
    # 7) Valuation profile
    # ---------------------------------------------------------

    def _build_valuation_profile(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        purchase_price: Optional[float],
    ) -> Dict[str, Any]:

        noi = income_profile.get("noi")
        noi_stab = income_profile.get("noi_stabilized") or noi
        cap_rate = cap_rate_profile.get("final_cap_rate")

        as_is = None
        stabilized = None

        if noi and cap_rate and cap_rate > 0:
            as_is = round(noi / cap_rate, 2)
        if noi_stab and cap_rate and cap_rate > 0:
            stabilized = round(noi_stab / cap_rate, 2)

        return {
            "purchase_price": purchase_price,
            "as_is_value": as_is,
            "stabilized_value": stabilized,
        }

    # ---------------------------------------------------------
    # SALES COMPARISON (NEW)
    # ---------------------------------------------------------

    def _run_sales_comparison(self, subject_profile: Dict, sales_comps: List[Dict]) -> Dict:
        """
        Run the sales comparison model if comps are provided.

        subject_profile should come from:
            subject_profile["listing_core"]
        """
        try:
            if not subject_profile:
                return {"success": False, "error": "Missing subject profile"}

            if not sales_comps:
                return {"success": False, "error": "No comparable sales provided"}

            model = SalesCompModel(
                subject=subject_profile,
                comps=sales_comps
            )
            summary = model.summary()
            summary["success"] = True
            return summary

        except Exception as e:
            return {
                "success": False,
                "error": f"Sales comparison failed: {str(e)}"
            }

    # ---------------------------------------------------------
    # 9) Recommendation assembly
    # ---------------------------------------------------------

    def _build_recommendation(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        financing_profile: Dict[str, Any],
        valuation_profile: Dict[str, Any],
        jurisdiction: Dict[str, Any],
    ) -> Dict[str, Any]:

        recommender = RecommendationEngine(
            risk_score=jurisdiction.get("risk_score"),
            risk_grade=jurisdiction.get("risk_grade"),
            dscr_summary=financing_profile,
            cap_rate_summary=cap_rate_profile,
            valuation_summary=valuation_profile,
            cash_on_cash=income_profile.get("cash_on_cash"),
            jurisdiction_flags={
                "is_rent_controlled": jurisdiction.get("is_rent_controlled", False),
                "jurisdiction": jurisdiction.get("jurisdiction"),
            },
        )

        return recommender.recommend()
