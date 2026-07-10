from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from earth_sim.world import World

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
    def __init__(self, world: Optional['World'] = None):
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