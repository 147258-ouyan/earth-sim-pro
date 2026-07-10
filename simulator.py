"""
============================================
 地球模拟器 Pro++ (深度现实版 · 完整文件)
 包含：个人主体、金融循环、多维生态、合法性博弈、蒙特卡洛框架
 历史校准 + 结构化人口 + 非国家行为体
============================================
"""
import numpy as np
import pandas as pd
import random
import copy
import json
import os
from typing import List, Dict, Optional, Tuple
from collections import deque
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.animation as animation
from matplotlib.animation import PillowWriter

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

q_table = {}
ai_memory = {}

COUNTRY_COORDS_SIM = {
    "华夏": (35.0, 105.0), "美利坚": (38.0, -97.0), "俄罗斯": (60.0, 90.0),
    "不列颠": (54.0, -2.0), "法兰西": (46.0, 2.0), "德意志": (51.0, 10.0),
    "日本": (36.0, 138.0), "意大利": (42.8, 12.5), "奥匈": (48.0, 16.0),
    "奥斯曼": (39.0, 35.0), "印度": (20.0, 78.0), "巴西": (-10.0, -55.0),
    "加拿大": (60.0, -95.0), "澳大利亚": (-25.0, 135.0), "阿根廷": (-34.0, -64.0),
    "南非": (-29.0, 24.0), "土耳其": (39.0, 35.0), "捷克斯洛伐克": (49.8, 15.5),
    "奥地利": (47.5, 14.5), "匈牙利": (47.0, 19.5), "乌克兰": (49.0, 31.0),
    "白俄罗斯": (53.0, 27.0), "哈萨克斯坦": (48.0, 66.0), "巴基斯坦": (30.0, 70.0),
    "以色列": (31.0, 35.0), "东德": (52.5, 13.4), "西德": (51.0, 10.0), "苏联": (60.0, 90.0),
}

class LivePlotter:
    def __init__(self, world, max_points=200, interactive=True):
        self.world = world
        self.max_points = max_points
        self.interactive = interactive
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(14, 5))
        self.fig.suptitle('地球模拟器 Pro++ 实时监控', fontsize=14)
        self.years = deque(maxlen=max_points)
        self.env_history = deque(maxlen=max_points)
        self.gdp_history = {}
        self.top_names = []

    def update(self):
        year = self.world.year
        env = self.world.global_environment
        self.years.append(year)
        self.env_history.append(env)
        alive = sorted([c for c in self.world.countries if c.alive],
                       key=lambda x: x.gdp, reverse=True)[:3]
        new_top = [c.name for c in alive]
        if new_top != self.top_names:
            for name in new_top:
                if name not in self.gdp_history:
                    self.gdp_history[name] = deque([float('nan')] * len(self.years), maxlen=self.max_points)
            self.top_names = new_top
        for name in self.top_names:
            if name not in self.gdp_history:
                self.gdp_history[name] = deque(maxlen=self.max_points)
            c = self.world.find(name)
            if c:
                self.gdp_history[name].append(c.gdp)
            else:
                self.gdp_history[name].append(float('nan'))
        self.ax1.clear()
        self.ax2.clear()
        self.ax1.set_title('全球环境健康度')
        self.ax1.plot(list(self.years), list(self.env_history), 'g-', linewidth=2)
        self.ax1.set_ylim(0, 100)
        self.ax1.set_ylabel('环境指数')
        self.ax1.grid(True, alpha=0.3)
        self.ax2.set_title('GDP 前三国家')
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
        yr_list = list(self.years)
        for i, name in enumerate(self.top_names):
            if name in self.gdp_history:
                gdp_list = list(self.gdp_history[name])
                min_len = min(len(yr_list), len(gdp_list))
                if min_len > 0:
                    self.ax2.plot(yr_list[-min_len:], gdp_list[-min_len:],
                                  label=name, color=colors[i % 3], linewidth=2)
        self.ax2.legend()
        self.ax2.set_ylabel('GDP (B)')
        self.ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        if self.interactive:
            plt.pause(0.01)

class TechEra:
    ERAS = [
        (1.2, "蒸汽时代", "工业起步"), (2.8, "电气时代", "电力与内燃机"),
        (5.0, "原子能时代", "核能与计算机"), (8.0, "信息时代", "互联网革命"),
        (11.0, "AI时代", "人工智能、绿色能源"), (15.0, "星际时代", "可控核聚变、生态修复"),
    ]
    @classmethod
    def get_era(cls, tech_sum):
        name, desc = "前工业时代", ""
        for t, n, d in cls.ERAS:
            if tech_sum >= t: name, desc = n, d
        return name, desc

class TechNode:
    def __init__(self, name, desc, unlock_conditions, effects, required_tech_sum=0, min_year=1900):
        self.name = name; self.desc = desc; self.unlock_conditions = unlock_conditions
        self.effects = effects; self.required_tech_sum = required_tech_sum
        self.min_year = min_year; self.unlocked = False

class TechTree:
    def __init__(self):
        self.nodes = [
            TechNode("蒸汽动力", "工业革命", {}, {"industry_tech":1.5}, 1.0, 1700),
            TechNode("电磁理论", "电力与通信", {"math":2.0}, {"energy_tech":1.3,"information_tech":1.2}, 2.5, 1800),
            TechNode("量子力学", "微观规则", {"math":4.0,"physics":3.0}, {"physics":1.5,"chemistry":1.3}, 5.0, 1900),
            TechNode("半导体", "计算机革命", {"量子力学":1}, {"information_tech":2.0,"industry_tech":1.3}, 7.0, 1940),
            TechNode("核能", "原子能利用", {"量子力学":1,"physics":5.0}, {"energy_tech":1.8}, 8.0, 1945),
            TechNode("基因编辑", "生命科学", {"biology":5.0,"chemistry":4.0}, {"biology":1.5,"medicine":1.5}, 9.0, 1970),
            TechNode("人工智能", "机器学习", {"半导体":1,"math":6.0}, {"ai_tech":2.0,"information_tech":1.5}, 11.0, 1950),
            TechNode("可控核聚变", "无限能源", {"核能":1,"physics":8.0,"energy_tech":6.0}, {"energy_tech":2.0,"environment_tech":1.5}, 14.0, 2000),
            TechNode("量子计算", "算力革命", {"量子力学":1,"人工智能":1,"math":8.0}, {"ai_tech":1.5,"information_tech":1.8,"scientific_knowledge":0.5}, 16.0, 2010),
        ]
    def check_unlocks(self, knowledge, year):
        for node in self.nodes:
            if node.unlocked: continue
            if year < node.min_year: continue
            cond_met = True
            for tech, level in node.unlock_conditions.items():
                if tech in [n.name for n in self.nodes]:
                    pre = next((n for n in self.nodes if n.name==tech), None)
                    if pre and not pre.unlocked: cond_met = False; break
                else:
                    if getattr(knowledge, tech, 0) < level: cond_met = False; break
            if cond_met and knowledge.total_tech() >= node.required_tech_sum:
                node.unlocked = True
                for attr, mult in node.effects.items():
                    cur = getattr(knowledge, attr, 0)
                    setattr(knowledge, attr, cur * mult)
                knowledge.log_event(f"🔬 科技突破：{node.name} - {node.desc}")

class KnowledgeTree:
    def __init__(self, world):
        self.world = world
        self.math, self.physics, self.chemistry = 0.5, 0.3, 0.4
        self.biology, self.medicine, self.agriculture = 0.5, 0.5, 0.5
        self.philosophy, self.sociology = 0.6, 0.4
        self.energy_tech, self.environment_tech = 0.2646, 0.2320
        self.industry_tech, self.information_tech = 0.3, 0.1
        self.space_tech, self.ai_tech = 0.0, 0.0
        self.global_green_policy = 0.1
        self.scientific_knowledge = 0.5
        self.quantum_tech = 0.0
        self.tech_tree = TechTree()

    def total_tech(self):
        return sum([self.energy_tech, self.industry_tech, self.information_tech,
                    self.ai_tech, self.space_tech, self.environment_tech])

    def log_event(self, msg):
        if self.world: self.world.log(msg)

    def update(self, countries, year):
        alive = [c for c in countries if c.alive]
        if not alive: return
        total_invest = sum(c.research_budget for c in alive)
        base_progress = total_invest * 0.0018
        progress = base_progress * (0.5 + self.scientific_knowledge)
        if self.ai_tech > 5 and self.math > 6 and self.quantum_tech < 10:
            self.quantum_tech = min(10, self.quantum_tech + base_progress * 0.1)
        if year >= 1940 and self.industry_tech < 4: progress *= 1.3
        if year >= 1990 and self.information_tech < 6: progress *= 1.5
        if year >= 2020 and self.ai_tech < 3: progress *= 1.8
        self.math = min(10, self.math + progress * 1.2)
        self.physics = min(10, self.physics + progress * 1.0)
        self.chemistry = min(10, self.chemistry + progress * 0.9)
        self.biology = min(10, self.biology + progress * 1.0)
        self.medicine = min(10, self.medicine + progress * 0.8)
        self.agriculture = min(10, self.agriculture + progress * 0.7)
        self.philosophy = min(10, self.philosophy + progress * 0.5 + self.global_green_policy*0.02)
        self.sociology = min(10, self.sociology + progress * 0.5)
        self.energy_tech = min(10, self.energy_tech + progress * 1.0)
        self.environment_tech = min(10, self.environment_tech + progress * 0.9 + self.global_green_policy*0.08)
        self.industry_tech = min(10, self.industry_tech + progress * 0.9)
        if self.math > 2: self.information_tech = min(10, self.information_tech + progress * 1.3)
        if self.physics > 4 and self.industry_tech > 4:
            self.space_tech = min(10, self.space_tech + progress * 0.6)
        if self.math > 3 and self.information_tech > 4:
            self.ai_tech = min(10, self.ai_tech + progress * 0.8)
        self.scientific_knowledge = min(10, self.scientific_knowledge + progress * 0.5)
        self.tech_tree.check_unlocks(self, year)

    def env_repair_rate(self):
        if self.environment_tech < 5: base = 0.002 * self.environment_tech
        else: base = 0.01 + (self.environment_tech - 5) * 0.1
        if self.space_tech > 5: base += 0.05
        if self.ai_tech > 7: base += 0.1
        if self.quantum_tech > 3: base += 0.1
        if any(n.name == "可控核聚变" and n.unlocked for n in self.tech_tree.nodes): base += 0.4
        base += self.global_green_policy * 0.3
        if self.green_ratio() > 0.9: base *= 1.1
        return base

    def green_ratio(self):
        raw = self.energy_tech * 0.06 + self.global_green_policy * 0.28
        bonus = 0.0
        if self.ai_tech > 7: bonus += 0.03
        if self.quantum_tech > 3: bonus += 0.05
        return min(0.98, raw + bonus)

