class IncomeApproach:
    """
    Computes GSR, vacancy, OPEX, and NOI for investment valuation.
    """

    def __init__(
        self,
        monthly_market_rent: float,
        num_units: int,
        vacancy_rate: float = 0.05,
        operating_expense_ratio: float = 0.35
    ):
        self.rent = monthly_market_rent
        self.units = num_units
        self.vacancy_rate = vacancy_rate
        self.op_ex_ratio = operating_expense_ratio

    def gsr(self):
        return self.rent * self.units * 12
    
    def vacancy_loss(self):
        return self.gsr() * self.vacancy_rate
    
    def effective_gross_income(self):
        return self.gsr() - self.vacancy_loss()
    
    def operating_expenses(self):
        return self.effective_gross_income() * self.op_ex_ratio
    
    def noi(self):
        return self.effective_gross_income() - self.operating_expenses()
    
    def cap_rate_value(self, cap_rate: float):
        if cap_rate == 0:
            return None
        return self.noi() / cap_rate
