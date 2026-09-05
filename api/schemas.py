from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SubjectInput(BaseModel):
    """Structured property facts. This is the primary, scraper-free intake path."""
    address_full: Optional[str] = None
    city: Optional[str] = Field(None, description='e.g. "Los Angeles", "Glendale", "unincorporated"')
    zip: Optional[str] = None
    price: float = Field(..., gt=0, description="Asking or offer price")
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[float] = None
    lot_size: Optional[float] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = Field(None, description="sfr | condo | 2-4 | 5+ | mixed_use | retail | office | industrial")
    num_units: Optional[int] = Field(None, ge=1)
    zone: Optional[str] = Field(None, description='ZIMAS zone string, e.g. "R1-1", "RD1.5-1"')
    stories: Optional[int] = None
    wood_frame: Optional[bool] = None
    tuck_under_parking: Optional[bool] = None
    in_very_high_fire_hazard_zone: Optional[bool] = None
    owner_is_corporate: bool = False
    unit_rents: Optional[List[float]] = Field(None, description="Market rent per unit, monthly")
    current_rents: Optional[List[float]] = Field(None, description="In-place rent per unit, monthly")
    listed_noi: Optional[float] = None
    listed_cap_rate: Optional[float] = None
    apn: Optional[str] = Field(None, description="LA County APN, e.g. 5055-008-012; speeds up parcel lookup")
    lat: Optional[float] = None
    lon: Optional[float] = None


class ManualRentComp(BaseModel):
    beds: int
    baths: float
    sqft: Optional[int] = None
    rent: float
    source: Optional[str] = None


class SalesComp(BaseModel):
    price: float
    sqft: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    num_units: Optional[int] = None
    distance_miles: Optional[float] = None
    sale_date: Optional[str] = None
    property_type: Optional[str] = None
    condition: Optional[str] = None
    source: Optional[str] = None


class FinancingConfig(BaseModel):
    interest_rate: float = 0.0725
    amort_years: int = 30
    min_dscr: float = 1.20
    max_ltv: float = 0.75
    underwrite_stabilized: bool = False


class ExpenseOverrides(BaseModel):
    vacancy_rate: Optional[float] = None
    property_tax_rate: Optional[float] = None
    insurance_rate_of_value: Optional[float] = None
    management_pct: Optional[float] = None
    maintenance_per_unit_annual: Optional[float] = None
    reserves_per_unit_annual: Optional[float] = None
    utilities_owner_paid_annual: Optional[float] = None
    other_fixed_annual: Optional[float] = None
    rso_fees_per_unit_annual: Optional[float] = None


class JurisdictionConfig(BaseModel):
    is_rent_controlled: Optional[bool] = None
    jurisdiction: Optional[str] = None
    submarket_class: str = "stable"
    risk_score: Optional[float] = Field(None, ge=0, le=100, description="0-100, higher = more risk")
    risk_grade: Optional[str] = None


class HouseHackConfig(BaseModel):
    owner_unit_index: int = 0
    loan_program: str = "fha"
    interest_rate: float = 0.0675
    down_payment_pct: Optional[float] = None
    property_tax_rate: float = 0.0125
    insurance_annual: Optional[float] = None
    hoa_monthly: float = 0.0
    current_rent_paid: Optional[float] = None


class ExitConfig(BaseModel):
    exit_price: Optional[float] = None


class ReportOptions(BaseModel):
    generate_html: bool = False
    generate_pdf: bool = False
    pdf_output_path: str = "appraisal_report.pdf"


class AppraisalRequest(BaseModel):
    subject: Optional[SubjectInput] = None
    enrich: Optional[bool] = Field(None, description="Set false to skip parcel/GIS/RentCast enrichment")
    primary_url: Optional[str] = Field(None, description="Optional listing URL; structured subject is preferred")
    rental_apartments_url: Optional[str] = None
    manual_rent_comps: Optional[List[ManualRentComp]] = None
    apn: Optional[str] = None
    assessor_html: Optional[str] = None
    zoning_code: Optional[str] = None
    zimas_html: Optional[str] = None
    financing: Optional[FinancingConfig] = None
    expenses: Optional[ExpenseOverrides] = None
    jurisdiction: Optional[JurisdictionConfig] = None
    sales_comps: Optional[List[SalesComp]] = None
    house_hack: Optional[HouseHackConfig] = None
    exit: Optional[ExitConfig] = None
    report_options: Optional[ReportOptions] = None


class AppraisalResponse(BaseModel):
    success: bool
    data: Dict[str, Any]


class HouseHackRequest(BaseModel):
    purchase_price: float = Field(..., gt=0)
    num_units: int = Field(..., ge=1, le=4)
    unit_rents: List[float]
    owner_unit_index: int = 0
    interest_rate: float = 0.0675
    loan_program: str = "fha"
    down_payment_pct: Optional[float] = None
    property_tax_rate: float = 0.0125
    insurance_annual: Optional[float] = None
    hoa_monthly: float = 0.0
    current_rent_paid: Optional[float] = None


class RegulatoryRequest(BaseModel):
    city: Optional[str] = None
    year_built: Optional[int] = None
    num_units: Optional[int] = None
    property_type: Optional[str] = None
    zone: Optional[str] = None
    lot_sqft: Optional[float] = None
    stories: Optional[int] = None
    wood_frame: Optional[bool] = None
    tuck_under_parking: Optional[bool] = None
    owner_is_corporate: bool = False
    in_very_high_fire_hazard_zone: Optional[bool] = None
    purchase_price: Optional[float] = None
    exit_price: Optional[float] = None
