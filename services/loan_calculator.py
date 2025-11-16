import math

class LoanCalculator:
    """
    Standard mortgage amortization and investor underwriting model.
    """

    def __init__(self, loan_amount: float, interest_rate: float, years: int):
        self.principal = loan_amount
        self.rate = interest_rate / 12
        self.months = years * 12

    def monthly_payment(self):
        r = self.rate
        n = self.months
        p = self.principal

        if r == 0:
            return p / n
        
        payment = p * (r * (1 + r)**n) / ((1 + r)**n - 1)
        return payment

    def annual_debt_service(self):
        return self.monthly_payment() * 12
