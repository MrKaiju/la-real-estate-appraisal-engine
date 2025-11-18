from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from engine.appraiser_engine import AppraiserEngine
from api.schemas import AppraisalRequest, AppraisalResponse


app = FastAPI(
    title="Real Estate Appraiser Engine API",
    description="HTTP API wrapper around the AppraiserEngine for automated real estate valuation.",
    version="0.1.0",
)

# Optional: enable CORS so you can call this API from a browser UI later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can tighten this to specific domains later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single engine instance for all requests
engine = AppraiserEngine()


@app.get("/health", tags=["system"])
def health_check() -> Dict[str, Any]:
    """
    Simple health check endpoint.
    """
    return {"status": "ok", "message": "Appraiser Engine API is running."}


@app.post("/appraise", response_model=AppraisalResponse, tags=["appraisal"])
def run_appraisal(payload: AppraisalRequest) -> AppraisalResponse:
    """
    Run a full appraisal based on the provided configuration.

    The payload is transformed into the config dict expected by AppraiserEngine.
    """
    try:
        # Convert Pydantic model into a plain dict
        request_dict = payload.dict()

        # Build config for AppraiserEngine.
        # We mostly pass through the same keys that the engine expects.
        config: Dict[str, Any] = {
            "primary_url": request_dict.get("primary_url"),
            "rental_apartments_url": request_dict.get("rental_apartments_url"),
            "apn": request_dict.get("apn"),
            "assessor_html": request_dict.get("assessor_html"),
            "zoning_code": request_dict.get("zoning_code"),
            "zimas_html": request_dict.get("zimas_html"),
        }

        # Optional nested configs
        if request_dict.get("manual_rent_comps"):
            config["manual_rent_comps"] = request_dict["manual_rent_comps"]

        if request_dict.get("financing"):
            config["financing"] = request_dict["financing"]

        if request_dict.get("jurisdiction"):
            config["jurisdiction"] = request_dict["jurisdiction"]

        if request_dict.get("sales_comps"):
            config["sales_comps"] = request_dict["sales_comps"]

        if request_dict.get("report_options"):
            config["report_options"] = request_dict["report_options"]

        # Run engine
        result = engine.run_full_appraisal(config)

        # If the engine signals failure, translate to HTTP 400
        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "Appraisal failed"))

        # Wrap in AppraisalResponse
        return AppraisalResponse(success=True, data=result)

    except HTTPException:
        # Re-raise explicit HTTP errors
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(status_code=500, detail=str(e))
