"""
report_generator.py

Builds HTML and optional PDF reports from a full appraisal dict.

- build_html_report(appraisal) -> str HTML
- build_pdf_report(html, output_path) -> str path (requires WeasyPrint)

If WeasyPrint is not installed, PDF generation will raise a clear error.
"""

from typing import Dict, Any, Optional

# Optional PDF library
try:
    from weasyprint import HTML  # type: ignore
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


def _safe_get(d: Dict[str, Any], path: str, default: Any = "") -> Any:
    """
    Utility to safely pull nested keys using 'a.b.c' style paths.
    """
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def build_html_report(appraisal: Dict[str, Any]) -> str:
    """
    Build a single-page HTML report summarizing:

    - Subject details
    - Income / NOI
    - Cap rate assumptions
    - Valuation (as-is / stabilized)
    - Sales comparison
    - Market confidence
    - Financing / DSCR
    - Recommendation
    - Narrative (full text)
    """

    subject = appraisal.get("subject", {}) or {}
    listing = subject.get("listing_core", {}) or {}
    narrative = appraisal.get("narrative", {}) or {}
    recommendation = appraisal.get("recommendation", {}) or {}
    income = appraisal.get("income", {}) or {}
    cap_rate = appraisal.get("cap_rate", {}) or {}
    valuation = appraisal.get("valuation", {}) or {}
    financing = appraisal.get("financing", {}) or {}
    sales_comp = appraisal.get("sales_comparison", {}) or {}
    market_conf = recommendation.get("market_confidence", {}) or {}

    addr = subject.get("address_normalized") or subject.get("address_raw") or "N/A"
    price = listing.get("price")
    price_str = f"${price:,.0f}" if isinstance(price, (int, float)) else "N/A"

    # Recommendation
    final_rec = recommendation.get("final_recommendation", "N/A")
    final_score = recommendation.get("final_score", "N/A")

    # HTML document
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Appraisal Report - {addr}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            margin: 24px;
            color: #222;
            line-height: 1.5;
        }}
        h1, h2, h3 {{
            margin-bottom: 4px;
        }}
        h1 {{
            font-size: 24px;
            margin-bottom: 8px;
        }}
        h2 {{
            font-size: 18px;
            margin-top: 20px;
        }}
        h3 {{
            font-size: 15px;
            margin-top: 14px;
        }}
        .header-bar {{
            padding: 12px 16px;
            background: #111;
            color: #f5f5f5;
            border-radius: 6px;
            margin-bottom: 16px;
        }}
        .section {{
            margin-bottom: 18px;
            padding: 12px 14px;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }}
        .badge-buy {{
            background: #0b8457;
            color: #fff;
        }}
        .badge-watch {{
            background: #e0a800;
            color: #111;
        }}
        .badge-pass {{
            background: #b00020;
            color: #fff;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 6px;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 6px 8px;
            text-align: left;
        }}
        th {{
            background: #f4f4f4;
            font-weight: 600;
        }}
        .muted {{
            color: #777;
            font-size: 12px;
        }}
        .mono {{
            font-family: "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }}
        pre {{
            white-space: pre-wrap;
            background: #fafafa;
            border-radius: 4px;
            padding: 10px;
            border: 1px solid #eee;
            font-size: 13px;
        }}
    </style>
</head>
<body>

<div class="header-bar">
    <h1>Appraisal Report</h1>
    <div>{addr}</div>
    <div class="muted">Listing Price: <span class="mono">{price_str}</span></div>
</div>

<div class="section">
    <h2>Executive Summary
"""

    # Recommendation badge
    badge_class = "badge"
    if isinstance(final_rec, str):
        if final_rec.upper() == "BUY":
            badge_class += " badge-buy"
        elif final_rec.upper() == "WATCH":
            badge_class += " badge-watch"
        elif final_rec.upper() == "PASS":
            badge_class += " badge-pass"

    html += f"""        <div>
            Final Recommendation:
            <span class="{badge_class}">{final_rec}</span>
            <span class="muted">Score: {final_score}</span>
        </div>
"""

    html += """</div>

<div class="section">
    <h2>Subject Property</h2>
    <table>
        <tr>
            <th>Address</th>
            <td>{addr}</td>
        </tr>
        <tr>
            <th>Property Type</th>
            <td>{prop_type}</td>
        </tr>
        <tr>
            <th>Beds / Baths</th>
            <td>{beds} / {baths}</td>
        </tr>
        <tr>
            <th>Building SF</th>
            <td>{sqft}</td>
        </tr>
        <tr>
            <th>Lot Size (SF)</th>
            <td>{lot_size}</td>
        </tr>
        <tr>
            <th>Year Built</th>
            <td>{year_built}</td>
        </tr>
        <tr>
            <th>Listing Price</th>
            <td>{price_str}</td>
        </tr>
    </table>
</div>
""".format(
        addr=addr,
        prop_type=listing.get("property_type_raw", "N/A"),
        beds=listing.get("beds", "N/A"),
        baths=listing.get("baths", "N/A"),
        sqft=listing.get("sqft", "N/A"),
        lot_size=listing.get("lot_size", "N/A"),
        year_built=listing.get("year_built", "N/A"),
        price_str=price_str,
    )

    # Income / NOI
    html += f"""
<div class="section">
    <h2>Income Approach</h2>
    <table>
        <tr><th>Gross Scheduled Rent (Annual)</th><td>${income.get("gross_scheduled_rent_annual", "N/A"):,.0f}</td></tr>
        <tr><th>Effective Gross Income (Annual)</th><td>${income.get("effective_gross_income_annual", "N/A"):,.0f}</td></tr>
        <tr><th>Operating Expenses (Annual)</th><td>${income.get("operating_expenses_annual", "N/A"):,.0f}</td></tr>
        <tr><th>NOI (Annual)</th><td>${income.get("noi", "N/A"):,.0f}</td></tr>
        <tr><th>Stabilized NOI</th><td>${income.get("noi_stabilized", "N/A"):,.0f}</td></tr>
    </table>
</div>
"""

    # Cap rate / valuation
    html += f"""
<div class="section">
    <h2>Cap Rate & Valuation</h2>
    <table>
        <tr><th>Base Cap Rate</th><td>{cap_rate.get("base_cap_rate", "N/A")}</td></tr>
        <tr><th>Risk Adjustment</th><td>{cap_rate.get("risk_adjustment", "N/A")}</td></tr>
        <tr><th>Final Cap Rate</th><td>{cap_rate.get("final_cap_rate", "N/A")}</td></tr>
        <tr><th>As-Is Value</th><td>${valuation.get("as_is_value", "N/A"):,.0f}</td></tr>
        <tr><th>Stabilized Value</th><td>${valuation.get("stabilized_value", "N/A"):,.0f}</td></tr>
    </table>
</div>
"""

    # Sales comparison / market confidence
    html += """
<div class="section">
    <h2>Sales Comparison & Market Confidence</h2>
    <table>
        <tr><th>Sales Comparison Active</th><td>{sales_active}</td></tr>
        <tr><th>Sales Rating</th><td>{sales_rating}</td></tr>
        <tr><th>Median Comp Value</th><td>{median_comp}</td></tr>
        <tr><th>Market Confidence Level</th><td>{mc_level}</td></tr>
        <tr><th>Market Confidence Score</th><td>{mc_score}</td></tr>
    </table>
    <div class="muted" style="margin-top:6px;">
        Sales comparison and confidence metrics are heuristic and should be benchmarked against professional appraisal.
    </div>
</div>
""".format(
        sales_active=str(sales_comp.get("success", False)),
        sales_rating=_safe_get(sales_comp, "rating", "N/A"),
        median_comp=f"${_safe_get(sales_comp, 'median_value', 0):,.0f}"
        if isinstance(_safe_get(sales_comp, "median_value", None), (int, float))
        else "N/A",
        mc_level=market_conf.get("level", "unknown"),
        mc_score=market_conf.get("score", "N/A"),
    )

    # Financing / DSCR
    html += f"""
<div class="section">
    <h2>Financing & DSCR</h2>
    <table>
        <tr><th>Meets Minimum DSCR</th><td>{financing.get("meets_min_dscr", 'N/A')}</td></tr>
        <tr><th>Max Loan Amount</th><td>${financing.get("max_loan_amount", 0):,.0f}</td></tr>
        <tr><th>Max Supported Price (DSCR)</th><td>${financing.get("max_supported_price", 0):,.0f}</td></tr>
    </table>
</div>
"""

    # Narrative
    full_text = narrative.get("full_text", "")
    html += f"""
<div class="section">
    <h2>Narrative Summary</h2>
    <pre>{full_text}</pre>
</div>
"""

    html += """
</body>
</html>
"""
    return html


def build_pdf_report(html: str, output_path: str = "appraisal_report.pdf") -> str:
    """
    Convert HTML string to PDF at the provided path.

    Requires WeasyPrint to be installed:
        pip install weasyprint

    Returns:
        output_path (for convenience)
    """
    if not HAS_WEASYPRINT:
        raise RuntimeError(
            "WeasyPrint is not installed. Install via 'pip install weasyprint' "
            "to enable PDF report generation."
        )

    HTML(string=html).write_pdf(output_path)
    return output_path