class ResourceMarket:
    def __init__(self):
        self.base_prices = {"石油":100,"天然气":80,"煤炭":60,"铁矿":50,"稀土":120,"锂":150,"铀":200,"氢":90}
        self.prices = self.base_prices.copy()
        self.trade_agreements = []
    def update(self, countries):
        total_reserves = {r:0.0 for r in self.base_prices}
        for c in countries:
            if c.alive:
                for r,amt in c.resources.items(): total_reserves[r] = total_reserves.get(r,0)+amt
        for r in self.base_prices:
            scarcity = max(0, (100 - total_reserves.get(r,0))/100)
            self.prices[r] = self.base_prices[r] * (1 + scarcity*2.0)
    def get_price(self, resource): return self.prices.get(resource, 50)
    def negotiate_trade(self, world):
        alive = [c for c in world.countries if c.alive]
        if len(alive) < 2: return
        a, b = random.sample(alive, 2)
        res = None
        for r in a.resources:
            if a.resources[r] > 20 and r not in b.resources: res = r; break
        if not res: return
        amount = 10
        self.trade_agreements.append((a.name, b.name, res, amount, world.year+5))
        if res in a.resources:
            a.resources[res] -= amount
            b.resources[res] = b.resources.get(res,0) + amount
        world.log(f"🤝 贸易协议：{a.name} 向 {b.name} 出口 {res}")

class ProxyWarSystem:
    def __init__(self, alliances): self.alliances = alliances
    def attempt(self, world):
        p5 = list(self.alliances.p5)
        random.shuffle(p5)
        if len(p5)<2: return
        a,b = world.find(p5[0]), world.find(p5[1])
        if not a or not b: return
        proxies_a = [c for c in world.countries if c.alive and c.name not in self.alliances.p5]
        proxies_b = [c for c in world.countries if c.alive and c.name not in self.alliances.p5]
        if not proxies_a or not proxies_b: return
        pa, pb = random.choice(proxies_a), random.choice(proxies_b)
        world.log(f"🥷 代理人战争：{a.name} 支持 {pa.name} 对抗 {b.name} 支持的 {pb.name}")
        a.material_gdp *= 0.99; a.service_gdp *= 0.99
        b.material_gdp *= 0.99; b.service_gdp *= 0.99
        world._war_direct(pa, pb, 0.3)

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
    def get_tech_spillover(self, country_name, year, world):
        spillover = 0.0
        for al in self.alliances:
            if al.active(year) and al.has(country_name):
                other_members = [world.find(m) for m in al.members if m != country_name and world.find(m) and world.find(m).alive]
                if other_members:
                    avg_budget = sum(c.research_budget for c in other_members) / len(other_members)
                    spillover += avg_budget * al.tech_share
        return spillover
    def defend(self, defender, attacker, year, world):
        defenders = []
        for al in self.alliances:
            if al.active(year) and al.has(defender.name) and al.defense_pact:
                for member in al.members:
                    if member != defender.name:
                        m = world.find(member)
                        if m and m.alive and m.name != attacker.name: defenders.append(m)
        return defenders

LANGUAGES = ["英语", "汉语", "俄语", "法语", "德语", "日语", "印地语", "阿拉伯语", "葡萄牙语", "西班牙语"]
RELIGIONS = ["基督教", "伊斯兰教", "印度教", "佛教", "无宗教", "东正教", "犹太教"]
IDEOLOGIES = ["自由主义", "保守主义", "共产主义", "民族主义", "社会民主主义", "威权主义"]

class InternalAgent:
    def __init__(self, name, agent_type, power, wealth=0.0, goal="profit"):
        self.name = name; self.type = agent_type; self.power = power; self.wealth = wealth
        self.goal = goal; self.alive = True

    def act(self, country):
        if self.type == "corporation":
            country.material_gdp *= 1.001
            country.env_pressure -= self.power * 0.001
            country.env_pressure = max(0.0, country.env_pressure)
        elif self.type == "ngo":
            country.env_pressure += self.power * 0.002
            country.env_pressure = min(1.0, country.env_pressure)
            country.material_gdp *= 0.999
        elif self.type == "lobby":
            if self.goal == "military":
                country.aggression += self.power * 0.005
                country.aggression = min(1.0, max(0.1, country.aggression))
                country.material_gdp *= 1.0005
            elif self.goal == "technology":
                country.research_budget += self.power * 0.1
                country.research_budget = min(30, country.research_budget)
            elif self.goal == "profit":
                country.material_gdp *= 1.0008
                country.env_pressure -= self.power * 0.0005
                country.env_pressure = max(0.0, country.env_pressure)
        if self.power > 0.3 and random.random() < 0.1:
            country.world.log(f"🏛️ {self.name}（{self.type}）成功影响{country.name}政策")

class MultinationalCorp(InternalAgent):
    def __init__(self, name, home_country, power, wealth=100.0):
        super().__init__(name, "corporation", power, wealth, "profit")
        self.home_country = home_country
        self.branches = []

    def expand(self, world):
        if not world.countries or len(world.countries) < 2: return
        candidates = [c for c in world.countries if c.alive
                      and c.name != self.home_country
                      and c.name not in self.branches]
        if not candidates: return
        target = random.choice(candidates)
        home_c = world.find(self.home_country)
        if home_c and home_c.alive:
            home_c.service_gdp *= 0.999
            home_c.material_gdp *= 0.9998
        target.material_gdp *= 1.002
        target.env_pressure += self.power * 0.001
        self.branches.append(target.name)
        world.log(f"🏢 {self.name} 在 {target.name} 设立分支")

class INGO:
    def __init__(self, name, focus, influence=0.2):
        self.name = name; self.focus = focus
        self.influence = influence; self.resources = 50.0; self.alive = True

    def act(self, world):
        if self.focus == "environment":
            env_urgency = (100 - world.global_environment) / 100
            world.knowledge.global_green_policy += self.influence * 0.002 * env_urgency
            world.knowledge.global_green_policy = min(1.0, world.knowledge.global_green_policy)
            top_polluters = sorted([c for c in world.countries if c.alive],
                                   key=lambda c: c.env_pressure, reverse=True)[:3]
            for country in top_polluters:
                if random.random() < self.influence * 0.5:
                    country.stability -= 0.01
                    world.log(f"📢 {self.name} 谴责{country.name}的环境记录")
            self.resources -= 0.1 * env_urgency
        elif self.focus == "human_rights":
            abusers = [c for c in world.countries if c.alive and (c.stability < 0.5 or c.government == "威权")]
            for country in random.sample(abusers, min(3, len(abusers))):
                if country.stability > 0.3 and random.random() < self.influence * 0.4:
                    country.stability -= 0.02
                    if random.random() < 0.2:
                        if country.trade_partners:
                            target = random.choice(list(country.trade_partners))
                            country.trade_partners.discard(target)
                            partner = world.find(target)
                            if partner and partner.alive and country.name in partner.trade_partners:
                                partner.trade_partners.discard(country.name)
                            world.log(f"🚫 {self.name} 推动对{country.name}的制裁")
            self.resources -= 0.1
        elif self.focus == "health":
            world.knowledge.medicine += self.influence * 0.001
            victims = [c for c in world.countries if c.alive and (c.food_reserve < 0.4 or c.population < c.founding_population * 0.5)]
            for country in random.sample(victims, min(3, len(victims))):
                country.food_reserve += 0.02
                country.stability += 0.01
                world.log(f"💊 {self.name} 向{country.name}提供医疗援助")
            self.resources -= 0.1
        self.resources += random.uniform(0.5, 1.5)
        self.resources = max(0, min(100, self.resources))
        if self.resources <= 0:
            self.alive = False
            world.log(f"💔 {self.name} 因资源枯竭解散")

class NonStateArmedGroup:
    def __init__(self, name, group_type, base_country, strength=10.0):
        self.name = name; self.type = group_type
        self.base_country = base_country; self.strength = strength; self.alive = True

    def act(self, world):
        country = world.find(self.base_country)
        if not country or not country.alive: self.alive = False; return
        if self.type == "guerrilla":
            country.stability -= self.strength * 0.01
            country.material_gdp *= (1 - self.strength * 0.001)
            if random.random() < 0.2: world.log(f"💣 {self.name} 在 {self.base_country} 发动袭击")
        elif self.type == "terrorist":
            country.stability -= self.strength * 0.02
            country.material_gdp *= (1 - self.strength * 0.002)
            if random.random() < 0.3: world.log(f"💥 {self.name} 在 {self.base_country} 制造恐怖事件")
        elif self.type == "mercenary":
            country.material_gdp *= (1 - self.strength * 0.0005)
        if country.stability < 0.3: self.strength += random.uniform(0, 0.5)
        else: self.strength -= random.uniform(0.1, 0.3)
        self.strength = max(0, min(50, self.strength))
        if self.strength <= 0:
            self.alive = False
            world.log(f"🕊️ {self.name} 在 {self.base_country} 被剿灭")

class Individual:
    def __init__(self, age, wealth, education):
        self.age = age
        self.wealth = wealth
        self.education = education
        self.satisfaction = 0.5
        self.alive = True

    def update(self, country, env_factor):
        self.age += 1
        if self.age > 85:
            self.alive = False
            return
        if self.wealth > 100:
            country.service_gdp += self.wealth * 0.01
        else:
            country.material_gdp += self.wealth * 0.02
        per_capita = country.gdp / max(1, country.population)
        self.satisfaction = (self.education * 0.3 +
                            country.stability * 0.3 +
                            min(1, per_capita / 100) * 0.2 +
                            (country.world.global_environment / 100) * 0.2)
        if self.satisfaction < 0.2 and random.random() < 0.001:
            country.stability -= 0.0001
            country.world.log(f"😞 {country.name} 民众不满情绪上升")

class Household:
    def __init__(self, country):
        self.members = []
        for _ in range(random.randint(2, 5)):
            age = random.randint(0, 80)
            wealth = random.uniform(1, 200)
            edu = random.uniform(0.1, 1.0)
            self.members.append(Individual(age, wealth, edu))
        self.country = country

    def update(self, country, env_factor):
        alive_members = [m for m in self.members if m.alive]
        if len(alive_members) < 1:
            return False
        for m in alive_members:
            m.update(country, env_factor)
        young_adults = [m for m in alive_members if 20 < m.age < 40]
        if young_adults and random.random() < 0.05 * len(young_adults):
            new_wealth = np.mean([m.wealth for m in alive_members])
            new_edu = np.mean([m.education for m in alive_members]) * random.uniform(0.8, 1.2)
            self.members.append(Individual(0, new_wealth, new_edu))
        return True

