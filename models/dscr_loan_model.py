"""
dscr_loan_model.py

Debt Service Coverage Ratio (DSCR) loan sizing model.

This model uses:
- Net Operating Income (NOI)
- Minimum DSCR constraint (e.g., 1.20x)
- Maximum LTV (e.g., 75% of value/purchase price)
- Interest rate and amortization term

to determine:
- Maximum loan amount supported by DSCR
- Maximum loan amount allowed by LTV
- Binding (final) loan amount
- Monthly P&I payment
- Annual debt service
- Actual DSCR at that loan amount
"""

from typing import Optional, Dict
import math


class DSCRLoanModel:
    """
    Parameters:
        noi: Net Operating Income (annual)
        purchase_price: purchase price or property value
        interest_rate: annual interest rate (e.g., 0.065 for 6.5%)
        amort_years: amortization term in years (e.g., 30 for 30 years)
        min_dscr: minimum DSCR required by the lender (e.g., 1.20)
        max_ltv: maximum loan-to-value (e.g., 0.75 for 75%)

    Example:
        model = DSCRLoanModel(
            noi=120_000,
            purchase_price=1_800_000,
            interest_rate=0.065,
            amort_years=30,
            min_dscr=1.20,
            max_ltv=0.75
        )
        result = model.summary()

        -> {
            "loan_by_dscr": ...,
            "loan_by_ltv": ...,
            "final_loan_amount": ...,
            "monthly_payment": ...,
            "annual_debt_service": ...,
            "dscr_at_final_loan": ...,
            ...
        }
    """

    def __init__(
        self,
        noi: float,
        purchase_price: float,
        interest_rate: float,
        amort_years: int,
        min_dscr: float = 1.20,
        max_ltv: float = 0.75,
    ):
        self.noi = noi
        self.purchase_price = purchase_price
        self.interest_rate = interest_rate
        self.amort_years = amort_years
        self.min_dscr = min_dscr
        self.max_ltv = max_ltv

    # ----------------------------------------------------------
    # Core loan math helpers
    # ----------------------------------------------------------

    def _monthly_rate(self) -> float:
        return self.interest_rate / 12.0

    def _num_payments(self) -> int:
        return self.amort_years * 12

    def _payment_for_loan(self, loan_amount: float) -> float:
        """
        Standard mortgage payment formula (P&I only).
        """
        r = self._monthly_rate()
        n = self._num_payments()

        if r <= 0:
            # Edge case: zero interest
            return loan_amount / n

        # Monthly payment formula: P = L * [r (1+r)^n] / [(1+r)^n - 1]
        numerator = loan_amount * r * (1 + r) ** n
        denominator = (1 + r) ** n - 1
        return numerator / denominator

    def _loan_from_annual_debt_service(self, annual_debt_service: float) -> float:
        """
        Inverse of _payment_for_loan, solving for loan amount from a target
        annual debt service.
        """
        monthly_payment = annual_debt_service / 12.0
        r = self._monthly_rate()
        n = self._num_payments()

        if r <= 0:
            # Zero interest edge case
            return monthly_payment * n

        # Rearranged payment formula to solve for L:
        # L = P * [(1+r)^n - 1] / [r (1+r)^n]
        factor = ((1 + r) ** n - 1) / (r * (1 + r) ** n)
        return monthly_payment * factor

    # ----------------------------------------------------------
    # DSCR-driven loan sizing
    # ----------------------------------------------------------

    def loan_by_dscr(self) -> Optional[float]:
        """
        Maximum loan supported by NOI and minimum DSCR requirement.
        """
        if self.min_dscr <= 0 or self.noi <= 0:
            return None

        # Allowable annual debt service
        max_annual_debt_service = self.noi / self.min_dscr
        return self._loan_from_annual_debt_service(max_annual_debt_service)

    def loan_by_ltv(self) -> Optional[float]:
        """
        Maximum loan allowed by LTV constraint.
        """
        if self.max_ltv <= 0 or self.purchase_price <= 0:
            return None

        return self.purchase_price * self.max_ltv

    # ----------------------------------------------------------
    # Combined loan sizing
    # ----------------------------------------------------------

    def final_loan_amount(self) -> Optional[float]:
        """
        Returns the binding loan amount:
        - The lower of loan_by_dscr and loan_by_ltv
        """
        l_dscr = self.loan_by_dscr()
        l_ltv = self.loan_by_ltv()

        if l_dscr is None and l_ltv is None:
            return None
        if l_dscr is None:
            return l_ltv
        if l_ltv is None:
            return l_dscr

        return min(l_dscr, l_ltv)

    def metrics_for_loan(self, loan_amount: float) -> Dict:
        """
        Given a loan amount, compute:
        - Monthly payment (P&I)
        - Annual debt service
        - DSCR
        - LTV
        """
        monthly_payment = self._payment_for_loan(loan_amount)
        annual_debt_service = monthly_payment * 12.0

        dscr = None
        if annual_debt_service > 0:
            dscr = self.noi / annual_debt_service

        ltv = None
        if self.purchase_price > 0:
            ltv = loan_amount / self.purchase_price

        return {
            "loan_amount": round(loan_amount, 2),
            "monthly_payment": round(monthly_payment, 2),
            "annual_debt_service": round(annual_debt_service, 2),
            "dscr": round(dscr, 3) if dscr is not None else None,
            "ltv": round(ltv, 3) if ltv is not None else None,
        }

    # ----------------------------------------------------------
    # Public summary
    # ----------------------------------------------------------

    def summary(self) -> Dict:
        """
        High-level summary for underwriting & reporting.
        """

        loan_dscr = self.loan_by_dscr()
        loan_ltv = self.loan_by_ltv()
        final_loan = self.final_loan_amount()

        metrics = self.metrics_for_loan(final_loan) if final_loan else None

        return {
            "inputs": {
                "noi": self.noi,
                "purchase_price": self.purchase_price,
                "interest_rate": self.interest_rate,
                "amort_years": self.amort_years,
                "min_dscr": self.min_dscr,
                "max_ltv": self.max_ltv,
            },
            "loan_by_dscr": round(loan_dscr, 2) if loan_dscr is not None else None,
            "loan_by_ltv": round(loan_ltv, 2) if loan_ltv is not None else None,
            "final_loan_amount": metrics["loan_amount"] if metrics else None,
            "monthly_payment": metrics["monthly_payment"] if metrics else None,
            "annual_debt_service": metrics["annual_debt_service"] if metrics else None,
            "dscr_at_final_loan": metrics["dscr"] if metrics else None,
            "ltv_at_final_loan": metrics["ltv"] if metrics else None,
        }
