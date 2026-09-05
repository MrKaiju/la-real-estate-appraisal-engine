import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from engine.appraiser_engine import AppraiserEngine
from api.schemas import (
    AppraisalRequest, AppraisalResponse, HouseHackRequest, RegulatoryRequest,
)
from core import la_regulatory
from core.house_hack import HouseHackInputs, analyze as analyze_house_hack
from api.store import DealStore

app = FastAPI(
    title="LA Appraisal Engine API",
    description="Los Angeles-specific underwriting: income value, DSCR sizing, LA regulatory stack "
                "(RSO / AB 1482 / ULA / Prop 13 / soft-story / SB 9), and owner-occupant house-hack math.",
    version="0.2.0",
)

_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

engine = AppraiserEngine()
_store: Optional[DealStore] = None


def store() -> DealStore:
    global _store
    if _store is None:
        _store = DealStore()
    return _store


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> Optional[str]:
    """Write endpoints are open when API_KEY is unset (local dev) and gated when it is set."""
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Api-Key")
    return x_api_key


@app.get("/health", tags=["system"])
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok", "version": app.version,
        "rules_as_of": la_regulatory.RULES_AS_OF.isoformat(),
        "enrichment": os.getenv("LA_ENGINE_ENRICH", "1") != "0",
        "rentcast_configured": bool(os.getenv("RENTCAST_API_KEY")),
        "hud_configured": bool(os.getenv("HUD_USER_API_TOKEN")),
    }


@app.post("/appraise", response_model=AppraisalResponse, tags=["appraisal"])
def run_appraisal(payload: AppraisalRequest) -> AppraisalResponse:
    config = payload.model_dump(exclude_none=True)
    try:
        result = engine.run_full_appraisal(config)
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Engine error: {e}")
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Appraisal failed"))
    return AppraisalResponse(success=True, data=result)


@app.post("/appraise/report.html", response_class=HTMLResponse, tags=["appraisal"])
def run_appraisal_html(payload: AppraisalRequest) -> str:
    config = payload.model_dump(exclude_none=True)
    config["report_options"] = {"generate_html": True}
    result = engine.run_full_appraisal(config)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Appraisal failed"))
    return result["report_outputs"]["html"]


@app.post("/deals", tags=["deals"], status_code=201)
def save_deal(payload: AppraisalRequest, owner: Optional[str] = Query(default=None),
              _: Optional[str] = Depends(require_api_key)) -> Dict[str, Any]:
    """Run the appraisal and persist request + result. Returns the deal id and summary."""
    config = payload.model_dump(exclude_none=True)
    result = engine.run_full_appraisal(config)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Appraisal failed"))
    deal_id = store().save(payload.model_dump(exclude_none=True), result, owner=owner)
    return {"id": deal_id, "recommendation": result["recommendation"]["final_recommendation"],
            "regime": result["regulatory"]["summary"]["regime"]}


@app.get("/deals", tags=["deals"])
def list_deals(owner: Optional[str] = Query(default=None), limit: int = Query(default=50, le=200),
               _: Optional[str] = Depends(require_api_key)) -> List[Dict[str, Any]]:
    return store().list(owner=owner, limit=limit)


@app.get("/deals/{deal_id}", tags=["deals"])
def get_deal(deal_id: str, _: Optional[str] = Depends(require_api_key)) -> Dict[str, Any]:
    d = store().get(deal_id)
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    return d


@app.post("/house-hack", tags=["consumer"])
def house_hack(payload: HouseHackRequest) -> Dict[str, Any]:
    try:
        return analyze_house_hack(HouseHackInputs(**payload.model_dump()))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/regulatory", tags=["consumer"])
def regulatory(payload: RegulatoryRequest) -> Dict[str, Any]:
    d = payload.model_dump()
    price, exit_price = d.pop("purchase_price"), d.pop("exit_price")
    return la_regulatory.evaluate(la_regulatory.LASubject(**d), purchase_price=price, exit_price=exit_price)
