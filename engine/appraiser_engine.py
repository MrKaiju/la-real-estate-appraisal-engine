"""
engine/appraiser_engine.py

Top-level orchestration for the LA appraisal / underwriting engine.

Pipeline
    1. Subject intake      structured `subject` dict (preferred) or a listing URL
    2. Subject profile     address normalisation, APN, zoning, property type
    3. LA regulatory stack RSO / AB 1482 / ULA / Prop 13 / soft-story / SB 9 / fire zone
    4. Rental profile      rent comps -> market rent per unit
    5. Income approach     explicit LA expense stack -> NOI, going-in cap, GRM
    6. Cap rate            2026-calibrated grid + risk + rent-control premium
    7. Financing           DSCR loan sizing, cash-on-cash
    8. Valuation           income value, as-is and stabilized
    9. Sales comparison    optional, if comps supplied
   10. House-hack          optional, for 1-4 unit owner-occupants
   11. Recommendation      BUY / WATCH / PASS with component transparency
   12. Narrative + report  plain-English summary, optional HTML / PDF

Design rule: the engine must produce a complete, honest result from structured
input alone. Scrapers are an optional convenience, never a dependency.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from services.zillow_parser import ZillowParser
from services.redfin_parser import RedfinParser
from services.realtor_parser import RealtorParser
from services.homesdotcom_parser import HomesDotComParser
from services.century21_parser import Century21Parser
from services.loopnet_parser import LoopNetParser
from services.apartments_parser import ApartmentsParser

from tools.address_normalizer import AddressNormalizer
from tools.apn_lookup import APNLookup
from tools.zoning_lookup import ZoningLookup
from tools.rental_comp_aggregator import RentalCompAggregator

from models.income_approach import IncomeApproach
from models.cap_rate_model import CapRateModel
from models.dscr_loan_model import DSCRLoanModel
from models.recommendation_engine import RecommendationEngine
from models.sales_comp_model import SalesCompModel
from models.narrative_builder import NarrativeBuilder

from core import la_regulatory
from core.enrichment import Enricher, sales_comps_from_extras
from core.house_hack import HouseHackInputs, analyze as analyze_house_hack

from reports.report_generator import build_html_report, build_pdf_report


SUBJECT_FIELDS = (
    "address_full", "city", "zip", "price", "beds", "baths", "sqft", "lot_size", "year_built",
    "property_type", "num_units", "zone", "stories", "wood_frame", "tuck_under_parking",
    "in_very_high_fire_hazard_zone", "unit_rents", "current_rents", "owner_is_corporate",
    "listed_noi", "listed_cap_rate",
)


class AppraiserEngine:
    """Main orchestration class coordinating all appraisal components."""

    def __init__(self, enricher: Optional[Enricher] = None):
        self.enricher = enricher

    def run_full_appraisal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        warnings: List[str] = []

        # 1. Subject intake -------------------------------------------------
        listing_data, err = self._intake(config, warnings)
        if err:
            return {"success": False, "error": err, "warnings": warnings}

        # 1b. Enrichment (public GIS + licensed APIs), user input always wins ----
        enrichment = self._enrich(listing_data, config, warnings)

        # 2. Subject profile ------------------------------------------------
        subject_profile = self._build_subject_profile(
            listing_data=listing_data,
            apn=config.get("apn"),
            assessor_html=config.get("assessor_html"),
            zoning_code=config.get("zoning_code") or listing_data.get("zone"),
            zimas_html=config.get("zimas_html"),
        )
        core = subject_profile["listing_core"]

        # 3. LA regulatory stack --------------------------------------------
        regulatory = self._build_regulatory(core, listing_data, config)
        jurisdiction = dict(config.get("jurisdiction") or {})
        reg_summary = regulatory["summary"]
        jurisdiction.setdefault("is_rent_controlled", reg_summary["regime"] in
                                ("LA_CITY_RSO", "LA_COUNTY_RSO", "LOCAL_RSO"))
        jurisdiction.setdefault("jurisdiction", listing_data.get("city"))
        jurisdiction.setdefault("submarket_class", "stable")

        # 4. Rental profile --------------------------------------------------
        rental_profile = self._build_rental_profile(
            subject_profile=subject_profile,
            apartments_url=config.get("rental_apartments_url"),
            manual_comps=config.get("manual_rent_comps") or [],
            unit_rents=listing_data.get("unit_rents"),
            warnings=warnings,
        )

        # 5. Income approach --------------------------------------------------
        income_profile = self._build_income_profile(core, rental_profile, regulatory,
                                                    config.get("expenses") or {}, listing_data)
        if not income_profile.get("success"):
            warnings.append(income_profile.get("error", "Income approach could not run."))

        # 6. Cap rate ---------------------------------------------------------
        cap_rate_profile = self._build_cap_rate_profile(core, jurisdiction)

        # 7. Financing --------------------------------------------------------
        financing_profile = self._build_financing_profile(
            income_profile, core.get("price"), config.get("financing") or {})
        income_profile["cash_on_cash"] = self._cash_on_cash(income_profile, financing_profile,
                                                            core.get("price"))

        # 8. Valuation --------------------------------------------------------
        valuation_profile = self._build_valuation_profile(income_profile, cap_rate_profile,
                                                          core.get("price"))

        # 9. Sales comparison ---------------------------------------------------
        sales_comparison_result = None
        if config.get("sales_comps"):
            sales_comparison_result = self._run_sales_comparison(core, config["sales_comps"])

        # 10. House hack ---------------------------------------------------------
        house_hack = self._build_house_hack(core, rental_profile, config, regulatory, warnings)

        # 11. Recommendation --------------------------------------------------------
        recommendation = RecommendationEngine(
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
            sales_comparison=sales_comparison_result,
            income_summary=income_profile,
            regulatory=regulatory,
        ).recommend()

        # 12. Narrative ----------------------------------------------------------------
        narrative = NarrativeBuilder(
            subject=subject_profile,
            income=income_profile,
            cap_rate=cap_rate_profile,
            financing=financing_profile,
            valuation=valuation_profile,
            sales_comparison=sales_comparison_result or {},
            market_confidence=recommendation.get("market_confidence") or {},
            recommendation=recommendation,
            jurisdiction=jurisdiction,
            regulatory=regulatory,
            house_hack=house_hack,
        ).build_narrative()

        report: Dict[str, Any] = {
            "success": True,
            "engine_version": "0.2.0",
            "subject": subject_profile,
            "enrichment": enrichment,
            "regulatory": regulatory,
            "rental": rental_profile,
            "income": income_profile,
            "cap_rate": cap_rate_profile,
            "financing": financing_profile,
            "valuation": valuation_profile,
            "sales_comparison": sales_comparison_result,
            "house_hack": house_hack,
            "recommendation": recommendation,
            "narrative": narrative,
            "warnings": warnings,
            "raw_parsed": {"listing": listing_data},
        }

        report_options = config.get("report_options") or {}
        report_outputs: Dict[str, Any] = {}
        if report_options.get("generate_html"):
            report_outputs["html"] = build_html_report(report)
        if report_options.get("generate_pdf") and report_outputs.get("html"):
            pdf_path = report_options.get("pdf_output_path", "appraisal_report.pdf")
            try:
                report_outputs["pdf_path"] = build_pdf_report(report_outputs["html"], pdf_path)
            except Exception as e:  # pragma: no cover - weasyprint optional
                report_outputs["pdf_error"] = str(e)
        report["report_outputs"] = report_outputs
        return report

    # ------------------------------------------------------------------
    # 1. Intake
    # ------------------------------------------------------------------

    def _intake(self, config: Dict[str, Any], warnings: List[str]):
        subject = dict(config.get("subject") or {})
        url = config.get("primary_url")
        listing: Dict[str, Any] = {}

        if url:
            parsed = self._parse_listing(url)
            if parsed.get("success"):
                listing.update(parsed)
            else:
                warnings.append(f"Listing fetch failed ({parsed.get('error')}); using structured subject.")
                listing["source_url"] = url

        # Structured subject wins over scraped fields.
        for k in SUBJECT_FIELDS:
            if subject.get(k) is not None:
                listing[k] = subject[k]
        listing.setdefault("source", "structured" if subject else listing.get("source"))

        if not listing.get("price"):
            return None, "A purchase/list price is required (subject.price or a parsable listing URL)."
        if not (subject or listing.get("address_full")):
            return None, "Provide `subject` (structured property facts) or a supported listing URL."
        return listing, None

    def _enrich(self, listing: Dict[str, Any], config: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        """Mutates `listing` in place with enriched fields; returns provenance/notes/extras."""
        if config.get("enrich") is False:
            return {"provenance": {k: "user" for k, v in listing.items() if v is not None},
                    "notes": ["enrichment disabled by request"], "extras": {}}
        enricher = self.enricher or Enricher()
        try:
            result = enricher.enrich(listing, apn=config.get("apn"))
        except Exception as e:  # never let enrichment kill the run
            warnings.append(f"Enrichment failed: {e}")
            return {"provenance": {}, "notes": [str(e)], "extras": {}}
        listing.update(result["subject"])
        if not config.get("sales_comps"):
            comps = sales_comps_from_extras(result["extras"])
            if comps:
                config["sales_comps"] = comps
                result["notes"].append(f"sales comps: {len(comps)} from RentCast value AVM")
        for c in (result["extras"].get("conflicts") or []):
            warnings.append(f"{c['field']}: you entered {c['user']}, {c['source']} says {c['enrichment']}; using yours.")
        return {"provenance": result["provenance"], "notes": result["notes"], "extras": result["extras"]}

    def _parse_listing(self, url: str) -> Dict[str, Any]:
        domain = urlparse(url).netloc.lower()
        parsers = {
            "zillow.com": ZillowParser, "redfin.com": RedfinParser, "realtor.com": RealtorParser,
            "homes.com": HomesDotComParser, "century21.com": Century21Parser, "loopnet.com": LoopNetParser,
        }
        cls = next((c for d, c in parsers.items() if d in domain), None)
        if cls is None:
            return {"success": False, "error": f"Unsupported listing domain: {domain}"}
        try:
            parser = cls(url)
            data = parser.parse() if hasattr(parser, "parse") else parser.extract()
            data["source_url"] = url
            return data
        except Exception as e:
            return {"success": False, "error": f"Parser failure: {e}"}

    # ------------------------------------------------------------------
    # 2. Subject profile
    # ------------------------------------------------------------------

    def _build_subject_profile(self, listing_data, apn, assessor_html, zoning_code, zimas_html):
        address_full = listing_data.get("address_full") or ""
        normalized = AddressNormalizer().normalize(address_full) if address_full else None
        apn_result = APNLookup().lookup(apn, assessor_html) if apn else None
        zoning_result = ZoningLookup().lookup(zoning_code=zoning_code, zimas_html=zimas_html) \
            if (zoning_code or zimas_html) else None

        num_units = listing_data.get("num_units")
        prop_type = self._classify_property_type(listing_data.get("property_type"), num_units)
        if num_units is None:
            num_units = {"sfr": 1, "condo": 1, "2-4": 2, "5+": 5}.get(prop_type, 1)

        return {
            "address_raw": address_full,
            "address_normalized": normalized,
            "city": listing_data.get("city"),
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
                "property_type": prop_type,
                "num_units": num_units,
                "zone": zoning_code,
                "source": listing_data.get("source"),
                "source_url": listing_data.get("source_url"),
            },
        }

    @staticmethod
    def _classify_property_type(raw: Optional[str], num_units: Optional[int]) -> str:
        r = (raw or "").lower()
        if num_units and num_units >= 5:
            return "5+"
        if num_units and 2 <= num_units <= 4:
            return "2-4"
        for key in ("retail", "office", "industrial", "land"):
            if key in r:
                return key
        if "mixed" in r:
            return "mixed_use"
        if "condo" in r or "townho" in r:
            return "condo"
        if any(k in r for k in ("duplex", "triplex", "fourplex", "quadplex", "multi")):
            return "2-4"
        if r in ("2-4", "5+", "sfr"):
            return r
        return "sfr"

    # ------------------------------------------------------------------
    # 3. Regulatory
    # ------------------------------------------------------------------

    def _build_regulatory(self, core, listing, config) -> Dict[str, Any]:
        subj = la_regulatory.LASubject(
            city=listing.get("city") or (config.get("jurisdiction") or {}).get("jurisdiction"),
            year_built=core.get("year_built"),
            num_units=core.get("num_units"),
            property_type=core.get("property_type"),
            zone=core.get("zone"),
            lot_sqft=core.get("lot_size"),
            stories=listing.get("stories"),
            wood_frame=listing.get("wood_frame"),
            tuck_under_parking=listing.get("tuck_under_parking"),
            owner_is_corporate=bool(listing.get("owner_is_corporate", False)),
            in_very_high_fire_hazard_zone=listing.get("in_very_high_fire_hazard_zone"),
        )
        exit_price = (config.get("exit") or {}).get("exit_price")
        return la_regulatory.evaluate(subj, purchase_price=core.get("price"), exit_price=exit_price)

    # ------------------------------------------------------------------
    # 4. Rental profile
    # ------------------------------------------------------------------

    def _build_rental_profile(self, subject_profile, apartments_url, manual_comps, unit_rents, warnings):
        listing = subject_profile["listing_core"]
        aggregator = RentalCompAggregator(
            subject_beds=listing.get("beds"),
            subject_baths=listing.get("baths"),
            subject_sqft=listing.get("sqft"),
        )
        apartments_data = None
        if apartments_url:
            try:
                apartments_data = ApartmentsParser(apartments_url).parse()
                if apartments_data.get("success"):
                    aggregator.add_comps_from_apartments(apartments_data)
                else:
                    warnings.append("Apartments.com fetch failed; ignoring.")
            except Exception as e:
                apartments_data = {"success": False}
                warnings.append(f"Apartments.com parser error: {e}")
        if manual_comps:
            aggregator.add_many_manual_comps(manual_comps)

        summary = aggregator.summary()
        rec = summary.get("recommended_rent") or {}
        if unit_rents:
            method = "user_supplied_unit_rents"
            rents = [float(r) for r in unit_rents]
        elif rec.get("rent_estimate"):
            method = rec.get("method")
            rents = [float(rec["rent_estimate"])] * max(1, int(listing.get("num_units") or 1))
        else:
            method, rents = None, []
            warnings.append("No rent evidence: supply unit_rents or manual_rent_comps.")
        return {
            "apartments_url": apartments_url,
            "apartments_data_success": apartments_data.get("success") if apartments_data else None,
            "manual_comp_count": len(manual_comps),
            "rent_summary": summary,
            "unit_rents_monthly": rents,
            "rent_method": method,
        }

    # ------------------------------------------------------------------
    # 5. Income
    # ------------------------------------------------------------------

    def _build_income_profile(self, core, rental_profile, regulatory, expenses, listing):
        rents = rental_profile["unit_rents_monthly"]
        findings = {f["key"]: f for f in regulatory["findings"]}
        ins = findings.get("insurance", {}).get("numbers", {})
        ins_rate = expenses.get("insurance_rate_of_value") or (
            (ins.get("insurance_rate_of_value_low", 0.004) + ins.get("insurance_rate_of_value_high", 0.005)) / 2)
        rso = regulatory["summary"]["regime"] in ("LA_CITY_RSO", "LA_COUNTY_RSO", "LOCAL_RSO")
        current = listing.get("current_rents")
        uplift = 0.0
        if current and rents and sum(current) > 0:
            uplift = max(0.0, sum(rents) / sum(current) - 1.0)
        model = IncomeApproach(
            unit_rents=(current if current else rents) or None,
            num_units=core.get("num_units") or 1,
            purchase_price=core.get("price"),
            vacancy_rate=expenses.get("vacancy_rate", 0.05 if not rso else 0.04),
            property_tax_rate=expenses.get("property_tax_rate", 0.0125),
            insurance_rate_of_value=ins_rate,
            management_pct=expenses.get("management_pct", 0.06),
            maintenance_per_unit_annual=expenses.get("maintenance_per_unit_annual", 1_200.0),
            reserves_per_unit_annual=expenses.get("reserves_per_unit_annual", 350.0),
            utilities_owner_paid_annual=expenses.get("utilities_owner_paid_annual", 0.0),
            other_fixed_annual=expenses.get("other_fixed_annual", 0.0),
            rso_fees_per_unit_annual=expenses.get("rso_fees_per_unit_annual", 90.0 if rso else 0.0),
            stabilized_rent_uplift=uplift,
            beds=core.get("beds"), baths=core.get("baths"), sqft=core.get("sqft"),
            rent_detail=rental_profile["rent_summary"],
        )
        out = model.summary()
        out["rent_growth_assumption"] = regulatory["summary"]["underwriting_rent_growth"]
        if listing.get("listed_noi"):
            out["listed_noi"] = listing["listed_noi"]
            if out.get("noi"):
                out["listed_vs_underwritten_noi_gap"] = round(out["noi"] - listing["listed_noi"], 2)
        return out

    # ------------------------------------------------------------------
    # 6. Cap rate
    # ------------------------------------------------------------------

    def _build_cap_rate_profile(self, core, jurisdiction):
        return CapRateModel(
            property_type=core.get("property_type"),
            submarket_class=jurisdiction.get("submarket_class", "stable"),
            risk_score=jurisdiction.get("risk_score"),
            is_rent_controlled=bool(jurisdiction.get("is_rent_controlled", False)),
        ).summary()

    # ------------------------------------------------------------------
    # 7. Financing
    # ------------------------------------------------------------------

    def _build_financing_profile(self, income_profile, purchase_price, financing):
        noi = income_profile.get("noi_stabilized") if financing.get("underwrite_stabilized") \
            else income_profile.get("noi")
        if not noi or not purchase_price:
            return {"inputs": financing, "note": "Missing NOI or purchase price; DSCR not computed.",
                    "meets_min_dscr": None}
        return DSCRLoanModel(
            noi=noi, purchase_price=purchase_price,
            interest_rate=financing.get("interest_rate", 0.0725),
            amort_years=financing.get("amort_years", 30),
            min_dscr=financing.get("min_dscr", 1.20),
            max_ltv=financing.get("max_ltv", 0.75),
        ).summary()

    @staticmethod
    def _cash_on_cash(income, financing, price) -> Optional[float]:
        noi, ads = income.get("noi"), financing.get("annual_debt_service")
        loan = financing.get("final_loan_amount")
        if noi is None or ads is None or not price or loan is None:
            return None
        equity = price - loan + price * 0.02   # closing costs
        return round((noi - ads) / equity, 4) if equity > 0 else None

    # ------------------------------------------------------------------
    # 8. Valuation
    # ------------------------------------------------------------------

    def _build_valuation_profile(self, income_profile, cap_rate_profile, purchase_price):
        noi = income_profile.get("noi")
        noi_stab = income_profile.get("noi_stabilized") or noi
        cap = cap_rate_profile.get("final_cap_rate")
        as_is = round(noi / cap, 2) if (noi and cap) else None
        stabilized = round(noi_stab / cap, 2) if (noi_stab and cap) else None
        gap = round(as_is - purchase_price, 2) if (as_is and purchase_price) else None
        return {
            "purchase_price": purchase_price,
            "as_is_value": as_is,
            "stabilized_value": stabilized,
            "income_value_gap": gap,
            "income_value_gap_pct": round(gap / purchase_price, 4) if (gap is not None and purchase_price) else None,
        }

    # ------------------------------------------------------------------
    # 9. Sales comparison
    # ------------------------------------------------------------------

    def _run_sales_comparison(self, core: Dict, sales_comps: List[Dict]) -> Dict:
        try:
            subject = dict(core)
            subject["property_type"] = core.get("property_type")
            summary = SalesCompModel(subject=subject, comps=sales_comps).summary()
            summary["success"] = True
            return summary
        except Exception as e:
            return {"success": False, "error": f"Sales comparison failed: {e}"}

    # ------------------------------------------------------------------
    # 10. House hack
    # ------------------------------------------------------------------

    def _build_house_hack(self, core, rental_profile, config, regulatory, warnings):
        hh = config.get("house_hack")
        units = int(core.get("num_units") or 1)
        if not hh or units > 4:
            return None
        # Tenants in place stay at in-place rent (RSO or not); owner's unit is valued at market.
        rents = list(rental_profile["unit_rents_monthly"])
        current = config.get("subject", {}).get("current_rents")
        if current and len(current) == units and len(rents) == units:
            idx = int(hh.get("owner_unit_index", 0))
            rents = [rents[k] if k == idx else float(current[k]) for k in range(units)]
        if len(rents) != units:
            if rents:
                rents = [sum(rents) / len(rents)] * units
            else:
                warnings.append("House-hack skipped: no per-unit rents.")
                return None
        ins = {f["key"]: f for f in regulatory["findings"]}.get("insurance", {}).get("numbers", {})
        ins_rate = (ins.get("insurance_rate_of_value_low", 0.004) + ins.get("insurance_rate_of_value_high", 0.005)) / 2
        try:
            return analyze_house_hack(HouseHackInputs(
                purchase_price=float(core["price"]), num_units=units, unit_rents=rents,
                owner_unit_index=int(hh.get("owner_unit_index", 0)),
                interest_rate=float(hh.get("interest_rate", 0.0675)),
                loan_program=hh.get("loan_program", "fha"),
                down_payment_pct=hh.get("down_payment_pct"),
                property_tax_rate=float(hh.get("property_tax_rate", 0.0125)),
                insurance_annual=hh.get("insurance_annual") or float(core["price"]) * ins_rate,
                hoa_monthly=float(hh.get("hoa_monthly", 0.0)),
                current_rent_paid=hh.get("current_rent_paid"),
            ))
        except ValueError as e:
            warnings.append(f"House-hack skipped: {e}")
            return None
