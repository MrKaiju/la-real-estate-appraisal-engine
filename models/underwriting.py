class Underwriting:
    """
    Computes DSCR, cash flow, CoC return, and feasibility.
    """

    def __init__(self, noi: float, annual_debt_service: float, cash_invested: float):
        self.noi = noi
        self.ads = annual_debt_service
        self.cash = cash_invested

    def dscr(self):
        if self.ads == 0:
            return None
        return self.noi / self.ads
    
    def annual_cash_flow(self):
        return self.noi - self.ads
    
    def coc_return(self):
        if self.cash == 0:
            return None
        return self.annual_cash_flow() / self.cash
