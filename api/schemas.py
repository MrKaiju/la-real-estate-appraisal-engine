from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ManualRentComp(BaseModel):
    beds: int
    baths: int
    sqft: int
    rent: float
    source: Optional[str] = None


class SalesComp(BaseModel):
    price: float
    sqft: int
    beds: Optional[int] = None
    baths: Optional[int] = None
    distance_miles: Optional[float] = None
    # Add more fields if your SalesCompModel uses them


class FinancingConfig(BaseModel):
    interest_rate: Optional[float] = 0.0675
    amort_years: Optional[int] = 30
    min_dscr: Optional[float] = 1.20
    max_ltv: Optional[float] = 0.75


class JurisdictionConfig(BaseModel):
    is_rent_controlled: Optional[bool] = None
    jurisdiction: Optional[str] = None
    submarket_class: Optional[str] = "stable"
    risk_score: Optional[float] = None
    risk_grade: Optional[str] = None


class ReportOptions(BaseModel):
    generate_html: Optional[bool] = False
    generate_pdf: Optional[bool] = False
    pdf_output_path: Optional[str] = "appraisal_report.pdf"


class AppraisalRequest(BaseModel):
    primary_url: str

    # Optional auxiliary fields
    rental_apartments_url: Optional[str] = None
    manual_rent_comps: Optional[List[ManualRentComp]] = None

    apn: Optional[str] = None
    assessor_html: Optional[str] = None
    zoning_code: Optional[str] = None
    zimas_html: Optional[str] = None

    financing: Optional[FinancingConfig] = None
    jurisdiction: Optional[JurisdictionConfig] = None
    sales_comps: Optional[List[SalesComp]] = None

    report_options: Optional[ReportOptions] = None


class AppraisalResponse(BaseModel):
    """
    Very loose response model; we just wrap the engine result.
    You can tighten this later if you want strict typing.
    """
    success: bool
    data: Dict[str, Any]

Add FastAPI request/response schemas