class CentralBank:
    def __init__(self, country):
        self.country = country
        self.base_interest_rate = 0.03
        self.money_supply = country.gdp * 1.5
        self.inflation = 0.02

    def update(self):
        gdp_growth = (self.country.gdp - getattr(self.country, '_prev_gdp', self.country.gdp)) / max(1, getattr(self.country, '_prev_gdp', self.country.gdp))
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
        gdp_growth = (self.country.gdp - getattr(self.country, '_prev_gdp', self.country.gdp)) / max(1, getattr(self.country, '_prev_gdp', self.country.gdp))
        self.index *= (1 + gdp_growth * 2 - self.country.interest_rate * 0.5 + random.uniform(-self.volatility, self.volatility))
        self.index = max(10, self.index)
        if self.index < 500:
            self.country.stability -= 0.002
            self.country.world.log(f"📉 {self.country.name} 股市暴跌，恐慌蔓延")

class Ecosystem:
    def __init__(self):
        self.forest_cover = 100.0
        self.ocean_health = 100.0
        self.freshwater = 100.0
        self.biodiversity = 100.0

    @property
    def overall_health(self):
        return (self.forest_cover + self.ocean_health + self.freshwater + self.biodiversity) / 4

    def update(self, waste, total_gdp):
        self.forest_cover -= total_gdp * 0.000005
        self.ocean_health -= waste * 0.0005
        self.freshwater -= total_gdp * 0.000002
        self.biodiversity -= waste * 0.00025
        repair_rate = 0.05 + (100 - self.overall_health) * 0.001
        for attr in ['forest_cover', 'ocean_health', 'freshwater', 'biodiversity']:
            val = getattr(self, attr)
            setattr(self, attr, min(100, val + (100 - val) * repair_rate))
        if self.forest_cover < 30 and random.random() < 0.001:
            self.forest_cover = max(0, self.forest_cover - 10)

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

