import random

class ResourceMarket:
    def __init__(self):
        self.base_prices = {"石油":100,"天然气":80,"煤炭":60,"铁矿":50,"稀土":120,"锂":150,"铀":200,"氢":90}
        self.prices = self.base_prices.copy()
        self.trade_agreements = []

    def update(self, countries):
        total_reserves = {r:0.0 for r in self.base_prices}
        for c in countries:
            if c.alive:
                for r,amt in c.resources.items():
                    total_reserves[r] = total_reserves.get(r,0)+amt
        for r in self.base_prices:
            scarcity = max(0, (100 - total_reserves.get(r,0))/100)
            self.prices[r] = self.base_prices[r] * (1 + scarcity*2.0)

    def get_price(self, resource):
        return self.prices.get(resource, 50)

    def negotiate_trade(self, world):
        alive = [c for c in world.countries if c.alive]
        if len(alive) < 2:
            return
        a, b = random.sample(alive, 2)
        res = None
        for r in a.resources:
            if a.resources[r] > 20 and r not in b.resources:
                res = r
                break
        if not res:
            return
        amount = 10
        self.trade_agreements.append((a.name, b.name, res, amount, world.year+5))
        if res in a.resources:
            a.resources[res] -= amount
            b.resources[res] = b.resources.get(res,0) + amount
        world.log(f"🤝 贸易协议：{a.name} 向 {b.name} 出口 {res}")