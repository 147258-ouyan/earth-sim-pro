import random

class CentralBank:
    def __init__(self, country):
        self.country = country
        self.base_interest_rate = 0.03
        self.money_supply = country.gdp * 1.5
        self.inflation = 0.02

    def update(self):
        prev_gdp = getattr(self.country, '_prev_gdp', self.country.gdp)
        gdp_growth = (self.country.gdp - prev_gdp) / max(1, prev_gdp)
        if self.inflation > 0.05:
            self.base_interest_rate += 0.01
        elif gdp_growth < 0:
            self.base_interest_rate -= 0.01
        self.base_interest_rate = max(0.001, min(0.15, self.base_interest_rate))
        self.money_supply = self.country.gdp * (1 + self.base_interest_rate * 5)
        self.inflation = 0.02 + gdp_growth * 0.5 + self.base_interest_rate * 0.1
        self.country.stability -= self.inflation * 0.01

class StockMarket:
    def __init__(self, country):
        self.country = country
        self.index = 1000.0
        self.volatility = 0.05

    def update(self):
        prev_gdp = getattr(self.country, '_prev_gdp', self.country.gdp)
        gdp_growth = (self.country.gdp - prev_gdp) / max(1, prev_gdp)
        self.index *= (1 + gdp_growth * 2 - self.country.interest_rate * 0.5 +
                       random.uniform(-self.volatility, self.volatility))
        self.index = max(10, self.index)
        if self.index < 500:
            self.country.stability -= 0.002
            self.country.world.log(f"📉 {self.country.name} 股市暴跌，恐慌蔓延")