class Country:
    def __init__(self, world, name, region, pop, gdp, res, tech, rb, ideology=0, camp=0,
                 government="混合", party_support=0.5, election_year=1904,
                 language="英语", religion="基督教", main_ideology="自由主义",
                 ai_controlled=False, constitution="standard"):
        self.world = world; self.name = name; self.region = region
        self.pop_children = pop * 0.35; self.pop_young = pop * 0.40
        self.pop_middle = pop * 0.20; self.pop_old = pop * 0.05
        self.material_gdp = gdp * 0.8; self.service_gdp = gdp * 0.2
        self.resources = res; self.tech_level = tech; self.research_budget = rb
        self.stability = 0.7+random.random()*0.2
        self.aggression = random.random()*0.4+0.2
        self.ideology = ideology; self.camp = camp
        self.trade_partners = set(); self.alive = True
        self.env_pressure = 0.0; self.education = 0.3; self.food_reserve = 0.5
        self.war_victory_bonus = 0.0; self.war_defeat_penalty = 0.0
        self.last_war_year = 0; self.democracy_movement_cd = 0
        self.government = government; self.party_support = party_support; self.election_year = election_year
        self.language = language; self.religion = religion; self.main_ideology = main_ideology
        self.cultural_influence = {}
        self.internal_agents: List[InternalAgent] = []
        self.ai_controlled = ai_controlled
        self._prev_gdp = self.gdp; self._prev_stability = self.stability
        self.founding_population = pop
        self.founding_language = language; self.founding_ideology = main_ideology
        self.latitude, self.longitude = COUNTRY_COORDS_SIM.get(self.name, (0, 0))
        self.is_federal = False; self.federal_age = 0
        self.debt = 0.0; self.interest_rate = 0.03
        self.constitution = constitution
        self.households = []
        self.central_bank = CentralBank(self)
        self.stock_market = StockMarket(self)
        self.legitimacy = PoliticalLegitimacy(self)

    @property
    def population(self):
        return self.pop_children + self.pop_young + self.pop_middle + self.pop_old

    @population.setter
    def population(self, value):
        total = self.population
        if total > 0:
            ratio = value / total
            self.pop_children *= ratio; self.pop_young *= ratio
            self.pop_middle *= ratio; self.pop_old *= ratio

    @property
    def gdp(self):
        return self.material_gdp + self.service_gdp

    def military_power(self):
        labor = self.pop_young + self.pop_middle * 0.7
        return (self.gdp * 0.3 + labor * 0.25 + self.world.knowledge.industry_tech*10) * (0.5+self.stability)

    @staticmethod
    def env_growth_factor(env):
        if env < 10: return 0.01
        elif env < 20: return 0.03
        elif env < 40: return 0.06
        return (env-10)/90

    def cultural_difference(self, other):
        diff = 0.0
        if self.language != other.language: diff += 0.3
        if self.religion != other.religion: diff += 0.3
        if self.main_ideology != other.main_ideology: diff += 0.4
        return diff

    def spawn_agents(self):
        for i in range(random.randint(2, 5)):
            self.internal_agents.append(InternalAgent(f"{self.name}企业{i}", "corporation", random.uniform(0.1, 0.4), random.uniform(10, 100), "profit"))
        for i in range(random.randint(1, 3)):
            self.internal_agents.append(InternalAgent(f"{self.name}绿色组织{i}", "ngo", random.uniform(0.05, 0.3), random.uniform(1, 10), "environment"))
        for i in range(random.randint(1, 2)):
            goal = random.choice(["military", "technology", "profit"])
            self.internal_agents.append(InternalAgent(f"{self.name}游说团{i}", "lobby", random.uniform(0.1, 0.35), random.uniform(20, 80), goal))

    def spawn_households(self, num_households=100):
        for _ in range(num_households):
            self.households.append(Household(self))

    def internal_development(self):
        w = self.world; k = w.knowledge; market = w.resource_market; year = w.year
        env_factor = Country.env_growth_factor(w.global_environment)
        carrying_capacity = (202 + w.global_environment * 8 + k.agriculture * 50 + k.medicine * 30)

        # 家庭和金融市场更新
        for hh in self.households[:]:
            if not hh.update(self, env_factor):
                self.households.remove(hh)
        self.central_bank.update()
        self.stock_market.update()
        self.interest_rate = self.central_bank.base_interest_rate
        gdp_growth = (self.gdp - self._prev_gdp) / max(1, self._prev_gdp)
        self.legitimacy.update(gdp_growth)

        # 人口更新
        total_pop = self.population
        births = (self.pop_young * 0.062 + self.pop_middle * 0.01) * env_factor
        child_death = self.pop_children * (0.02 / (1 + k.medicine * 0.5)) * (1 / env_factor)
        death_young = self.pop_young * (0.005 / (1 + k.medicine * 0.2))
        death_middle = self.pop_middle * (0.02 / (1 + k.medicine * 0.2))
        death_old = self.pop_old * (0.133 / (1 + k.medicine * 0.3))
        aging_to_young = self.pop_children * 0.07
        aging_to_middle = self.pop_young * 0.022
        aging_to_old = self.pop_middle * 0.015
        self.pop_children += births - child_death - aging_to_young
        self.pop_young += aging_to_young - death_young - aging_to_middle
        self.pop_middle += aging_to_middle - death_middle - aging_to_old
        self.pop_old += aging_to_old - death_old
        for attr in ['pop_children', 'pop_young', 'pop_middle', 'pop_old']:
            setattr(self, attr, max(0.1, getattr(self, attr)))
        if total_pop > carrying_capacity:
            scale = carrying_capacity / total_pop
            self.pop_children *= scale; self.pop_young *= scale
            self.pop_middle *= scale; self.pop_old *= scale

        self.education = min(1, self.education + 0.003*self.research_budget)
        trade_multiplier = w.alliances.get_trade_boost(self.name, year)
        tech_spillover = w.alliances.get_tech_spillover(self.name, year, w)
        per_capita = self.gdp / max(1, self.population)
        convergence_factor = 1.0
        if per_capita > 200: convergence_factor = 0.7
        elif per_capita > 100: convergence_factor = 0.85
        if per_capita < 20 and self.population < 500: convergence_factor = 1.3
        total_mat = sum(c.material_gdp for c in w.countries if c.alive)
        country_mat_cap = self.population * (3 + k.industry_tech * 0.5) + sum(self.resources.values()) * 0.3
        self_saturation = max(0.01, 1 - self.material_gdp / max(1, country_mat_cap))
        global_saturation = max(0.01, 1 - total_mat / 80000)
        mat_saturation = min(self_saturation, global_saturation)
        mat_base = 0.024 + k.industry_tech*0.0086 - env_factor*0.005
        resource_income = sum(market.get_price(r)*amt*0.0001 for r,amt in self.resources.items())
        env_penalty = max(0, (50 - w.global_environment) * 0.005)
        mat_growth = (mat_base + resource_income - env_penalty) * mat_saturation * env_factor * trade_multiplier * convergence_factor
        mat_growth += self.war_victory_bonus - self.war_defeat_penalty
        if self.is_federal: mat_growth -= 0.015; self.federal_age += 1
        mat_growth += random.uniform(-0.005,0.005)
        labor_ratio = (self.pop_young + self.pop_middle * 0.7) / max(1, self.population)
        mat_growth *= (0.5 + labor_ratio)
        energy_needed = self.material_gdp * 0.0001
        energy_supplied = self.resources.get("石油", 0) * 0.3 + self.resources.get("天然气", 0) * 0.2 + self.resources.get("煤炭", 0) * 0.1 + k.energy_tech * 10
        if energy_supplied < energy_needed * 0.5:
            mat_growth *= energy_supplied / (energy_needed + 1)
        self.material_gdp *= (1+mat_growth)

        total_serv = sum(c.service_gdp for c in w.countries if c.alive)
        total_gdp = sum(c.gdp for c in w.countries if c.alive)
        service_share = total_serv / max(1, total_gdp)
        serv_saturation = max(0.02, 1 - service_share/0.9)
        serv_base = 0.0278 + k.information_tech*0.0119 + k.ai_tech*0.006 - env_penalty*0.1
        if k.quantum_tech > 2: serv_base += 0.005
        serv_growth = serv_base * serv_saturation * trade_multiplier + random.uniform(-0.005,0.005)
        self.service_gdp *= (1+serv_growth)
        if self.service_gdp < 0.01: self.service_gdp = 0.01

        # 财政与国债
        tax_rate = 0.2
        tax_income = self.gdp * tax_rate
        spending = self.research_budget + self.service_gdp * 0.1
        interest_payment = self.debt * self.interest_rate
        deficit = spending + interest_payment - tax_income
        if not np.isnan(deficit): self.debt += deficit
        if self.debt < 0: self.debt = 0
        debt_ratio = self.debt / max(1, self.gdp)
        self.interest_rate = max(0.01, 0.03 + debt_ratio * 0.05)
        if debt_ratio > 1.61:
            self.stability -= 0.05
            w.log(f"📉 {self.name} 债务危机，国债/GDP超过150%")

        self.research_budget += 0.008*(self.gdp / max(1,self.population)) + tech_spillover * 0.01
        if per_capita > 200: self.research_budget *= 0.99
        self.research_budget = max(0.1, min(30, self.research_budget))
        self.env_pressure = ((100-w.global_environment)/100)*self.education*0.3
        if self.stability > 0.5: k.global_green_policy += self.env_pressure*0.008

        # 稳定度计算
        social_fairness = (self.education + k.medicine/10 + self.env_pressure) / 3
        self.stability += social_fairness * 0.005
        if per_capita < 0.3: self.stability -= 0.04
        elif per_capita > 200: self.stability -= 0.04
        elif per_capita > 100: self.stability -= 0.02
        self.stability += k.sociology * 0.0005
        if self.food_reserve < 0.3: self.stability -= 0.03
        scale_penalty = 1.0
        if self.population > 500:
            if self.is_federal: scale_penalty += (self.population - 500) / 500 * 1.0
            else: scale_penalty += (self.population - 500) / 500 * 2.0
        institutional_entropy = (self.population * self.gdp) / 50000000 * scale_penalty
        self.stability -= institutional_entropy * 0.001
        negentropy = (self.research_budget * 0.063 + k.energy_tech * 0.1) * env_factor
        self.stability += min(negentropy, institutional_entropy * 0.05)
        if self.population > 800 and not self.is_federal:
            self.stability -= (self.population / 1000) * 0.03
        elif self.population > 500 and not self.is_federal:
            self.stability -= (self.population / 1000) * 0.01
        serv_share = self.service_gdp / max(1, self.gdp)
        if serv_share > 0.8: self.stability -= (serv_share - 0.8) * 0.05
        old_burden = self.pop_old / max(1, self.population)
        if old_burden > 0.2:
            self.research_budget *= 0.999
            self.stability -= old_burden * 0.01
        if w.global_environment < 40:
            self.stability -= (40 - w.global_environment) * 0.001
            if k.global_green_policy > 0.4: self.stability += 0.01
        self._update_culture(year)
        self._update_politics(year)
        if self.population > 500 and not self.is_federal and self.stability > 0.3:
            self.is_federal = True; self.federal_age = 0
            w.log(f"🏛️ {self.name} 因规模过大转为联邦制，内部高度自治")
        defeat_penalty = self.war_defeat_penalty
        if defeat_penalty > 0.005:
            if year >= 1960 and year < 1980: defeat_penalty *= 0.5
            elif year >= 1980: defeat_penalty = 0.0
            if defeat_penalty > 0: self.stability -= 0.02
        if year >= 1980 and self.war_defeat_penalty <= 0.005 and self.stability < 0.6:
            self.stability += 0.015
            w.log(f"📈 {self.name} 战后复兴提振稳定度")
        if random.random() < 0.03:
            if self.stability < 0.4:
                event = random.choice(["罢工", "政变"])
                w.log(f"⚡ {self.name} 发生{event}")
                self.stability -= 0.05; self.material_gdp *= 0.98
                if event == "政变": self._coup()
            elif self.stability < 0.6:
                if random.random() < 0.2:
                    w.log(f"⚡ {self.name} 爆发抗议")
                    self.stability -= 0.02
        if self.education > 0.7 and per_capita > 5 and random.random() < 0.01:
            if self.democracy_movement_cd <= year:
                w.log(f"🗳️ {self.name} 爆发民主化运动")
                self.stability -= 0.03; k.sociology += 0.02; self.democracy_movement_cd = year + 5
                if self.government == "威权" and random.random() < 0.5:
                    self.government = "混合"
                    w.log(f"   {self.name} 政府向混合制过渡")
        if self.ideology > 0.5: self.stability += 0.005
        elif self.ideology < -0.5: self.stability -= 0.005
        total_diff = 0; count = 0
        for c in w.countries:
            if c.alive and c.name != self.name:
                total_diff += self.cultural_difference(c); count += 1
        if count > 0:
            avg_diff = total_diff / count
            self.stability -= avg_diff * 0.02
            self.aggression += avg_diff * 0.02
            self.aggression = max(0.1, min(1.0, self.aggression))
        self.stability = max(0, min(1, self.stability + random.uniform(-0.02, 0.02)))

        # 资源消耗
        for r in list(self.resources.keys()):
            price = market.get_price(r)
            depletion = (0.3+self.tech_level*0.2) / (1+price/100)
            if k.information_tech>6: depletion*=0.6
            self.resources[r] -= depletion
            if r in self.resources: depletion_amount = min(depletion, self.resources[r])
            else: depletion_amount = depletion
            w.waste_accumulation += depletion_amount * 0.05
            if self.resources[r] <= 0:
                del self.resources[r]; w.log(f"{self.name} 的 {r} 枯竭")
                self.material_gdp *= 0.94
        if not self.resources and k.information_tech>4 and random.random()<0.15:
            high_res = max(market.prices.items(), key=lambda x:x[1])[0]
            self.resources[high_res] = 20; w.log(f"{self.name} 因高价刺激开发出 {high_res} 替代技术")
        self.food_reserve += k.agriculture*0.01 - (100-w.global_environment)*0.0003
        self.food_reserve = max(0,min(1,self.food_reserve))

        # 内部智能体
        for agent in self.internal_agents:
            if agent.alive: agent.act(self)

        # 联邦分裂
        if self.alive and self.is_federal and self.federal_age > 10:
            separation_chance = min(0.05, (self.population / 1000) * 0.022)
            if random.random() < separation_chance:
                sep_pop = self.population * random.uniform(0.15, 0.3)
                ratio = sep_pop / self.population
                self.pop_children *= (1 - ratio); self.pop_young *= (1 - ratio)
                self.pop_middle *= (1 - ratio); self.pop_old *= (1 - ratio)
                self.stability += 0.05
                w.log(f"🏛️ {self.name} 的联邦成员和平独立，分离人口 {sep_pop:.0f}M")
                new_name = f"{self.name}自治区"
                w.spawn(new_name, self.region, sep_pop,
                        self.gdp * (sep_pop / (self.population + sep_pop)),
                        {}, self.tech_level, self.research_budget * 0.6,
                        self.ideology, self.camp, self.government, sup=0.5,
                        elec=w.year + random.randint(3,5),
                        lang=self.language, rel=self.religion, ide=self.main_ideology)

        if self.stability <= 0 or self.population <= 0.3:
            self.alive = False; w.log(f"💔 {self.name} 崩溃")
        if not self.alive and k.information_tech > 3 and random.random() < 0.9:
            self.alive = True; self.stability=0.6
            self.pop_children = self.population * 0.35 * 0.85
            self.pop_young = self.population * 0.40 * 0.85
            self.pop_middle = self.population * 0.20 * 0.85
            self.pop_old = self.population * 0.05 * 0.85
            self.material_gdp*=0.85; self.service_gdp*=0.85
            w.log(f"🔄 {self.name} 重组为流亡政府")
        self._prev_gdp = self.gdp

    def _update_culture(self, year):
        w = self.world
        for other in w.countries:
            if not other.alive or other.name == self.name: continue
            trade_volume = (self.gdp + other.gdp) * 0.01
            alliance_bonus = 1.0
            for al in w.alliances.alliances:
                if al.active(year) and al.has(self.name) and al.has(other.name):
                    alliance_bonus = 1.5; break
            distance = ((self.latitude - other.latitude)**2 + (self.longitude - other.longitude)**2) ** 0.5
            geo_factor = 1.0 / (1 + distance * 0.01)
            influence_gain = trade_volume * alliance_bonus * 0.001 * geo_factor
            if other.name not in self.cultural_influence:
                self.cultural_influence[other.name] = 0
            self.cultural_influence[other.name] += influence_gain
            resistance = (self.population * self.education) / 200
            if resistance > 0.9: resistance = 0.9
            threshold = 10 + 20 * resistance
            if self.cultural_influence[other.name] > threshold:
                if random.random() < 0.1 * (1 - resistance):
                    if random.random() < 0.5 and self.language != other.language:
                        old_lang = self.language
                        self.language = other.language
                        w.log(f"🌍 {self.name} 在{other.name}影响下，语言从{old_lang}改为{self.language}")
                    elif random.random() < 0.5 and self.main_ideology != other.main_ideology:
                        old_ide = self.main_ideology
                        self.main_ideology = other.main_ideology
                        w.log(f"🌍 {self.name} 在{other.name}影响下，意识形态从{old_ide}改为{self.main_ideology}")
                self.cultural_influence[other.name] = 0

    def _update_politics(self, year):
        if self.government == "民主":
            if year >= self.election_year:
                self.election_year += random.randint(4, 6)
                self.party_support += random.uniform(-0.2, 0.2)
                self.party_support = max(0.1, min(0.9, self.party_support))
                self.world.log(f"🗳️ {self.name} 举行大选，执政党支持率 {self.party_support:.2f}")
                if self.party_support < 0.3: self.stability -= 0.1
        elif self.government == "威权":
            self.party_support -= 0.01
            if random.random() < 0.05:
                self.world.log(f"⚡ {self.name} 爆发反威权抗议")
                self.stability -= 0.05
        if self.government != "民主" and self.stability < 0.3 and random.random() < 0.02:
            self._coup()

    def _coup(self):
        old_gov = self.government
        new_gov = random.choice(["民主", "威权", "混合"])
        self.government = new_gov
        self.stability = 0.4; self.party_support = 0.5
        self.world.log(f"💥 {self.name} 发生政变！政府由{old_gov}转为{new_gov}")
        if self.government == "威权":
            for al in self.world.alliances.alliances:
                if al.has(self.name) and al.name in ["北约", "欧盟"]:
                    al.members.remove(self.name)
                    self.world.log(f"🚫 {self.name} 因政变被{al.name}开除")

def get_ai_state(world, country):
    env = world.global_environment
    gdp_growth = (country.gdp - country._prev_gdp) / max(1, country._prev_gdp)
    stability = country.stability
    max_military = max([c.military_power() for c in world.countries if c.alive and c.name != country.name], default=1)
    mil_ratio = country.military_power() / max_military
    env_state = 0 if env > 60 else 1 if env > 30 else 2
    growth_state = 0 if gdp_growth > 0.03 else 1 if gdp_growth > 0 else 2
    stability_state = 0 if stability > 0.7 else 1 if stability > 0.4 else 2
    mil_state = 0 if mil_ratio > 1.2 else 1 if mil_ratio > 0.8 else 2
    early_flag = 0 if world.year < 1920 else 1
    return (env_state, growth_state, stability_state, mil_state, early_flag)

