"""
reports/report_generator.py

Builds an HTML report (and optional PDF via WeasyPrint) from a full appraisal
dict. All values are None-safe and HTML-escaped.
"""

from html import escape
from typing import Dict, Any, Optional

try:
    from weasyprint import HTML  # type: ignore
    HAS_WEASYPRINT = True
except ImportError:  # pragma: no cover
    HAS_WEASYPRINT = False


def _m(v: Optional[float]) -> str:
    try:
        return f"${float(v):,.0f}" if v is not None else "n/a"
    except (TypeError, ValueError):
        return "n/a"


def _p(v: Optional[float], d: int = 2) -> str:
    try:
        return f"{float(v) * 100:.{d}f}%" if v is not None else "n/a"
    except (TypeError, ValueError):
        return "n/a"


def _s(v: Any) -> str:
    return escape("n/a" if v is None else str(v))


def _row(label: str, value: str) -> str:
    return f"<tr><th>{escape(label)}</th><td>{value}</td></tr>"


CSS = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1c1c1c;max-width:900px;margin:32px auto;padding:0 20px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:#555;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;width:42%;color:#444;font-weight:600;padding:5px 8px;background:#f6f6f6}td{padding:5px 8px;border-bottom:1px solid #eee}
.badge{display:inline-block;padding:3px 10px;border-radius:4px;font-weight:700;color:#fff}.buy{background:#1f7a3a}.watch{background:#b8860b}.pass{background:#9b2c2c}
.flag{padding:6px 10px;border-left:4px solid #999;margin:6px 0;font-size:13px;background:#fafafa}.risk{border-color:#9b2c2c}.opportunity{border-color:#1f7a3a}.caution{border-color:#b8860b}
pre{white-space:pre-wrap;font:13px/1.5 inherit;background:#fafafa;padding:12px;border:1px solid #eee}.muted{color:#777;font-size:12px}
"""


def build_html_report(a: Dict[str, Any]) -> str:
    subject = a.get("subject") or {}
    l = subject.get("listing_core") or {}
    rec = a.get("recommendation") or {}
    inc = a.get("income") or {}
    cap = a.get("cap_rate") or {}
    val = a.get("valuation") or {}
    fin = a.get("financing") or {}
    sc = a.get("sales_comparison") or {}
    mc = rec.get("market_confidence") or {}
    reg = a.get("regulatory") or {}
    hh = a.get("house_hack") or {}
    narrative = a.get("narrative") or {}

    final = (rec.get("final_recommendation") or "N/A").upper()
    badge = {"BUY": "buy", "WATCH": "watch", "PASS": "pass"}.get(final, "")

    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Appraisal Report</title><style>{CSS}</style></head><body>"]
    h.append(f"<h1>{_s(subject.get('address_raw') or 'Subject Property')}</h1>")
    h.append(f"<div>Asking {_m(l.get('price'))} &nbsp;·&nbsp; <span class='badge {badge}'>{_s(final)}</span> "
             f"<span class='muted'>score {_s(rec.get('final_score'))}/5 · engine {_s(a.get('engine_version'))}</span></div>")

    h.append("<h2>Subject</h2><table>")
    h += [_row("Property type", _s(l.get("property_type"))), _row("Units", _s(l.get("num_units"))),
          _row("Beds / Baths", f"{_s(l.get('beds'))} / {_s(l.get('baths'))}"),
          _row("Building SF", _s(l.get("sqft"))), _row("Lot SF", _s(l.get("lot_size"))),
          _row("Year built", _s(l.get("year_built"))), _row("Zone", _s(l.get("zone")))]
    h.append("</table>")

    if reg.get("findings"):
        h.append("<h2>LA Regulatory Stack</h2>")
        for f in reg["findings"]:
            if f.get("applies") is False and f.get("severity") == "info":
                continue
            h.append(f"<div class='flag {escape(f.get('severity', ''))}'><b>{_s(f.get('headline'))}</b><br>"
                     f"{_s(f.get('detail'))}<br><span class='muted'>Basis: {_s(f.get('basis'))}</span></div>")

    h.append("<h2>Income Approach</h2><table>")
    opex = inc.get("operating_expenses") or {}
    h += [_row("Gross potential income", _m(inc.get("gross_potential_income"))),
          _row("Vacancy", _p(inc.get("vacancy_rate"), 0)),
          _row("Effective gross income", _m(inc.get("effective_gross_income")))]
    for k, v in opex.items():
        if v:
            h.append(_row("   " + k.replace("_", " ").title(), _m(v)))
    h += [_row("Total operating expenses", f"{_m(inc.get('operating_expenses_annual'))} ({_p(inc.get('expense_ratio'), 0)})"),
          _row("NOI", _m(inc.get("noi"))), _row("Stabilized NOI", _m(inc.get("noi_stabilized"))),
          _row("Going-in cap rate", _p(inc.get("going_in_cap_rate"))), _row("GRM", _s(inc.get("grm"))),
          _row("Cash-on-cash (yr 1)", _p(inc.get("cash_on_cash"), 1))]
    h.append("</table>")

    h.append("<h2>Cap Rate &amp; Value</h2><table>")
    h += [_row("Base market cap", _p(cap.get("base_cap_rate"))), _row("Risk adjustment", _p(cap.get("risk_adjustment"))),
          _row("Rent-control adjustment", _p(cap.get("rent_control_adjustment"))),
          _row("Reconciled cap rate", _p(cap.get("final_cap_rate"))),
          _row("As-is income value", _m(val.get("as_is_value"))), _row("Stabilized value", _m(val.get("stabilized_value"))),
          _row("Gap vs asking", f"{_m(val.get('income_value_gap'))} ({_p(val.get('income_value_gap_pct'), 1)})")]
    h.append("</table>")

    h.append("<h2>Financing (DSCR)</h2><table>")
    h += [_row("Meets min DSCR at max LTV", _s(fin.get("meets_min_dscr"))),
          _row("Lender-supported loan", f"{_m(fin.get('final_loan_amount'))} ({_s(fin.get('binding_constraint'))} bound)"),
          _row("Equity required", _m(fin.get("equity_required"))), _row("Monthly P&amp;I", _m(fin.get("monthly_payment"))),
          _row("DSCR at max LTV", _s(fin.get("dscr_at_max_ltv_loan"))),
          _row("Max DSCR-supported price", _m(fin.get("max_supported_price")))]
    h.append("</table>")

    if hh:
        m, lo, v = hh.get("monthly", {}), hh.get("loan", {}), hh.get("verdict", {})
        h.append("<h2>House-Hack (Owner-Occupant)</h2><table>")
        h += [_row("Program / down", f"{_s(lo.get('program'))} / {_p(lo.get('down_payment_pct'), 1)}"),
              _row("Cash to close (est.)", _m(lo.get("cash_to_close_estimate"))),
              _row("Total monthly payment", _m(m.get("pitia"))),
              _row("Rent from other units (net of vacancy)", _m(m.get("effective_rent_other_units"))),
              _row("Net housing cost", _m(m.get("net_housing_cost"))),
              _row("Same unit would rent for", _m(m.get("owner_unit_market_rent"))),
              _row("Cash flow if you move out", _m(m.get("cash_flow_if_owner_moves_out"))),
              _row("FHA self-sufficiency", _s(hh.get("lender_tests", {}).get("self_sufficiency_test_pass"))),
              _row("Verdict", _s(v.get("label")))]
        h.append("</table>")

    h.append("<h2>Sales Comparison &amp; Confidence</h2><table>")
    comp = (rec.get("components") or {}).get("sales_comparison") or {}
    ve = sc.get("value_estimates") or {}
    h += [_row("Comps used", _s(len(sc.get("normalized_comps") or []) if sc else 0)),
          _row("Comp-derived value", _m(ve.get("base_value"))),
          _row("vs asking", f"{_p(comp.get('pct_diff'), 1)} ({_s(comp.get('rating'))})"),
          _row("Market confidence", f"{_s(mc.get('level'))} ({_s(mc.get('score'))})")]
    h.append("</table>")

    h.append("<h2>Narrative</h2>")
    h.append(f"<pre>{escape(narrative.get('full_text') or '')}</pre>")
    if a.get("warnings"):
        h.append("<h2>Warnings</h2><ul>" + "".join(f"<li>{_s(w)}</li>" for w in a["warnings"]) + "</ul>")
    h.append("<p class='muted'>Automated underwriting output. Not an appraisal under USPAP and not legal, tax or "
             "investment advice. Verify all regulatory findings with ZIMAS, LAHD and the LA County Assessor.</p>")
    h.append("</body></html>")
    return "\n".join(h)


def build_pdf_report(html: str, output_path: str = "appraisal_report.pdf") -> str:
    if not HAS_WEASYPRINT:
        raise RuntimeError("WeasyPrint is not installed. Install with: pip install 'la-appraisal-engine[pdf]'")
    HTML(string=html).write_pdf(output_path)
    return output_path
