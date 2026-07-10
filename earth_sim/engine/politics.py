import random

class PoliticalLegitimacy:
    def __init__(self, country):
        self.country = country
        self.procedural_legitimacy = 0.7
        self.performance_legitimacy = 0.7

    def update(self, gdp_growth):
        if self.country.government == "民主":
            self.procedural_legitimacy += random.uniform(-0.02, 0.02)
        else:
            self.procedural_legitimacy -= 0.01
        self.performance_legitimacy = 0.5 + gdp_growth * 2 + self.country.stability * 0.3
        self.performance_legitimacy = max(0, min(1, self.performance_legitimacy))