def apply_ai_action(world, country, action):
    budget_choice, war_choice = divmod(action, 2)
    if world.year <= 2025: war_choice = 0
    if budget_choice == 0:
        country.research_budget = max(1, country.research_budget * 0.9)
        world.log(f"🤖 AI {country.name} 选择低科研预算")
    elif budget_choice == 1:
        world.log(f"🤖 AI {country.name} 保持中等科研预算")
    else:
        country.research_budget = min(25, country.research_budget * 1.1)
        world.log(f"🤖 AI {country.name} 选择高科研预算")
    if war_choice == 1:
        enemies = [c for c in world.countries if c.alive and c.name != country.name and world.alliances.can_war(country.name, c.name, world.year)]
        if enemies:
            target = random.choice(enemies)
            world._war_direct(country, target, 0.2)
            world.log(f"🤖 AI {country.name} 主动进攻 {target.name}")
        else:
            world.log(f"🤖 AI {country.name} 试图开战但无合法目标")

def get_reward(world, country, prev_stability, prev_gdp):
    reward = (country.stability - prev_stability) * 10
    gdp_growth = (country.gdp - prev_gdp) / max(1, prev_gdp)
    reward += gdp_growth * 10
    reward += (world.global_environment - 50) * 0.1
    if world.global_environment < 40: reward += country.env_pressure * 5
    reward += country.research_budget * 0.2
    alive = [c for c in world.countries if c.alive]
    if alive:
        avg_rb = sum(c.research_budget for c in alive) / len(alive)
        if country.research_budget > avg_rb * 1.2: reward += 2
        elif country.research_budget < avg_rb * 0.8: reward -= 1
    if country.ai_controlled:
        serv_ratio = country.service_gdp / max(1, country.gdp)
        if serv_ratio < 0.1: reward -= 5
    return reward

def ai_decision(world, country, initial_epsilon=0.3):
    state = get_ai_state(world, country)
    years_passed = max(1, world.year - 1900)
    epsilon = max(0.02, initial_epsilon * (0.995 ** years_passed))
    if state not in q_table: q_table[state] = {a: 0.0 for a in range(6)}
    if random.random() < epsilon: action = random.choice(list(q_table[state].keys()))
    else: action = max(q_table[state], key=q_table[state].get)
    return action

