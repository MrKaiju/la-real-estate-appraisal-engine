"""
appraiser_engine.py

Top-level integration engine that orchestrates:
- Listing parsers (Zillow, Redfin, Realtor, Homes.com, Century21, LoopNet)
- Address normalization
- APN / assessor data (optional, if provided)
- Zoning lookup (optional, if provided)
- Rental comp aggregation (Apartments.com + manual comps)
- Income approach (NOI modeling)
- Cap rate model
- DSCR loan model
- Sales comparison model (NEW)
- Market Confidence Score (NEW)
- Narrative generation (NEW)
- HTML/PDF report generation (NEW)
- Recommendation engine

Produces a complete "Appraisal Report" in structured dict form.

Requires the following modules:

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
    sales_comp_model.SalesCompModel
    narrative_builder.NarrativeBuilder (NEW)

reports/
    report_generator.build_html_report
    report_generator.build_pdf_report
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

# ---- Models ----
from models.income_approach import IncomeApproach
from models.cap_rate_model import CapRateModel
from models.dscr_loan_model import DSCRLoanModel
from models.recommendation_engine import RecommendationEngine
from models.sales_comp_model import SalesCompModel
from models.narrative_builder import NarrativeBuilder

# ---- Report Generator (NEW) ----
from reports.report_generator import build_html_report, build_pdf_report



class AppraiserEngine:
    """
    Main orchestration class coordinating all appraisal components.
    """

    # ---------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------

    def run_full_appraisal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the full appraisal workflow.
        """

        # -------------------------------
        # 1. Ensure a primary URL exists
        # -------------------------------
        primary_url = config.get("primary_url")
        if not primary_url:
            return {"success": False, "error": "primary_url is required"}

        # -------------------------------
        # 2. Parse listing
        # -------------------------------
        listing_data = self._parse_listing(primary_url)

        # -------------------------------
        # 3. Subject Profile
        # -------------------------------
        subject_profile = self._build_subject_profile(
            listing_data=listing_data,
            apn=config.get("apn"),
            assessor_html=config.get("assessor_html"),
            zoning_code=config.get("zoning_code"),
            zimas_html=config.get("zimas_html"),
        )

        # -------------------------------
        # 4. Rental Profile
        # -------------------------------
        rental_profile = self._build_rental_profile(
            subject_profile=subject_profile,
            apartments_url=config.get("rental_apartments_url"),
            manual_comps=config.get("manual_rent_comps") or [],
        )

        # -------------------------------
        # 5. Income Approach
        # -------------------------------
        income_profile = self._build_income_profile(
            subject_profile=subject_profile,
            rental_profile=rental_profile,
        )

        # -------------------------------
        # 6. Cap Rate Profile
        # -------------------------------
        cap_rate_profile = self._build_cap_rate_profile(
            subject_profile=subject_profile,
            jurisdiction=config.get("jurisdiction") or {},
            income_profile=income_profile,
        )

        # -------------------------------
        # 7. DSCR / Financing
        # -------------------------------
        financing_profile = self._build_financing_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
            financing=config.get("financing") or {},
        )

        # -------------------------------
        # 8. Valuation
        # -------------------------------
        valuation_profile = self._build_valuation_profile(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            purchase_price=listing_data.get("price"),
        )

        # -------------------------------
        # 9. Sales Comparison (optional)
        # -------------------------------
        sales_comparison_result = None
        if "sales_comps" in config:
            sales_comparison_result = self._run_sales_comparison(
                subject_profile=subject_profile.get("listing_core", {}),
                sales_comps=config["sales_comps"],
            )

        # -------------------------------
        # 10. Recommendation (w/ Market Confidence)
        # -------------------------------
        recommendation = self._build_recommendation(
            income_profile=income_profile,
            cap_rate_profile=cap_rate_profile,
            financing_profile=financing_profile,
            valuation_profile=valuation_profile,
            jurisdiction=config.get("jurisdiction") or {},
            sales_comparison=sales_comparison_result,
        )

        # -------------------------------
        # 11. Narrative (NEW)
        # -------------------------------
        narrative = NarrativeBuilder(
            subject=subject_profile,
            income=income_profile,
            cap_rate=cap_rate_profile,
            financing=financing_profile,
            valuation=valuation_profile,
            sales_comparison=sales_comparison_result or {},
            market_confidence=recommendation.get("market_confidence") or {},
            recommendation=recommendation,
            jurisdiction=config.get("jurisdiction") or {},
        ).build_narrative()

        # -------------------------------
        # 12. Base report dictionary
        # -------------------------------
        report = {
            "success": True,
            "subject": subject_profile,
            "rental": rental_profile,
            "income": income_profile,
            "cap_rate": cap_rate_profile,
            "financing": financing_profile,
            "valuation": valuation_profile,
            "sales_comparison": sales_comparison_result,
            "recommendation": recommendation,
            "narrative": narrative,
            "raw_parsed": {
                "listing": listing_data,
            },
        }

        # -------------------------------
        # 13. Optional HTML/PDF generation (NEW)
        # -------------------------------
        report_options = config.get("report_options") or {}
        report_outputs: Dict[str, Any] = {}

        # HTML generation
        if report_options.get("generate_html"):
            html = build_html_report(report)
            report_outputs["html"] = html

        # PDF generation (requires HTML)
        if report_options.get("generate_pdf") and report_outputs.get("html"):
            pdf_path = report_options.get("pdf_output_path", "appraisal_report.pdf")
            try:
                output_path = build_pdf_report(report_outputs["html"], pdf_path)
                report_outputs["pdf_path"] = output_path
            except Exception as e:
                report_outputs["pdf_error"] = str(e)

        report["report_outputs"] = report_outputs
        return report

    # ---------------------------------------------------------
    # Listing Parsing
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
    # Subject Profile
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
        apn_lookup = APNLookup()
        zoning_lookup = ZoningLookup()

        address_full = listing_data.get("address_full") or ""
        normalized = addr_norm_tool.normalize(address_full)

        apn_result = apn_lookup.lookup(apn, assessor_html) if apn else None
        zoning_result = zoning_lookup.lookup(
            zoning_code=zoning_code,
            zimas_html=zimas_html,
        )

        return {
            "address_raw": address_full,
            "address_normalized": normalized,
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
    # Rental Profile
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
    # Income Profile
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
    # Cap Rate Profile
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

        # property type logic
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

        model = CapRateModel(
            property_type=prop_type,
            submarket_class=jurisdiction.get("submarket_class", "stable"),
            risk_score=jurisdiction.get("risk_score"),
            is_rent_controlled=jurisdiction.get("is_rent_controlled", False),
        )

        return model.summary()

    # ---------------------------------------------------------
    # Financing / DSCR
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
                "note": "Missing NOI or purchase price; DSCR not computed.",
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
    # Valuation Profile
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

        as_is = stabilized = None
        if noi and cap_rate:
            as_is = round(noi / cap_rate, 2)
        if noi_stab and cap_rate:
            stabilized = round(noi_stab / cap_rate, 2)

        return {
            "purchase_price": purchase_price,
            "as_is_value": as_is,
            "stabilized_value": stabilized,
        }

    # ---------------------------------------------------------
    # Sales Comparison
    # ---------------------------------------------------------

    def _run_sales_comparison(self, subject_profile: Dict, sales_comps: List[Dict]) -> Dict:
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
            return {"success": False, "error": f"Sales comparison failed: {str(e)}"}

    # ---------------------------------------------------------
    # Recommendation (includes Market Confidence)
    # ---------------------------------------------------------

    def _build_recommendation(
        self,
        income_profile: Dict[str, Any],
        cap_rate_profile: Dict[str, Any],
        financing_profile: Dict[str, Any],
        valuation_profile: Dict[str, Any],
        jurisdiction: Dict[str, Any],
        sales_comparison: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        engine = RecommendationEngine(
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
            sales_comparison=sales_comparison,   # NEW
        )

        return engine.recommend()
