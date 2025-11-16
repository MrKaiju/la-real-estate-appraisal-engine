"""
report_generator.py

Generates a markdown-formatted investment-style appraisal report
using the standard 9-section structure:

1. Property Snapshot
2. Zoning & Legal Use
3. Rent Control & Regulatory Factors
4. Comparable Sales Summary
5. Income Approach & Cap Rate
6. Financing & Monthly Payment
7. Cash Flow & Return Scenarios
8. Risks & Red Flags
9. Strategic Recommendation
"""

from typing import Dict, Optional


def generate_markdown_report(
    subject: Dict,
    zoning: Dict,
    hazards: Dict,
    comps_summary: Optional[Dict],
    income_summary: Optional[Dict],
    underwriting_summary: Optional[Dict]
) -> str:
    """
    subject: {
      "address": str,
      "price": float,
      "beds": ...,
      "baths": ...,
      "sqft": ...,
      "lot_sqft": ...,
      "year_built": ...
    }

    zoning: zoning_check.summary()
    hazards: hazard_overlay.summary()
    comps_summary: valuation_range + key comp stats
    income_summary: {gsr, noi, cap_rate, value_estimate}
    underwriting_summary: {dscr, coc_return, annual_cash_flow, annual_debt_service, monthly_pi}
    """

    lines = []

    # 1. Property Snapshot
    lines.append("# 1. Property Snapshot")
    lines.append(f"**Address:** {subject.get('address')}")
    price = subject.get("price")
    if price:
        try:
            price = float(price)
            lines.append(f"**Asking Price:** ${price:,.0f}")
        except Exception:
            lines.append(f"**Asking Price:** {price}")
    else:
        lines.append("**Asking Price:** N/A")
    lines.append(f"**Beds/Baths:** {subject.get('beds')} / {subject.get('baths')}")
    lines.append(f"**Building SF:** {subject.get('sqft')} | **Lot SF:** {subject.get('lot_sqft')}")
    lines.append(f"**Year Built:** {subject.get('year_built')}")
    lines.append("")

    # 2. Zoning & Legal Use
    lines.append("## 2. Zoning & Legal Use")
    lines.append(f"- Zoning Code: {zoning.get('zoning_code')}")
    lines.append(f"- SFR: {zoning.get('is_sfr')} | Multifamily: {zoning.get('is_multifamily')} | Commercial: {zoning.get('is_commercial')}")
    lines.append("")

    # 3. Rent Control & Regulatory Factors
    lines.append("## 3. Rent Control & Regulatory Factors")
    lines.append("- RSO / rent control analysis to be added based on jurisdiction, year built, and local ordinances.")
    lines.append("")

    # 4. Comparable Sales Summary
    lines.append("## 4. Comparable Sales Summary")
    if comps_summary:
        lines.append(f"- Low Value: ${comps_summary.get('low_value'):,.0f}")
        lines.append(f"- Base Value: ${comps_summary.get('base_value'):,.0f}")
        lines.append(f"- High Value: ${comps_summary.get('high_value'):,.0f}")
    else:
        lines.append("- Comparable sales data unavailable or not yet modeled.")
    lines.append("")

    # 5. Income Approach & Cap Rate
    lines.append("## 5. Income Approach & Cap Rate")
    if income_summary:
        lines.append(f"- Gross Scheduled Rent (GSR): ${income_summary.get('gsr'):,.0f}")
        lines.append(f"- Net Operating Income (NOI): ${income_summary.get('noi'):,.0f}")
        cap_rate = income_summary.get("cap_rate")
        if cap_rate is not None:
            lines.append(f"- Implied Cap Rate: {cap_rate:.2%}")
        lines.append(f"- Income Approach Value Estimate: ${income_summary.get('value_estimate'):,.0f}")
    else:
        lines.append("- Income approach not calculated.")
    lines.append("")

    # 6. Financing & Monthly Payment
    lines.append("## 6. Financing & Monthly Payment")
    if underwriting_summary:
        ads = underwriting_summary.get("annual_debt_service")
        mpi = underwriting_summary.get("monthly_pi")
        if ads is not None:
            lines.append(f"- Annual Debt Service: ${ads:,.0f}")
        if mpi is not None:
            lines.append(f"- Monthly Principal & Interest (P&I): ${mpi:,.0f}")
    else:
        lines.append("- Financing scenario not modeled.")
    lines.append("")

    # 7. Cash Flow & Return Scenarios
    lines.append("## 7. Cash Flow & Return Scenarios")
    if underwriting_summary:
        dscr = underwriting_summary.get("dscr")
        annual_cf = underwriting_summary.get("annual_cash_flow")
        coc = underwriting_summary.get("coc_return")
        if dscr is not None:
            lines.append(f"- DSCR: {dscr:.2f}")
        if annual_cf is not None:
            lines.append(f"- Annual Cash Flow (Before Taxes): ${annual_cf:,.0f}")
        if coc is not None:
            lines.append(f"- Cash-on-Cash Return: {coc:.2%}")
    else:
        lines.append("- Return scenarios not calculated.")
    lines.append("")

    # 8. Risks & Red Flags
    lines.append("## 8. Risks & Red Flags")
    lines.append(f"- Hazard Summary: {hazards}")
    lines.append("- Confirm legal unit count, permits, and code compliance with city/county agencies.")
    lines.append("- Verify any non-conforming or unpermitted improvements with a qualified professional.")
    lines.append("")

    # 9. Strategic Recommendation
    lines.append("## 9. Strategic Recommendation")
    lines.append("- Provide a Buy / Watch / Pass recommendation here based on your risk tolerance, financing, and long-term strategy.")
    lines.append("")

    return "\n".join(lines)