class World:
    def __init__(self, **kwargs):
        self.year = 1900
        self.countries = []
        self.knowledge = KnowledgeTree(self)
        self.global_environment = 100.0
        self.events_log = []
        self.alliances = AllianceSystem()
        self.resource_market = ResourceMarket()
        self.proxy_war_system = ProxyWarSystem(self.alliances)
        self.expected_environment = 100.0
        self.env_history = []
        self.gdp_history = []; self.pop_history = []
        self.max_gdp = kwargs.get("max_gdp", 120000)
        self.war_prob = kwargs.get("war_prob", 0.0166)
        self.proxy_prob = kwargs.get("proxy_prob", 0.0154)
        self.emergence_prob = kwargs.get("emergence_prob", 0.0309)
        self.civilization_ended = False
        self._apply_historical = kwargs.get("apply_historical", False)
        self.waste_accumulation = 0.0
        self.multinationals = []
        self.ingos = []
        self.nsags = []
        self.ecosystem = Ecosystem()
        try: self.real_data = pd.read_csv("historical_data_real.csv")
        except: self.real_data = None
        if not kwargs.get("no_init", False): self._init_1900()

    def to_dict(self):
        return {
            "year": self.year, "global_environment": self.global_environment,
            "expected_environment": self.expected_environment, "max_gdp": self.max_gdp,
            "war_prob": self.war_prob, "proxy_prob": self.proxy_prob, "emergence_prob": self.emergence_prob,
            "knowledge": {
                "math": self.knowledge.math, "physics": self.knowledge.physics,
                "chemistry": self.knowledge.chemistry, "biology": self.knowledge.biology,
                "medicine": self.knowledge.medicine, "agriculture": self.knowledge.agriculture,
                "philosophy": self.knowledge.philosophy, "sociology": self.knowledge.sociology,
                "energy_tech": self.knowledge.energy_tech, "environment_tech": self.knowledge.environment_tech,
                "industry_tech": self.knowledge.industry_tech, "information_tech": self.knowledge.information_tech,
                "space_tech": self.knowledge.space_tech, "ai_tech": self.knowledge.ai_tech,
                "global_green_policy": self.knowledge.global_green_policy,
                "scientific_knowledge": self.knowledge.scientific_knowledge,
                "quantum_tech": self.knowledge.quantum_tech,
                "unlocked_nodes": [n.name for n in self.knowledge.tech_tree.nodes if n.unlocked]
            },
            "countries": [{
                "name": c.name, "region": c.region, "alive": c.alive,
                "pop_children": c.pop_children, "pop_young": c.pop_young,
                "pop_middle": c.pop_middle, "pop_old": c.pop_old,
                "material_gdp": c.material_gdp, "service_gdp": c.service_gdp,
                "tech_level": c.tech_level, "research_budget": c.research_budget,
                "stability": c.stability, "aggression": c.aggression,
                "ideology": c.ideology, "camp": c.camp, "resources": c.resources,
                "war_victory_bonus": c.war_victory_bonus, "war_defeat_penalty": c.war_defeat_penalty,
                "last_war_year": c.last_war_year, "democracy_movement_cd": c.democracy_movement_cd,
                "education": c.education, "food_reserve": c.food_reserve,
                "trade_partners": list(c.trade_partners), "government": c.government,
                "party_support": c.party_support, "election_year": c.election_year,
                "language": c.language, "religion": c.religion, "main_ideology": c.main_ideology,
                "ai_controlled": c.ai_controlled, "cultural_influence": c.cultural_influence,
                "is_federal": c.is_federal, "federal_age": c.federal_age,
                "debt": c.debt, "interest_rate": c.interest_rate, "constitution": c.constitution,
                "internal_agents": [{"name": a.name, "type": a.type, "power": a.power, "wealth": a.wealth, "goal": a.goal, "alive": a.alive} for a in c.internal_agents]
            } for c in self.countries],
            "resource_market": {"prices": self.resource_market.prices, "trade_agreements": self.resource_market.trade_agreements},
            "events_log": self.events_log[-100:], "waste_accumulation": self.waste_accumulation,
            "multinationals": [{"name": m.name, "home_country": m.home_country, "power": m.power, "wealth": m.wealth, "branches": m.branches, "alive": m.alive} for m in self.multinationals],
            "ingos": [{"name": i.name, "focus": i.focus, "influence": i.influence, "resources": i.resources, "alive": i.alive} for i in self.ingos],
            "nsags": [{"name": n.name, "type": n.type, "base_country": n.base_country, "strength": n.strength, "alive": n.alive} for n in self.nsags]
        }

    @classmethod
    def from_dict(cls, state):
        world = cls(no_init=True)
        world.year = state["year"]; world.global_environment = state["global_environment"]
        world.expected_environment = state.get("expected_environment", 100.0)
        world.max_gdp = state.get("max_gdp", 120000)
        world.war_prob = state.get("war_prob", 0.0166); world.proxy_prob = state.get("proxy_prob", 0.0154)
        world.emergence_prob = state.get("emergence_prob", 0.0309)
        world.waste_accumulation = state.get("waste_accumulation", 0.0)
        kn = state["knowledge"]; world.knowledge = KnowledgeTree(world)
        for attr in ["math","physics","chemistry","biology","medicine","agriculture","philosophy","sociology",
                     "energy_tech","environment_tech","industry_tech","information_tech","space_tech","ai_tech",
                     "global_green_policy","scientific_knowledge","quantum_tech"]:
            setattr(world.knowledge, attr, kn.get(attr, 0))
        for node in world.knowledge.tech_tree.nodes:
            if node.name in kn.get("unlocked_nodes", []): node.unlocked = True
        for cd in state["countries"]:
            total_pop = cd.get("pop_children", 0) + cd.get("pop_young", 0) + cd.get("pop_middle", 0) + cd.get("pop_old", 0)
            if total_pop == 0: total_pop = cd.get("population", 10)
            c = Country(world, cd["name"], cd["region"], total_pop, cd["material_gdp"]+cd["service_gdp"],
                        cd["resources"], cd["tech_level"], cd["research_budget"], cd["ideology"], cd["camp"],
                        cd.get("government","混合"), cd.get("party_support",0.5), cd.get("election_year",world.year+4),
                        language=cd.get("language","英语"), religion=cd.get("religion","基督教"),
                        main_ideology=cd.get("main_ideology","自由主义"), ai_controlled=cd.get("ai_controlled", False),
                        constitution=cd.get("constitution", "standard"))
            c.alive = cd["alive"]
            c.pop_children = cd.get("pop_children", total_pop * 0.35); c.pop_young = cd.get("pop_young", total_pop * 0.40)
            c.pop_middle = cd.get("pop_middle", total_pop * 0.20); c.pop_old = cd.get("pop_old", total_pop * 0.05)
            c.material_gdp = cd["material_gdp"]; c.service_gdp = cd["service_gdp"]
            c.stability = cd["stability"]; c.aggression = cd.get("aggression", 0.3)
            c.war_victory_bonus = cd.get("war_victory_bonus", 0); c.war_defeat_penalty = cd.get("war_defeat_penalty", 0)
            c.last_war_year = cd.get("last_war_year", 0); c.democracy_movement_cd = cd.get("democracy_movement_cd", 0)
            c.education = cd.get("education", 0.3); c.food_reserve = cd.get("food_reserve", 0.5)
            c.trade_partners = set(cd.get("trade_partners", []))
            c.is_federal = cd.get("is_federal", False); c.federal_age = cd.get("federal_age", 0)
            c.debt = cd.get("debt", 0.0); c.interest_rate = cd.get("interest_rate", 0.03)
            c.internal_agents = []
            for ad in cd.get("internal_agents", []):
                agent = InternalAgent(ad["name"], ad["type"], ad["power"], ad.get("wealth", 0), ad.get("goal", "profit"))
                agent.alive = ad.get("alive", True); c.internal_agents.append(agent)
            c.cultural_influence = cd.get("cultural_influence", {})
            world.countries.append(c)
        rm = state.get("resource_market", {})
        world.resource_market.prices = rm.get("prices", world.resource_market.prices)
        world.resource_market.trade_agreements = rm.get("trade_agreements", [])
        world.events_log = state.get("events_log", [])
        world.multinationals = []
        for md in state.get("multinationals", []):
            m = MultinationalCorp(md["name"], md["home_country"], md.get("power", 0.3), md.get("wealth", 100))
            m.branches = md.get("branches", []); m.alive = md.get("alive", True); world.multinationals.append(m)
        world.ingos = []
        for ingo_dict in state.get("ingos", []):
            ingo = INGO(ingo_dict["name"], ingo_dict["focus"], ingo_dict.get("influence", 0.2))
            ingo.resources = ingo_dict.get("resources", 50); ingo.alive = ingo_dict.get("alive", True); world.ingos.append(ingo)
        world.nsags = []
        for nd in state.get("nsags", []):
            nsag = NonStateArmedGroup(nd["name"], nd["type"], nd["base_country"], nd.get("strength", 10))
            nsag.alive = nd.get("alive", True); world.nsags.append(nsag)
        return world

    def _init_1900(self):
        data = [
            ("华夏","东亚",400,50,{"煤炭":80,"铁矿":60,"稀土":90},0.3,0.8092,0,0,"混合",0.5,1904,"汉语","无宗教","共产主义", True, "standard"),
            ("美利坚","北美",76,120,{"石油":70,"铁矿":50},0.7,0.8092,1,1,"民主",0.6,1904,"英语","基督教","自由主义", True, "standard"),
            ("俄罗斯","东欧",120,40,{"石油":90,"天然气":80,"铁矿":40},0.4,0.8092,-1,0,"威权",0.7,1905,"俄语","东正教","威权主义", True, "standard"),
            ("不列颠","西欧",41,60,{"煤炭":70,"铁矿":40},0.6,0.8092,1,1,"民主",0.55,1906,"英语","基督教","自由主义", False, "standard"),
            ("法兰西","西欧",38,40,{"铁矿":50,"煤炭":30},0.5,0.8092,1,1,"民主",0.5,1906,"法语","基督教","自由主义", False, "standard"),
            ("德意志","中欧",56,55,{"煤炭":80,"铁矿":70},0.6,0.8092,0,0,"威权",0.8,1907,"德语","基督教","民族主义", False, "standard"),
            ("日本","东亚",44,30,{"煤炭":10},0.5,0.8092,0,0,"威权",0.9,1908,"日语","佛教","民族主义", False, "pacifist"),
            ("意大利","南欧",32,20,{"煤炭":20,"铁矿":20},0.4,0.8092,0,0,"混合",0.4,1904,"意大利语","基督教","自由主义", False, "standard"),
            ("奥匈","中欧",45,25,{"煤炭":40,"铁矿":30},0.4,0.8092,0,0,"威权",0.6,1907,"德语","基督教","民族主义", False, "standard"),
            ("奥斯曼","中东",25,15,{"石油":40},0.3,0.8092,-1,0,"威权",0.7,1905,"阿拉伯语","伊斯兰教","民族主义", False, "standard"),
            ("印度","南亚",280,30,{"煤炭":60},0.3,0.8092,0,0,"混合",0.3,1905,"印地语","印度教","民族主义", False, "standard"),
            ("巴西","南美",18,10,{"森林":90,"铁矿":30},0.3,0.8092,0,0,"混合",0.5,1906,"葡萄牙语","基督教","社会民主主义", False, "standard"),
            ("加拿大","北美",5,8,{"森林":70},0.5,0.8092,1,1,"民主",0.6,1904,"英语","基督教","自由主义", False, "standard"),
            ("澳大利亚","大洋洲",4,6,{"煤炭":30,"铁矿":40},0.5,0.8092,1,1,"民主",0.55,1907,"英语","基督教","自由主义", False, "standard"),
            ("阿根廷","南美",8,5,{"农业":70},0.4,0.8092,0,0,"混合",0.4,1905,"西班牙语","基督教","社会民主主义", False, "standard"),
        ]
        mult_homes = ["美利坚", "不列颠", "德意志"]
        for i, home in enumerate(mult_homes):
            self.multinationals.append(MultinationalCorp(f"{home}跨国集团{i}", home, random.uniform(0.3, 0.5), random.uniform(150, 300)))
        self.ingos.append(INGO("国际绿色和平", "environment", 0.4))
        self.ingos.append(INGO("人权观察", "human_rights", 0.3))
        self.ingos.append(INGO("全球卫生基金会", "health", 0.35))
        for it in data:
            name, region, pop, gdp, res, tech, rb, ideo, camp, gov, sup, elec, lang, rel, ide, ai, const = it
            c = Country(self, name, region, pop, gdp, res, tech, rb, ideo, camp, gov, sup, elec,
                        language=lang, religion=rel, main_ideology=ide, ai_controlled=ai, constitution=const)
            self.countries.append(c)
            c.spawn_agents()
            c.spawn_households(100)

    def log(self,m): self.events_log.append(f"[{self.year}] {m}")
    def find(self,n):
        for c in self.countries:
            if c.name==n and c.alive: return c
        return None
    def spawn(self,n,r,pop,gdp,res,tech,rb,ideo,camp,gov="混合",sup=0.5,elec=0,lang="英语",rel="基督教",ide="自由主义"):
        if not self.find(n):
            if elec == 0: elec = self.year + random.randint(3,5)
            c = Country(self,n,r,pop,gdp,res,tech,rb,ideo,camp,gov,sup,elec, language=lang, religion=rel, main_ideology=ide)
            c.spawn_agents()
            c.spawn_households(100)
            self.countries.append(c)
            self.log(f"🆕 {n} 建立（{gov}）")
    def remove(self,n):
        c = self.find(n)
        if c: c.alive=False; self.log(f"💔 {n} 不复存在")

    def _refugee_crisis(self):
        for country in self.countries:
            if not country.alive: continue
            refugee_out = 0
            if self.global_environment < 15 and country.stability < 0.5:
                refugee_out = country.population * 0.05
            elif country.stability < 0.2:
                refugee_out = country.population * 0.03
            elif country.population <= 0.5:
                refugee_out = country.population * 0.1
            if refugee_out > 0:
                alive_others = [c for c in self.countries if c.alive and c.name != country.name]
                if not alive_others: continue
                alive_others.sort(key=lambda c: ((country.latitude - c.latitude)**2 + (country.longitude - c.longitude)**2)**0.5)
                receivers = alive_others[:3]
                total_dist = sum(((country.latitude - r.latitude)**2 + (country.longitude - r.longitude)**2)**0.5 for r in receivers)
                if total_dist == 0: total_dist = 1
                for r in receivers:
                    dist = ((country.latitude - r.latitude)**2 + (country.longitude - r.longitude)**2)**0.5
                    share = (1 - dist / total_dist)
                    inflow = refugee_out * share
                    r.pop_young += inflow * 0.8; r.pop_middle += inflow * 0.2
                    r.stability -= 0.02
                country.population -= refugee_out
                self.log(f"🚶 {country.name} 产生难民潮，约 {refugee_out:.1f}M 人逃往邻国")

    def _spawn_nsags_from_chaos(self):
        for c in self.countries:
            if c.alive and c.stability < 0.3 and random.random() < 0.002:
                existing = [g for g in self.nsags if g.base_country == c.name and g.alive]
                if len(existing) < 2:
                    gtype = random.choice(["guerrilla", "terrorist"])
                    g = NonStateArmedGroup(f"{c.name}{gtype}组织", gtype, c.name, random.uniform(5,15))
                    self.nsags.append(g)
                    self.log(f"💣 {c.name} 境内出现{gtype}组织：{g.name}")

    def _force_historical(self):
        if not self._apply_historical or self.real_data is None or self.year > 2025: return
        year_data = self.real_data[self.real_data['year'] == self.year]
        if year_data.empty: return
        total_co2 = 0.0
        for _, row in year_data.iterrows():
            c = self.find(row['country'])
            if c and c.alive:
                if pd.isna(row['gdp']) or pd.isna(row['population']): continue
                old_ratio = c.material_gdp / max(1, c.gdp)
                c.population = row['population']; c.material_gdp = row['gdp'] * old_ratio
                c.service_gdp = row['gdp'] * (1 - old_ratio); total_co2 += row.get('co2', 0)
                if c.ai_controlled: c.aggression = 0.05; c.research_budget = min(c.research_budget, 10)
        cumulative_co2_factor = min(1.0, total_co2 / 50)
        target_env = 100 - cumulative_co2_factor * 40
        self.global_environment = target_env
        self.expected_environment = 0.7 * self.global_environment + 0.3 * self.expected_environment

    def run_year(self):
        if self.civilization_ended: return False
        self.year += 1
        for c in self.countries:
            if c.alive and c.ai_controlled:
                prev_stability = c.stability; prev_gdp = c.gdp
                state = get_ai_state(self, c); action = ai_decision(self, c)
                apply_ai_action(self, c, action)
                ai_memory[c.name] = (state, action, prev_stability, prev_gdp)
        self._history()
        self.knowledge.update(self.countries, self.year)
        for c in [c for c in self.countries if c.alive]: c.internal_development()
        self.resource_market.update(self.countries)
        if random.random()<0.1: self.resource_market.negotiate_trade(self)
        for mcorp in self.multinationals:
            if mcorp.alive: mcorp.expand(self)
        for ingo in self.ingos:
            if ingo.alive: ingo.act(self)
        self._refugee_crisis()
        for nsag in self.nsags:
            if nsag.alive: nsag.act(self)
        self._diplomacy()
        self._environment()
        self._emergence()
        self._random()
        self._force_historical()
        self._spawn_nsags_from_chaos()
        total_gdp = sum(c.gdp for c in self.countries if c.alive)
        self.ecosystem.update(self.waste_accumulation, total_gdp)
        raw_env = self.ecosystem.overall_health
        self.global_environment = max(0, min(100, raw_env))
        self.countries = [c for c in self.countries if c.alive]
        if not self.countries:
            self.civilization_ended = True
            self.log("☠️ 人类文明终结。")
        self.env_history.append(self.global_environment)
        total_gdp = sum(c.gdp for c in self.countries if c.alive)
        total_pop = sum(c.population for c in self.countries if c.alive)
        self.gdp_history.append(total_gdp); self.pop_history.append(total_pop)
        if len(self.env_history) > 1000: self.env_history = self.env_history[-500:]
        for c in self.countries:
            if c.alive and c.ai_controlled and c.name in ai_memory:
                state, action, prev_stab, prev_gdp = ai_memory.pop(c.name)
                reward = get_reward(self, c, prev_stab, prev_gdp)
                if state in q_table:
                    old_q = q_table[state][action]
                    next_state = get_ai_state(self, c)
                    next_max = max(q_table.get(next_state, {a:0 for a in range(6)}).values())
                    q_table[state][action] = old_q + 0.1 * (reward + 0.9 * next_max - old_q)
        for c in self.countries:
            if c.alive and c.ai_controlled: c._prev_gdp = c.gdp; c._prev_stability = c.stability
        for c in self.countries:
            if c.alive and c.stability < 0: c.stability = 0.01
            elif c.alive: c.stability = max(0.0, min(1.0, c.stability))
        return True

    def _history(self):
        y = self.year
        if y==1914: self.log("🌍 一战爆发"); self._script_war(["不列颠","法兰西","俄罗斯","意大利","美利坚"],["德意志","奥匈","奥斯曼"],0.5)
        if y==1917 and random.random()<0.95:
            rus=self.find("俄罗斯");
            if rus: rus.ideology=-1; rus.government="威权"
        if y==1918:
            self.remove("奥匈"); self.spawn("奥地利","中欧",6,3,{},0.4,2,0,0,"民主",0.5,self.year+3,"德语","基督教","自由主义")
            self.spawn("匈牙利","中欧",7,2,{},0.4,2,0,0,"混合",0.4,self.year+3,"匈牙利语","基督教","民族主义")
            self.spawn("捷克斯洛伐克","中欧",13,5,{},0.5,3,1,0,"民主",0.6,self.year+4,"捷克语","基督教","自由主义")
            self.remove("奥斯曼"); self.spawn("土耳其","中东",14,4,{"石油":10},0.4,2,0,0,"混合",0.5,self.year+2,"土耳其语","伊斯兰教","民族主义")
            for n in ["德意志","奥地利","匈牙利","土耳其"]:
                c=self.find(n)
                if c: c.war_defeat_penalty=0.005
            for n in ["不列颠","法兰西","意大利","美利坚"]:
                c=self.find(n)
                if c: c.war_victory_bonus=0.003
        if y==1922 and self.find("俄罗斯") and self.find("俄罗斯").ideology<0:
            self.find("俄罗斯").name="苏联"; self.log("苏联成立")
        if y==1929: self.log("📉 大萧条"); [setattr(c,'material_gdp',c.material_gdp*0.8) for c in self.countries]
        if y==1933:
            ger=self.find("德意志")
            if ger: ger.ideology=-1; ger.government="威权"
        if y==1939:
            self.log("🌍 二战爆发")
            self._script_war(["不列颠","法兰西","苏联","美利坚","华夏"],["德意志","意大利","日本"],0.7)
        if y==1945:
            for n in ["美利坚","苏联","不列颠","法兰西","华夏"]:
                c=self.find(n)
                if c: c.war_victory_bonus=0.008
            for n in ["德意志","意大利","日本"]:
                c=self.find(n)
                if c:
                    c.war_defeat_penalty=0.01; c.stability-=0.05
                    if n != "日本": c.government = "民主"
            ger=self.find("德意志")
            if ger: ger.name="西德"; self.spawn("东德","中欧",16,4,{},0.5,2,-1,2,"威权",0.6,self.year+3,"德语","无宗教","共产主义")
            jap=self.find("日本")
            if jap: jap.ideology=1; jap.government="民主"
        if y==1947:
            ind=self.find("印度")
            if ind: self.spawn("巴基斯坦","南亚",30,3,{},0.3,1,0,0,"混合",0.4,self.year+2,"乌尔都语","伊斯兰教","民族主义")
        if y==1948: self.spawn("以色列","中东",1,2,{},0.6,5,1,0,"民主",0.6,self.year+4,"希伯来语","犹太教","民族主义")
        if y==1949:
            chi=self.find("华夏")
            if chi: chi.ideology=-1; chi.camp=2; chi.government="威权"
        if y==1962: self.log("🚀 古巴导弹危机")
        if y==1973: self.log("⛽ 石油危机"); [setattr(c,'material_gdp',c.material_gdp*0.95) for c in self.countries if "石油" not in c.resources]
        if y==1978:
            chi=self.find("华夏")
            if chi: chi.ideology=0; chi.government="混合"
        if y==1989: self.log("🧱 柏林墙倒塌")
        if y==1991:
            sov=self.find("苏联")
            if sov:
                sov.name="俄罗斯"; sov.ideology=0; sov.government="混合"
                self.spawn("乌克兰","东欧",52,10,{"煤炭":30},0.4,2,0,0,"混合",0.5,self.year+4,"乌克兰语","东正教","民族主义")
                self.spawn("白俄罗斯","东欧",10,3,{},0.4,1,0,0,"威权",0.6,self.year+3,"白俄罗斯语","东正教","威权主义")
                self.spawn("哈萨克斯坦","中亚",16,2,{"石油":20},0.3,1,0,0,"威权",0.7,self.year+5,"哈萨克语","伊斯兰教","威权主义")
            self.remove("东德"); wg=self.find("西德")
            if wg: wg.name="德意志"; wg.government="民主"
        if y==1993: self.log("🇪🇺 欧盟成立")
        if y==2001: self.log("✈️ 911")
        if y==2008: self.log("🏦 金融危机"); [setattr(c,'material_gdp',c.material_gdp*0.92) for c in self.countries]
        if y==2020:
            self.log("🦠 新冠疫情")
            for c in self.countries: c.population*=0.95; c.material_gdp*=0.94
            self.knowledge.medicine+=0.5
        if y==2023: self.log("🤖 AI突破"); self.knowledge.ai_tech+=1.5

    def _script_war(self,a_list,b_list,intensity):
        for a in a_list:
            for b in b_list:
                ca=self.find(a); cb=self.find(b)
                if ca and cb: self._war_direct(ca,cb,intensity)

    def _war_direct(self, attacker, defender, scale):
        if attacker.constitution == "pacifist" and scale > 0:
            self.log(f"🕊️ {attacker.name} 受和平宪法约束，无法主动进攻")
            return
        allies = self.alliances.defend(defender, attacker, self.year, self)
        for ally in allies: self.log(f"⚔️ {ally.name} 因联盟义务加入防御 {defender.name}")
        ap = attacker.military_power()
        total_dp = defender.military_power() + sum(a.military_power() for a in allies) * 0.7
        if ap > total_dp * 1.3:
            defender.material_gdp *= (1 - 0.1 * scale)
            defender.population *= (1 - 0.03 * scale)
            defender.stability -= 0.15 * scale
            attacker.material_gdp += defender.material_gdp * 0.04
            self.global_environment -= 0.5 * scale
            self.log(f"⚔️ {attacker.name} 击败 {defender.name}")
        else:
            attacker.material_gdp *= (1 - 0.06 * scale)
            defender.material_gdp *= (1 - 0.04 * scale)
            self.global_environment -= 0.25 * scale

    def _diplomacy(self):
        alive=[c for c in self.countries if c.alive]
        if len(alive)<2: return
        if self.year>=1945 and random.random()<0.15:
            self.log("🌐 联合国气候峰会")
            self.knowledge.global_green_policy+=0.03
        if random.random()<self.proxy_prob: self.proxy_war_system.attempt(self)
        for i in range(len(alive)):
            for j in range(i+1,len(alive)):
                a,b=alive[i],alive[j]
                a.trade_partners.add(b.name); b.trade_partners.add(a.name)
                if (self.alliances.can_war(a.name,b.name,self.year) and random.random()<self.war_prob * 0.5):
                    if (self.year - a.last_war_year > 5 and self.year - b.last_war_year > 5):
                        if (a.stability<0.5 or b.stability<0.5 or a.aggression>0.7 or b.aggression>0.7):
                            self._war_direct(a,b,0.2)
                            a.last_war_year = self.year; b.last_war_year = self.year

    def _environment(self):
        alive = [c for c in self.countries if c.alive]
        if not alive:
            self.global_environment += 0.5
            self.global_environment = min(100, self.global_environment)
            return
        emission = sum(c.material_gdp * 0.000012 * (1 - self.knowledge.green_ratio()) for c in alive)
        natural = 0.03 * (100 - self.global_environment) / 100
        repair = self.knowledge.env_repair_rate() * 0.3
        self.global_environment += -emission + natural + repair
        if self.knowledge.green_ratio() < 0.8:
            if 1920 <= self.year <= 2020: self.global_environment -= 0.05
            elif 2021 <= self.year <= 2050: self.global_environment -= 0.1
        waste_penalty = self.waste_accumulation * 0.001
        self.global_environment -= waste_penalty
        self.waste_accumulation *= 0.9995
        total_global_gdp = sum(c.gdp for c in alive)
        if total_global_gdp > 300000:
            self.global_environment -= 0.3
            if random.random() < 0.1: self.log("🌪️ 全球经济过热导致环境加速恶化")
        if self.global_environment < 40 and random.random() < 0.5:
            self.knowledge.global_green_policy += 0.08
            self.knowledge.environment_tech = min(10, self.knowledge.environment_tech + 1.0)
            self.knowledge.energy_tech = min(10, self.knowledge.energy_tech + 0.5)
            self.log("🌿 全球紧急生态修复行动启动")
        if self.global_environment > 90 and random.random() < 0.01:
            self.global_environment -= random.uniform(2, 5)
            self.log("🌍 行星边界反馈：气候系统扰动")
        if random.random() < 0.005:
            disaster = random.choice(["小行星撞击", "超级火山", "太阳风暴"])
            self.global_environment -= random.uniform(10, 20)
            self.log(f"☄️ 全球灾难：{disaster}！环境遭受重创")
        self.global_environment = max(0, min(100, self.global_environment))
        self.expected_environment = 0.7 * self.global_environment + 0.3 * self.expected_environment
        if self.expected_environment < 50: self.knowledge.global_green_policy += 0.005
        if self.global_environment < 15 and random.random() < 0.1:
            self.log("☠️ 局部生态崩溃")
            for c in alive: c.population *= 0.9; c.stability -= 0.1
        if abs(self.expected_environment - self.global_environment) > 20:
            adjustment = (self.expected_environment - self.global_environment) * 0.001
            self.knowledge.global_green_policy += adjustment
            if abs(adjustment) > 0.005: self.log("⚛️ 政策过度反应")

    def _emergence(self):
        if random.random()<self.emergence_prob:
            m=random.choice(["全球气候罢课","开源绿色能源革命","反战和平运动","去中心化科研浪潮",
                             "基本收入实验推广","全球大流行病变种预警","气候工程意外后果讨论",
                             "AI伦理国际公约","太空资源开发倡议","量子互联网雏形"])
            self.log(f"🌱 涌现事件：{m}")
            if "气候罢课" in m: self.knowledge.global_green_policy+=0.05
            elif "绿色能源" in m: self.knowledge.energy_tech+=0.5
            elif "和平" in m: [setattr(c,'aggression',c.aggression*0.9) for c in self.countries]
            elif "科研" in m: self.knowledge.scientific_knowledge+=0.5
            elif "基本收入" in m: [setattr(c,'stability',c.stability+0.05) for c in self.countries]
            elif "大流行病变种" in m:
                for c in self.countries: c.population*=0.97; c.material_gdp*=0.96
                self.knowledge.medicine+=0.4; self.log("  ↳ 引发新一轮医学研究投入")
            elif "气候工程意外" in m:
                self.global_environment+=random.choice([-5,3])
                self.knowledge.global_green_policy+=0.03
            elif "AI伦理" in m:
                [setattr(c,'aggression',c.aggression*0.95) for c in self.countries]; self.knowledge.sociology+=0.3
            elif "太空资源" in m: self.knowledge.space_tech+=0.5; self.knowledge.industry_tech+=0.2
            elif "量子互联网" in m: self.knowledge.quantum_tech+=0.8; self.knowledge.information_tech+=0.5
        if self.year >= 2100 and self.knowledge.ai_tech >= 10 and self.knowledge.quantum_tech >= 10 and self.knowledge.scientific_knowledge >= 10:
            if random.random() < 0.002:
                self.knowledge.scientific_knowledge = min(15, self.knowledge.scientific_knowledge + 2)
                self.knowledge.ai_tech = min(15, self.knowledge.ai_tech + 2)
                self.knowledge.quantum_tech = min(15, self.knowledge.quantum_tech + 2)
                self.log("💡 技术奇点发生！基础科学取得突破性进展，开启新时代")

    def _random(self):
        if random.random()<0.04:
            ev=random.choice(["大萧条","疫情","技术突破","资源发现"])
            self.log(f"🌐 {ev}")
            alive=[c for c in self.countries if c.alive]
            if ev=="大萧条": [setattr(c,'material_gdp',c.material_gdp*0.9) for c in alive]
            elif ev=="疫情": [setattr(c,'population',c.population*0.93) for c in alive]; self.knowledge.medicine+=0.2
            elif ev=="技术突破":
                tech=random.choice(["energy_tech","information_tech","ai_tech","environment_tech"])
                setattr(self.knowledge,tech,min(10,getattr(self.knowledge,tech)+1))
            elif ev=="资源发现":
                res=random.choice(["石油","天然气","锂","稀土","铀"])
                for c in random.sample(alive,min(3,len(alive))): c.resources[res]=c.resources.get(res,0)+30

    def monte_carlo_prediction(self, num_simulations=100, years=80):
        futures = {self.year + y: [] for y in range(years+1)}
        for _ in range(num_simulations):
            w = copy.deepcopy(self)
            for _ in range(years):
                w.run_year()
            futures[self.year + years].append(w.global_environment)
        result = {}
        for y, values in futures.items():
            result[y] = (np.mean(values), np.percentile(values, 10), np.percentile(values, 90))
        return result

    def show_env_trend(self):
        if not self.env_history: return
        print(" 环境趋势 (最近20年):")
        max_env = max(self.env_history[-20:])
        for val in self.env_history[-20:]:
            bar_len = int(val/max(1,max_env)*20)
            print(f"  {val:5.1f} |{'█'*bar_len}")

    def status_report(self):
        era_name,_ = TechEra.get_era(self.knowledge.total_tech())
        print(f"\n{'='*60}")
        print(f" 地球模拟器 Pro++ · {self.year}年")
        print(f" 时代: {era_name} | 环境: {self.global_environment:.1f} | 清洁能源: {self.knowledge.green_ratio()*100:.0f}%")
        print(f" 国家: {len(self.countries)} | 修复力: {self.knowledge.env_repair_rate():.2f} | 科学知识: {self.knowledge.scientific_knowledge:.2f}")
        print(f" 量子科技: {self.knowledge.quantum_tech:.2f} | 预期环境: {self.expected_environment:.1f}")
        if self.civilization_ended: print("【文明已终结】")
        else:
            print(f"{'='*60}")
            for c in sorted(self.countries, key=lambda x: x.gdp, reverse=True)[:12]:
                s = "🟢" if c.stability>0.7 else "🟡" if c.stability>0.4 else "🔴"
                gov_short = {"民主":"民","威权":"威","混合":"混"}.get(c.government,"?")
                ai_tag = "🤖" if c.ai_controlled else ""
                fed_tag = "🏛️" if c.is_federal else ""
                print(f" {ai_tag}{fed_tag}{c.name:<10} 人口{c.population:.0f}M GDP{c.gdp:.0f}B (物{c.material_gdp:.0f}/服{c.service_gdp:.0f}) 稳{c.stability:.2f} [{gov_short}] {c.main_ideology[:2]} {s}")
        print(f"{'='*60}")
        if hasattr(self, 'multinationals') and self.multinationals:
            print(f"🏢 跨国公司: {len(self.multinationals)} 家")
            for m in self.multinationals[:5]: print(f"   {m.name} (母国: {m.home_country}) 分支数: {len(m.branches)}")
        if hasattr(self, 'ingos') and self.ingos:
            print(f"🌐 国际非政府组织: {len(self.ingos)} 家")
            for ingo in self.ingos[:5]: print(f"   {ingo.name} (焦点: {ingo.focus}) 资源: {ingo.resources:.1f}")
        if hasattr(self, 'nsags') and self.nsags:
            print(f"💣 非国家武装团体: {len(self.nsags)} 个")
            for g in self.nsags[:5]: print(f"   {g.name} (类型:{g.type}) 强度:{g.strength:.1f}")
        self.show_env_trend()
        print()

    def generate_report(self, filename=None):
        if filename is None: filename = f"report_{self.year}.html"
        wars = [e for e in self.events_log if "⚔️" in e]
        culture_events = [e for e in self.events_log if "🌍" in e and "战争" not in e and "爆发" not in e]
        tech_events = [e for e in self.events_log if "🔬" in e]
        emergence_events = [e for e in self.events_log if "🌱" in e]
        corp_events = [e for e in self.events_log if "🏢" in e or "🏛️" in e]
        ingo_events = [e for e in self.events_log if "📢" in e or "🚫" in e or "💊" in e]
        nsag_events = [e for e in self.events_log if "💣" in e or "💥" in e]
        env_trend = "上升" if len(self.env_history) >= 2 and self.env_history[-1] > self.env_history[0] else "下降"
        html = f"""<html><head><meta charset="utf-8"><title>人类世报告 {self.year}</title>
        <style>body{{font-family:sans-serif;max-width:800px;margin:auto;padding:20px;}}h1{{color:#333;}}h2{{border-bottom:1px solid #aaa;}}.stats{{display:flex;gap:20px;flex-wrap:wrap;}}.card{{background:#f5f5f5;padding:10px;border-radius:5px;}}</style></head>
        <body>
        <h1>地球模拟器 Pro++ 人类世报告</h1>
        <p><b>年份：</b>{self.year} &nbsp; | &nbsp; <b>时代：</b>{TechEra.get_era(self.knowledge.total_tech())[0]}</p>
        <div class="stats">
        <div class="card"><b>环境健康度</b><br>{self.global_environment:.1f} / 100<br><small>趋势：{env_trend}</small></div>
        <div class="card"><b>清洁能源占比</b><br>{self.knowledge.green_ratio()*100:.0f}%</div>
        <div class="card"><b>国家数量</b><br>{len(self.countries)}</div>
        <div class="card"><b>环境修复力</b><br>{self.knowledge.env_repair_rate():.2f}</div>
        <div class="card"><b>科学知识</b><br>{self.knowledge.scientific_knowledge:.2f}</div>
        </div>"""
        if self.countries:
            html += "<h2>强国概况（前5）</h2><table border='1' cellpadding='5' cellspacing='0'>"
            html += "<tr><th>国家</th><th>人口(M)</th><th>GDP(B)</th><th>稳定度</th><th>政体</th><th>意识形态</th></tr>"
            top5 = sorted([c for c in self.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:5]
            for c in top5:
                gov = {"民主":"民主","威权":"威权","混合":"混合"}.get(c.government, c.government)
                html += f"<tr><td>{c.name}{' 🤖' if c.ai_controlled else ''}</td><td>{c.population:.0f}</td><td>{c.gdp:.0f}</td><td>{c.stability:.2f}</td><td>{gov}</td><td>{c.main_ideology}</td></tr>"
            html += "</table>"
        else: html += "<h2>文明状态</h2><p>文明已终结，无存活国家。</p>"
        html += f"<h2>重大战争（最近20条）</h2><ul>"
        for w in wars[-20:]: html += f"<li>{w}</li>"
        if not wars: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>文化变迁（最近20条）</h2><ul>"
        for ce in culture_events[-20:]: html += f"<li>{ce}</li>"
        if not culture_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>科技突破（最近20条）</h2><ul>"
        for te in tech_events[-20:]: html += f"<li>{te}</li>"
        if not tech_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>涌现事件（最近20条）</h2><ul>"
        for ee in emergence_events[-20:]: html += f"<li>{ee}</li>"
        if not emergence_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>跨国公司活动（最近20条）</h2><ul>"
        for ce in corp_events[-20:]: html += f"<li>{ce}</li>"
        if not corp_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>国际组织行动（最近20条）</h2><ul>"
        for ie in ingo_events[-20:]: html += f"<li>{ie}</li>"
        if not ingo_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>非国家武装活动（最近20条）</h2><ul>"
        for ne in nsag_events[-20:]: html += f"<li>{ne}</li>"
        if not nsag_events: html += "<li>无记录</li>"
        html += "</ul>"
        html += "<p><em>本报告由地球模拟器 Pro++ 自动生成</em></p></body></html>"
        with open(filename, 'w', encoding='utf-8') as f: f.write(html)
        print(f"人类世报告已保存至 {filename}")
        return html

    def generate_biography(self, country_name, filename=None):
        country = self.find(country_name)
        if not country: return
        if filename is None: filename = f"biography_{country_name}_{self.year}.html"
        events = [e for e in self.events_log if country_name in e]
        html = f"""<html><head><meta charset="utf-8"><title>{country_name}传记 {self.year}</title>
        <style>body{{font-family:sans-serif;max-width:800px;margin:auto;padding:20px;}}h1{{color:#333;}}h2{{border-bottom:1px solid #aaa;}}.stat{{display:flex;gap:20px;flex-wrap:wrap;}}.card{{background:#f5f5f5;padding:10px;border-radius:5px;min-width:120px;}}</style></head>
        <body><h1>{country_name}国家传记</h1><p><b>年份：</b>{self.year} &nbsp; | &nbsp; <b>状态：</b>{'存活' if country.alive else '灭亡'}</p></body></html>"""
        with open(filename, 'w', encoding='utf-8') as f: f.write(html)
        return html

if __name__ == "__main__":
    print("🌍 地球模拟器 Pro++ 深度现实版")
    world = World()
    plotter = LivePlotter(world)
    world.status_report()
    while True:
        cmd = input("命令: next/run N/predict/set/save/load/gif/report/biography 国家/quit > ").strip()
        if cmd == "quit": break
        elif cmd == "next":
            if world.civilization_ended: continue
            world.run_year(); world.status_report(); plotter.update()
        elif cmd.startswith("run "):
            n = int(cmd.split()[1])
            for _ in range(n):
                if world.civilization_ended: break
                world.run_year(); plotter.update()
            world.status_report()
        elif cmd == "predict":
            futures = world.monte_carlo_prediction(50, 80)
            for y, (mean, p10, p90) in futures.items():
                print(f"{y}: 环境均值 {mean:.1f} (90%区间: {p10:.1f}-{p90:.1f})")
        elif cmd == "report": world.generate_report()
        else: print("?")