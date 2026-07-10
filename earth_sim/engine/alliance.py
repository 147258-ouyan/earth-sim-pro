from __future__ import annotations
from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from earth_sim.world import World

class Alliance:
    def __init__(self, name, members, start, end=9999, defense_pact=True, trade_boost=0.05, tech_share=0.1):
        self.name = name; self.members = members; self.start = start; self.end = end
        self.defense_pact = defense_pact; self.trade_boost = trade_boost; self.tech_share = tech_share
    def active(self, year): return self.start <= year <= self.end
    def has(self, country_name): return country_name in self.members

class AllianceSystem:
    def __init__(self):
        self.alliances = [
            Alliance("北约", ["美利坚","不列颠","法兰西","意大利","德意志","加拿大","土耳其"], 1949),
            Alliance("华约", ["苏联","波兰","东德","捷克斯洛伐克","匈牙利"], 1955, 1991),
            Alliance("欧盟", ["法兰西","德意志","意大利","荷兰","比利时","卢森堡","爱尔兰","西班牙","葡萄牙","奥地利","瑞典","芬兰","波兰","捷克","斯洛伐克","匈牙利","罗马尼亚","保加利亚","希腊","丹麦"], 1993, trade_boost=0.08, tech_share=0.15),
            Alliance("东盟", ["印尼","马来西亚","菲律宾","新加坡","泰国","越南","缅甸","老挝","柬埔寨","文莱"], 1967, trade_boost=0.04),
            Alliance("金砖", ["华夏","俄罗斯","印度","巴西","南非"], 2009, trade_boost=0.03),
        ]
        self.p5 = {"美利坚","俄罗斯","华夏","不列颠","法兰西"}

    def can_war(self, a, b, year):
        if a in self.p5 or b in self.p5: return False
        for al in self.alliances:
            if al.active(year) and al.has(a) and al.has(b): return False
        return True

    def get_trade_boost(self, country_name, year):
        boost = 1.0
        for al in self.alliances:
            if al.active(year) and al.has(country_name): boost += al.trade_boost
        return min(boost, 1.15)

    def get_tech_spillover(self, country_name, year, world: 'World'):
        spillover = 0.0
        for al in self.alliances:
            if al.active(year) and al.has(country_name):
                other_members = [world.find(m) for m in al.members if m != country_name and world.find(m) and world.find(m).alive]
                if other_members:
                    avg_budget = sum(c.research_budget for c in other_members) / len(other_members)
                    spillover += avg_budget * al.tech_share
        return spillover

    def defend(self, defender, attacker, year, world: 'World') -> List:
        defenders = []
        for al in self.alliances:
            if al.active(year) and al.has(defender.name) and al.defense_pact:
                for member in al.members:
                    if member != defender.name:
                        m = world.find(member)
                        if m and m.alive and m.name != attacker.name: defenders.append(m)
        return defenders