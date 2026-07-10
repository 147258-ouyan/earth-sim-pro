from __future__ import annotations
import numpy as np
import pandas as pd
import random
import copy
from collections import deque
from typing import List

from earth_sim.config.default_params import DEFAULT_PARAMS
from earth_sim.engine.config import COUNTRY_COORDS_SIM
from earth_sim.engine.ecosystem import Ecosystem
from earth_sim.engine.politics import PoliticalLegitimacy
from earth_sim.engine.finance import CentralBank, StockMarket
from earth_sim.engine.market import ResourceMarket
from earth_sim.engine.knowledge import KnowledgeTree, TechEra
from earth_sim.engine.alliance import AllianceSystem
from earth_sim.engine.warfare import ProxyWarSystem
from earth_sim.engine.agents.internal import InternalAgent, MultinationalCorp
from earth_sim.engine.agents.ingo import INGO
from earth_sim.engine.agents.nsag import NonStateArmedGroup
from earth_sim.engine.agents.individual import Household
from earth_sim.ai.qlearning import (
    q_table, ai_memory, get_ai_state, apply_ai_action, get_reward, ai_decision
)


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
        self.stability = 0.7 + random.random() * 0.2
        self.aggression = random.random() * 0.4 + 0.2
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
        return (self.gdp * 0.3 + labor * 0.25 + self.world.knowledge.industry_tech * 10) * (0.5 + self.stability)

    @staticmethod
    def env_growth_factor(env):
        if env < 10: return 0.01
        elif env < 20: return 0.03
        elif env < 40: return 0.06
        return (env - 10) / 90

    def cultural_difference(self, other):
        diff = 0.0
        if self.language != other.language: diff += 0.3
        if self.religion != other.religion: diff += 0.3
        if self.main_ideology != other.main_ideology: diff += 0.4
        return diff

    def spawn_agents(self):
        for i in range(random.randint(2, 5)):
            self.internal_agents.append(InternalAgent(
                f"{self.name}企业{i}", "corporation", random.uniform(0.1, 0.4), random.uniform(10, 100), "profit"))
        for i in range(random.randint(1, 3)):
            self.internal_agents.append(InternalAgent(
                f"{self.name}绿色组织{i}", "ngo", random.uniform(0.05, 0.3), random.uniform(1, 10), "environment"))
        for i in range(random.randint(1, 2)):
            goal = random.choice(["military", "technology", "profit"])
            self.internal_agents.append(InternalAgent(
                f"{self.name}游说团{i}", "lobby", random.uniform(0.1, 0.35), random.uniform(20, 80), goal))

    def spawn_households(self, num_households=100):
        for _ in range(num_households):
            self.households.append(Household(self))

    def internal_development(self):
        w = self.world; k = w.knowledge; market = w.resource_market; year = w.year
        p = w.params  # 参数字典

        env_factor = Country.env_growth_factor(w.global_environment)
        carrying_capacity = (p["carrying_capacity_base"] +
                             w.global_environment * p["carrying_capacity_env_coef"] +
                             k.agriculture * p["carrying_capacity_agri_coef"] +
                             k.medicine * p["carrying_capacity_med_coef"])

        # 家庭和金融市场
        for hh in self.households[:]:
            if not hh.update(self, env_factor):
                self.households.remove(hh)
        self.central_bank.update()
        self.stock_market.update()
        self.interest_rate = self.central_bank.base_interest_rate
        gdp_growth = (self.gdp - self._prev_gdp) / max(1, self._prev_gdp)
        self.legitimacy.update(gdp_growth)

        # 人口
        total_pop = self.population
        births = (self.pop_young * p["birth_rate_young"] + self.pop_middle * p["birth_rate_middle"]) * env_factor
        child_death = self.pop_children * (p["child_death_base"] / (1 + k.medicine * p["medicine_effect_child_death"])) * (1 / env_factor)
        death_young = self.pop_young * (p["death_young_base"] / (1 + k.medicine * p["medicine_effect_young"]))
        death_middle = self.pop_middle * (p["death_middle_base"] / (1 + k.medicine * p["medicine_effect_middle"]))
        death_old = self.pop_old * (p["death_old_base"] / (1 + k.medicine * p["medicine_effect_old"]))
        aging_to_young = self.pop_children * p["aging_to_young"]
        aging_to_middle = self.pop_young * p["aging_to_middle"]
        aging_to_old = self.pop_middle * p["aging_to_old"]
        self.pop_children += births - child_death - aging_to_young
        self.pop_young += aging_to_young - death_young - aging_to_middle
        self.pop_middle += aging_to_middle - death_middle - aging_to_old
        self.pop_old += aging_to_old - death_old
        for attr in ['pop_children', 'pop_young', 'pop_middle', 'pop_old']:
            setattr(self, attr, max(p["min_pop_group"], getattr(self, attr)))
        if total_pop > carrying_capacity:
            scale = carrying_capacity / total_pop
            self.pop_children *= scale; self.pop_young *= scale
            self.pop_middle *= scale; self.pop_old *= scale

        self.education = min(1, self.education + p["education_research_factor"] * self.research_budget)
        trade_multiplier = w.alliances.get_trade_boost(self.name, year)
        tech_spillover = w.alliances.get_tech_spillover(self.name, year, w)
        per_capita = self.gdp / max(1, self.population)

        # 收敛因子
        convergence_factor = 1.0
        if per_capita > p["convergence_per_capita_high"]:
            convergence_factor = p["convergence_factor_high"]
        elif per_capita > p["convergence_per_capita_mid"]:
            convergence_factor = p["convergence_factor_mid"]
        if per_capita < p["catchup_per_capita_low"] and self.population < p["catchup_pop_under"]:
            convergence_factor = p["convergence_factor_low"]

        # 物质GDP
        total_mat = sum(c.material_gdp for c in w.countries if c.alive)
        country_mat_cap = (self.population * (p["mat_cap_base_per_pop"] + k.industry_tech * p["mat_cap_industry_coef"]) +
                           sum(self.resources.values()) * p["mat_cap_resource_coef"])
        self_saturation = max(p["self_saturation_min"], 1 - self.material_gdp / max(1, country_mat_cap))
        global_saturation = max(p["global_saturation_min"], 1 - total_mat / p["global_mat_cap"])
        mat_saturation = min(self_saturation, global_saturation)

        mat_base = (p["mat_base"] + k.industry_tech * p["mat_industry_coef"] -
                    env_factor * p["mat_env_penalty_factor"])
        resource_income = sum(market.get_price(r) * amt * p["resource_income_factor"] for r, amt in self.resources.items())
        env_penalty = max(0, (p["env_penalty_threshold"] - w.global_environment) * p["env_penalty_factor"])
        mat_growth = ((mat_base + resource_income - env_penalty) * mat_saturation * env_factor *
                      trade_multiplier * convergence_factor)
        mat_growth += self.war_victory_bonus - self.war_defeat_penalty
        if self.is_federal:
            mat_growth -= p["federal_growth_penalty"]
            self.federal_age += 1
        mat_growth += random.uniform(-p["mat_growth_stochastic"], p["mat_growth_stochastic"])

        labor_ratio = (self.pop_young + self.pop_middle * p["middle_age_labor_weight"]) / max(1, self.population)
        mat_growth *= (p["labor_effect_base"] + labor_ratio)

        energy_needed = self.material_gdp * p["energy_demand_per_material"]
        energy_supplied = (self.resources.get("石油", 0) * p["energy_fossil_oil"] +
                           self.resources.get("天然气", 0) * p["energy_fossil_gas"] +
                           self.resources.get("煤炭", 0) * p["energy_fossil_coal"] +
                           k.energy_tech * p["energy_tech_supply"])
        if energy_supplied < energy_needed * p["energy_shortage_threshold"]:
            mat_growth *= energy_supplied / (energy_needed + 1)
        self.material_gdp *= (1 + mat_growth)

        # 服务GDP
        total_serv = sum(c.service_gdp for c in w.countries if c.alive)
        total_gdp = sum(c.gdp for c in w.countries if c.alive)
        service_share = total_serv / max(1, total_gdp)
        serv_saturation = max(p["serv_saturation_min"], 1 - service_share / p["service_share_cap"])
        serv_base = (p["serv_base"] + k.information_tech * p["serv_info_coef"] +
                     k.ai_tech * p["serv_ai_coef"] - env_penalty * p["serv_env_penalty"])
        if k.quantum_tech > p["quantum_tech_threshold"]:
            serv_base += p["serv_quantum_bonus"]
        serv_growth = (serv_base * serv_saturation * trade_multiplier +
                       random.uniform(-p["serv_growth_stochastic"], p["serv_growth_stochastic"]))
        self.service_gdp *= (1 + serv_growth)
        if self.service_gdp < 0.01:
            self.service_gdp = 0.01

        # 财政与国债
        tax_income = self.gdp * p["tax_rate"]
        spending = self.research_budget + self.service_gdp * p["spending_service_ratio"]
        interest_payment = self.debt * self.interest_rate
        deficit = spending + interest_payment - tax_income
        if not np.isnan(deficit):
            self.debt += deficit
        if self.debt < 0:
            self.debt = 0
        debt_ratio = self.debt / max(1, self.gdp)
        self.interest_rate = max(0.01, p["interest_base"] + debt_ratio * p["interest_debt_coef"])
        if debt_ratio > p["debt_crisis_threshold"]:
            self.stability -= p["debt_crisis_stability_penalty"]
            w.log(f"📉 {self.name} 债务危机")
        # 内生金融危机逻辑
        serv_ratio = self.service_gdp / max(1, self.gdp)
        stock_overheat = self.stock_market.index > p.get("crisis_stock_threshold", 3000)
        debt_overhang = debt_ratio > p.get("crisis_debt_threshold", 1.2)
        if serv_ratio > p.get("crisis_serv_ratio_trigger", 0.75) and (stock_overheat or debt_overhang):
            if random.random() < p.get("crisis_prob", 0.05):
                severity = random.uniform(0.2, 0.3)  # 物质GDP萎缩20%-30%
                self.material_gdp *= (1 - severity)
                self.stability -= 0.1
                self.stock_market.index *= 0.6
                w.log(f"📉 {self.name} 爆发金融危机！物质GDP萎缩 {severity * 100:.0f}%")

        # 科研与环境
        self.research_budget += (p["research_budget_per_capita"] * (self.gdp / max(1, self.population)) +
                                 tech_spillover * p["tech_spillover_factor"])
        if per_capita > p["convergence_per_capita_high"]:
            self.research_budget *= p["research_budget_high_income_decay"]
        self.research_budget = max(p["research_budget_min"], min(p["research_budget_max"], self.research_budget))
        self.env_pressure = ((100 - w.global_environment) / 100) * self.education * p["env_pressure_edu_factor"]
        if self.stability > p["green_policy_stability_threshold"]:
            k.global_green_policy += self.env_pressure * p["green_policy_from_stability"]

        # 稳定度
        social_fairness = (self.education + k.medicine / p["medicine_to_fairness_divider"] + self.env_pressure) / 3
        self.stability += social_fairness * p["stability_social_fairness_factor"]
        if per_capita < p["per_capita_low_threshold"]:
            self.stability -= p["per_capita_low_penalty"]
        elif per_capita > p["convergence_per_capita_high"]:
            self.stability -= p["per_capita_high_penalty"]
        elif per_capita > p["convergence_per_capita_mid"]:
            self.stability -= p["per_capita_mid_penalty"]
        self.stability += k.sociology * p["sociology_stability_factor"]
        if self.food_reserve < p["food_reserve_threshold"]:
            self.stability -= p["food_reserve_low_penalty"]

        scale_penalty = p["scale_penalty_base"]
        if self.population > p["population_federal_limit"]:
            if self.is_federal:
                scale_penalty += ((self.population - p["population_federal_limit"]) /
                                  p["scale_penalty_denominator"]) * p["population_scale_penalty1"]
            else:
                scale_penalty += ((self.population - p["population_federal_limit"]) /
                                  p["scale_penalty_denominator"]) * p["population_scale_penalty2"]
        institutional_entropy = (self.population * self.gdp) / p["institutional_entropy_divisor"] * scale_penalty
        self.stability -= institutional_entropy * p["institutional_entropy_scale"]
        negentropy = (self.research_budget * p["negentropy_research"] + k.energy_tech * p["negentropy_energy"]) * env_factor
        self.stability += min(negentropy, institutional_entropy * p["negentropy_max_ratio"])

        if self.population > p["population_very_large_limit"] and not self.is_federal:
            self.stability -= (self.population / p["population_scale_stability_divisor"]) * p["population_very_large_penalty"]
        elif self.population > p["population_federal_limit"] and not self.is_federal:
            self.stability -= (self.population / p["population_scale_stability_divisor"]) * p["population_large_penalty"]

        serv_share = self.service_gdp / max(1, self.gdp)
        if serv_share > p["service_share_threshold"]:
            self.stability -= (serv_share - p["service_share_threshold"]) * p["service_share_high_penalty"]

        old_burden = self.pop_old / max(1, self.population)
        if old_burden > p["old_burden_threshold"]:
            self.research_budget *= p["old_burden_research_penalty"]
            self.stability -= old_burden * p["old_burden_stability_penalty"]

        if w.global_environment < p["environment_stability_threshold"]:
            self.stability -= ((p["environment_stability_threshold"] - w.global_environment) *
                               p["environment_low_stability_penalty"])
            if k.global_green_policy > p["green_policy_stability_bonus_threshold"]:
                self.stability += p["green_policy_high_stability_bonus"]

        self._update_culture(year)
        self._update_politics(year)

        if self.population > p["population_federal_limit"] and not self.is_federal and self.stability > p["federal_switch_stability_threshold"]:
            self.is_federal = True; self.federal_age = 0
            w.log(f"🏛️ {self.name} 转为联邦制")

        # 战败惩罚
        if self.war_defeat_penalty > 0.005:
            if p["defeat_penalty_decay_start"] <= year < p["defeat_penalty_decay_end"]:
                self.war_defeat_penalty *= 0.5
            elif year >= p["defeat_penalty_decay_end"]:
                self.war_defeat_penalty = 0.0
            if self.war_defeat_penalty > 0:
                self.stability -= 0.02
        if year >= p["defeat_penalty_decay_end"] and self.war_defeat_penalty <= 0.005 and self.stability < 0.6:
            self.stability += p["post_war_recovery_bonus"]

        if random.random() < p["random_event_prob"]:
            if self.stability < 0.4:
                event = random.choice(["罢工", "政变"])
                w.log(f"⚡ {self.name} 发生{event}")
                self.stability -= p["event_stability_penalty"]
                self.material_gdp *= p["event_gdp_damage"]
                if event == "政变":
                    self._coup()
            elif self.stability < p["protest_stability_threshold"]:
                if random.random() < p["protest_prob"]:
                    w.log(f"⚡ {self.name} 爆发抗议")
                    self.stability -= p["protest_stability_penalty"]

        if (self.education > p["democracy_movement_edu_threshold"] and
            per_capita > p["democracy_movement_per_capita_threshold"] and
            random.random() < p["democracy_movement_prob"]):
            if self.democracy_movement_cd <= year:
                w.log(f"🗳️ {self.name} 民主化运动")
                self.stability -= p["democracy_movement_stability_cost"]
                k.sociology += p["democracy_movement_sociology_gain"]
                self.democracy_movement_cd = year + 5
                if self.government == "威权" and random.random() < 0.5:
                    self.government = "混合"

        if self.ideology > p["ideology_extreme_threshold"]:
            self.stability += p["ideology_stability_bonus"]
        elif self.ideology < p["ideology_extreme_negative_threshold"]:
            self.stability -= p["ideology_stability_bonus"]

        total_diff = 0; count = 0
        for c in w.countries:
            if c.alive and c.name != self.name:
                total_diff += self.cultural_difference(c)
                count += 1
        if count > 0:
            avg_diff = total_diff / count
            self.stability -= avg_diff * p["cultural_diff_stability_impact"]
            self.aggression += avg_diff * p["cultural_diff_aggression_impact"]
            self.aggression = max(p["min_aggression"], min(1.0, self.aggression))
            
            # 高稳定度衰减（防止永远封顶）
        if self.stability > p.get("high_stability_threshold", 0.9):
           self.stability -= p.get("high_stability_decay", 0.005)
        self.stability = max(0, min(1, self.stability + random.uniform(-p["stability_random_noise"], p["stability_random_noise"])))

        # 资源消耗
        for r in list(self.resources.keys()):
            price = market.get_price(r)
            depletion = (p["depletion_base"] + self.tech_level * p["depletion_tech_factor"]) / (1 + price / p["price_normalization"])
            if k.information_tech > p["info_tech_depletion_threshold"]:
                depletion *= p["depletion_info_tech_reduction"]
            self.resources[r] -= depletion
            if r in self.resources:
                depletion_amount = min(depletion, self.resources[r])
            else:
                depletion_amount = depletion
            w.waste_accumulation += depletion_amount * p["depletion_waste_factor"]
            if self.resources[r] <= 0:
                del self.resources[r]; w.log(f"{self.name} 的 {r} 枯竭")
                self.material_gdp *= p["resource_depletion_gdp_damage"]
        if not self.resources and k.information_tech > 4 and random.random() < p["resource_crisis_recovery_chance"]:
            high_res = max(market.prices.items(), key=lambda x: x[1])[0]
            self.resources[high_res] = 20; w.log(f"{self.name} 开发出替代技术 {high_res}")
        self.food_reserve += k.agriculture * p["food_from_agriculture"] - (100 - w.global_environment) * p["food_env_penalty"]
        self.food_reserve = max(0, min(1, self.food_reserve))

        # 内部代理
        for agent in self.internal_agents:
            if agent.alive:
                agent.act(self)

        # 联邦分裂
        if self.alive and self.is_federal and self.federal_age > 10:
            separation_chance = min(p["max_federal_split_chance"],
                                    (self.population / p["federal_split_pop_divisor"]) * p["federal_split_chance_coef"])
            if random.random() < separation_chance:
                sep_pop = self.population * random.uniform(p["federal_split_ratio_min"], p["federal_split_ratio_max"])
                ratio = sep_pop / self.population
                self.pop_children *= (1 - ratio); self.pop_young *= (1 - ratio)
                self.pop_middle *= (1 - ratio); self.pop_old *= (1 - ratio)
                self.stability += 0.05
                w.log(f"🏛️ {self.name} 分裂出 {sep_pop:.0f}M 人口")
                new_name = f"{self.name}自治区"
                w.spawn(new_name, self.region, sep_pop,
                        self.gdp * (sep_pop / (self.population + sep_pop)),
                        {}, self.tech_level, self.research_budget * p["federal_split_research_transfer"],
                        self.ideology, self.camp, self.government, sup=0.5,
                        elec=w.year + random.randint(3, 5),
                        lang=self.language, rel=self.religion, ide=self.main_ideology)

        # 崩溃与重组
        if self.stability <= 0 or self.population <= p["collapse_pop_threshold"]:
            self.alive = False; w.log(f"💔 {self.name} 崩溃")
        if not self.alive and k.information_tech > p["info_tech_revival_threshold"] and random.random() < p["revival_prob"]:
            self.alive = True; self.stability = 0.6
            self.pop_children = self.population * 0.35 * p["revival_pop_scale"]
            self.pop_young = self.population * 0.40 * p["revival_pop_scale"]
            self.pop_middle = self.population * 0.20 * p["revival_pop_scale"]
            self.pop_old = self.population * 0.05 * p["revival_pop_scale"]
            self.material_gdp *= p["revival_gdp_scale"]; self.service_gdp *= p["revival_gdp_scale"]
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
                        w.log(f"🌍 {self.name} 语言变为 {self.language}")
                    elif random.random() < 0.5 and self.main_ideology != other.main_ideology:
                        old_ide = self.main_ideology
                        self.main_ideology = other.main_ideology
                        w.log(f"🌍 {self.name} 意识形态变为 {self.main_ideology}")
                self.cultural_influence[other.name] = 0

    def _update_politics(self, year):
        if self.government == "民主":
            if year >= self.election_year:
                self.election_year += random.randint(4, 6)
                self.party_support += random.uniform(-0.2, 0.2)
                self.party_support = max(0.1, min(0.9, self.party_support))
                self.world.log(f"🗳️ {self.name} 大选，支持率 {self.party_support:.2f}")
                if self.party_support < 0.3: self.stability -= 0.1
        elif self.government == "威权":
            self.party_support -= 0.01
            if random.random() < 0.05:
                self.world.log(f"⚡ {self.name} 反威权抗议")
                self.stability -= 0.05
        if self.government != "民主" and self.stability < 0.3 and random.random() < 0.02:
            self._coup()

    def _coup(self):
        old_gov = self.government
        new_gov = random.choice(["民主", "威权", "混合"])
        self.government = new_gov
        self.stability = 0.4; self.party_support = 0.5
        self.world.log(f"💥 {self.name} 政变！{old_gov} → {new_gov}")
        if self.government == "威权":
            for al in self.world.alliances.alliances:
                if al.has(self.name) and al.name in ["北约", "欧盟"]:
                    al.members.remove(self.name)
                    self.world.log(f"🚫 {self.name} 被 {al.name} 开除")


class World:
    def __init__(self, params=None, **kwargs):
        self.params = DEFAULT_PARAMS.copy()
        if params:
            self.params.update(params)

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
        self.max_gdp = kwargs.get("max_gdp", self.params.get("max_gdp", 120000))
        self.war_prob = kwargs.get("war_prob", self.params.get("war_prob", 0.0166))
        self.proxy_prob = kwargs.get("proxy_prob", self.params.get("proxy_prob", 0.0154))
        self.emergence_prob = kwargs.get("emergence_prob", self.params.get("emergence_prob", 0.0309))
        self.civilization_ended = False
        self._apply_historical = kwargs.get("apply_historical", False)
        self.waste_accumulation = 0.0
        self.multinationals = []
        self.ingos = []
        self.nsags = []
        self.ecosystem = Ecosystem()
        try:
            self.real_data = pd.read_csv("historical_data_real.csv")
        except:
            self.real_data = None
        if not kwargs.get("no_init", False):
            self._init_1900()
            # 记录初始年的环境、GDP、人口，保证历史列表与年份同步
            self.env_history = [self.global_environment]
            total_gdp = sum(c.gdp for c in self.countries if c.alive)
            total_pop = sum(c.population for c in self.countries if c.alive)
            self.gdp_history = [total_gdp]
            self.pop_history = [total_pop]

    def _init_1900(self):
        data = [
            ("华夏","东亚",400,50,{"煤炭":80,"铁矿":60,"稀土":90},0.3,0.8092,0,0,"混合",0.5,1904,"汉语","无宗教","共产主义",True,"standard"),
            ("美利坚","北美",76,120,{"石油":70,"铁矿":50},0.7,0.8092,1,1,"民主",0.6,1904,"英语","基督教","自由主义",True,"standard"),
            ("俄罗斯","东欧",120,40,{"石油":90,"天然气":80,"铁矿":40},0.4,0.8092,-1,0,"威权",0.7,1905,"俄语","东正教","威权主义",True,"standard"),
            ("不列颠","西欧",41,60,{"煤炭":70,"铁矿":40},0.6,0.8092,1,1,"民主",0.55,1906,"英语","基督教","自由主义",False,"standard"),
            ("法兰西","西欧",38,40,{"铁矿":50,"煤炭":30},0.5,0.8092,1,1,"民主",0.5,1906,"法语","基督教","自由主义",False,"standard"),
            ("德意志","中欧",56,55,{"煤炭":80,"铁矿":70},0.6,0.8092,0,0,"威权",0.8,1907,"德语","基督教","民族主义",False,"standard"),
            ("日本","东亚",44,30,{"煤炭":10},0.5,0.8092,0,0,"威权",0.9,1908,"日语","佛教","民族主义",False,"pacifist"),
            ("意大利","南欧",32,20,{"煤炭":20,"铁矿":20},0.4,0.8092,0,0,"混合",0.4,1904,"意大利语","基督教","自由主义",False,"standard"),
            ("奥匈","中欧",45,25,{"煤炭":40,"铁矿":30},0.4,0.8092,0,0,"威权",0.6,1907,"德语","基督教","民族主义",False,"standard"),
            ("奥斯曼","中东",25,15,{"石油":40},0.3,0.8092,-1,0,"威权",0.7,1905,"阿拉伯语","伊斯兰教","民族主义",False,"standard"),
            ("印度","南亚",280,30,{"煤炭":60},0.3,0.8092,0,0,"混合",0.3,1905,"印地语","印度教","民族主义",False,"standard"),
            ("巴西","南美",18,10,{"森林":90,"铁矿":30},0.3,0.8092,0,0,"混合",0.5,1906,"葡萄牙语","基督教","社会民主主义",False,"standard"),
            ("加拿大","北美",5,8,{"森林":70},0.5,0.8092,1,1,"民主",0.6,1904,"英语","基督教","自由主义",False,"standard"),
            ("澳大利亚","大洋洲",4,6,{"煤炭":30,"铁矿":40},0.5,0.8092,1,1,"民主",0.55,1907,"英语","基督教","自由主义",False,"standard"),
            ("阿根廷","南美",8,5,{"农业":70},0.4,0.8092,0,0,"混合",0.4,1905,"西班牙语","基督教","社会民主主义",False,"standard"),
        ]
        mult_homes = ["美利坚","不列颠","德意志"]
        for i, home in enumerate(mult_homes):
            self.multinationals.append(MultinationalCorp(f"{home}跨国集团{i}", home, random.uniform(0.3,0.5), random.uniform(150,300)))
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
            "nsags": [{"name": n.name, "type": n.type, "base_country": n.base_country, "strength": n.strength, "alive": n.alive} for n in self.nsags],
            "env_history": self.env_history,
            "gdp_history": self.gdp_history,
            "pop_history": self.pop_history,
        }

    @classmethod
    def from_dict(cls, state):
        world = cls(no_init=True)
        world.year = state["year"]
        world.global_environment = state["global_environment"]
        world.expected_environment = state.get("expected_environment", 100.0)
        world.max_gdp = state.get("max_gdp", 120000)
        world.war_prob = state.get("war_prob", 0.0166)
        world.proxy_prob = state.get("proxy_prob", 0.0154)
        world.emergence_prob = state.get("emergence_prob", 0.0309)
        world.waste_accumulation = state.get("waste_accumulation", 0.0)
        kn = state["knowledge"]
        world.knowledge = KnowledgeTree(world)
        for attr in ["math","physics","chemistry","biology","medicine","agriculture","philosophy","sociology",
                     "energy_tech","environment_tech","industry_tech","information_tech","space_tech","ai_tech",
                     "global_green_policy","scientific_knowledge","quantum_tech"]:
            setattr(world.knowledge, attr, kn.get(attr, 0))
        for node in world.knowledge.tech_tree.nodes:
            if node.name in kn.get("unlocked_nodes", []):
                node.unlocked = True
        for cd in state["countries"]:
            total_pop = cd.get("pop_children",0)+cd.get("pop_young",0)+cd.get("pop_middle",0)+cd.get("pop_old",0)
            if total_pop == 0:
                total_pop = cd.get("population",10)
            c = Country(world, cd["name"], cd["region"], total_pop, cd["material_gdp"]+cd["service_gdp"],
                        cd["resources"], cd["tech_level"], cd["research_budget"], cd["ideology"], cd["camp"],
                        cd.get("government","混合"), cd.get("party_support",0.5), cd.get("election_year",world.year+4),
                        language=cd.get("language","英语"), religion=cd.get("religion","基督教"),
                        main_ideology=cd.get("main_ideology","自由主义"), ai_controlled=cd.get("ai_controlled", False),
                        constitution=cd.get("constitution", "standard"))
            c.alive = cd["alive"]
            c.pop_children = cd.get("pop_children", total_pop*0.35)
            c.pop_young = cd.get("pop_young", total_pop*0.40)
            c.pop_middle = cd.get("pop_middle", total_pop*0.20)
            c.pop_old = cd.get("pop_old", total_pop*0.05)
            c.material_gdp = cd["material_gdp"]
            c.service_gdp = cd["service_gdp"]
            c.stability = cd["stability"]
            c.aggression = cd.get("aggression",0.3)
            c.war_victory_bonus = cd.get("war_victory_bonus",0)
            c.war_defeat_penalty = cd.get("war_defeat_penalty",0)
            c.last_war_year = cd.get("last_war_year",0)
            c.democracy_movement_cd = cd.get("democracy_movement_cd",0)
            c.education = cd.get("education",0.3)
            c.food_reserve = cd.get("food_reserve",0.5)
            c.trade_partners = set(cd.get("trade_partners",[]))
            c.is_federal = cd.get("is_federal",False)
            c.federal_age = cd.get("federal_age",0)
            c.debt = cd.get("debt",0.0)
            c.interest_rate = cd.get("interest_rate",0.03)
            c.internal_agents = []
            for ad in cd.get("internal_agents",[]):
                agent = InternalAgent(ad["name"], ad["type"], ad["power"], ad.get("wealth",0), ad.get("goal","profit"))
                agent.alive = ad.get("alive",True)
                c.internal_agents.append(agent)
            c.cultural_influence = cd.get("cultural_influence",{})
            world.countries.append(c)
        rm = state.get("resource_market",{})
        world.resource_market.prices = rm.get("prices", world.resource_market.prices)
        world.resource_market.trade_agreements = rm.get("trade_agreements",[])
        world.events_log = state.get("events_log",[])
        world.multinationals = []
        for md in state.get("multinationals",[]):
            m = MultinationalCorp(md["name"], md["home_country"], md.get("power",0.3), md.get("wealth",100))
            m.branches = md.get("branches",[])
            m.alive = md.get("alive",True)
            world.multinationals.append(m)
        world.ingos = []
        for ingo_dict in state.get("ingos",[]):
            ingo = INGO(ingo_dict["name"], ingo_dict["focus"], ingo_dict.get("influence",0.2))
            ingo.resources = ingo_dict.get("resources",50)
            ingo.alive = ingo_dict.get("alive",True)
            world.ingos.append(ingo)
        world.nsags = []
        for nd in state.get("nsags",[]):
            nsag = NonStateArmedGroup(nd["name"], nd["type"], nd["base_country"], nd.get("strength",10))
            nsag.alive = nd.get("alive",True)
            world.nsags.append(nsag)
        # 恢复历史记录（如果存档中有的话）
        world.env_history = state.get("env_history", [world.global_environment])
        world.gdp_history = state.get("gdp_history", [sum(c.gdp for c in world.countries if c.alive)])
        world.pop_history = state.get("pop_history", [sum(c.population for c in world.countries if c.alive)])
        return world

    def _refugee_crisis(self):
        for country in self.countries:
            if not country.alive:
                continue
            refugee_out = 0
            if self.global_environment < 15 and country.stability < 0.5:
                refugee_out = country.population * 0.05
            elif country.stability < 0.2:
                refugee_out = country.population * 0.03
            elif country.population <= 0.5:
                refugee_out = country.population * 0.1
            if refugee_out > 0:
                alive_others = [c for c in self.countries if c.alive and c.name != country.name]
                if not alive_others:
                    continue
                alive_others.sort(key=lambda c: ((country.latitude - c.latitude) ** 2 + (country.longitude - c.longitude) ** 2) ** 0.5)
                receivers = alive_others[:3]
                total_dist = sum(((country.latitude - r.latitude) ** 2 + (country.longitude - r.longitude) ** 2) ** 0.5 for r in receivers)
                if total_dist == 0:
                    total_dist = 1
                for r in receivers:
                    dist = ((country.latitude - r.latitude) ** 2 + (country.longitude - r.longitude) ** 2) ** 0.5
                    share = (1 - dist / total_dist)
                    inflow = refugee_out * share
                    r.pop_young += inflow * 0.8
                    r.pop_middle += inflow * 0.2
                    r.stability -= 0.02
                country.population -= refugee_out
                self.log(f"🚶 {country.name} 产生难民潮，约 {refugee_out:.1f}M 人逃往邻国")

    def _spawn_nsags_from_chaos(self):
        for c in self.countries:
            if c.alive and c.stability < 0.3 and random.random() < 0.002:
                existing = [g for g in self.nsags if g.base_country == c.name and g.alive]
                if len(existing) < 2:
                    gtype = random.choice(["guerrilla", "terrorist"])
                    g = NonStateArmedGroup(f"{c.name}{gtype}组织", gtype, c.name, random.uniform(5, 15))
                    self.nsags.append(g)
                    self.log(f"💣 {c.name} 境内出现{gtype}组织：{g.name}")

    def _force_historical(self):
        if not self._apply_historical or self.real_data is None or self.year > 2025:
            return
        year_data = self.real_data[self.real_data['year'] == self.year]
        if year_data.empty:
            return
        total_co2 = 0.0
        for _, row in year_data.iterrows():
            c = self.find(row['country'])
            if c and c.alive:
                if pd.isna(row['gdp']) or pd.isna(row['population']):
                    continue
                old_ratio = c.material_gdp / max(1, c.gdp)
                c.population = row['population']
                c.material_gdp = row['gdp'] * old_ratio
                c.service_gdp = row['gdp'] * (1 - old_ratio)
                total_co2 += row.get('co2', 0)
                if c.ai_controlled:
                    c.aggression = 0.05
                    c.research_budget = min(c.research_budget, 10)
        cumulative_co2_factor = min(1.0, total_co2 / 50)
        target_env = 100 - cumulative_co2_factor * 40
        self.global_environment = target_env
        self.expected_environment = 0.7 * self.global_environment + 0.3 * self.expected_environment

    def run_year(self):
        if self.civilization_ended:
            return False
        self.year += 1
        for c in self.countries:
            if c.alive and c.ai_controlled:
                prev_stability = c.stability
                prev_gdp = c.gdp
                state = get_ai_state(self, c)
                action = ai_decision(self, c)
                apply_ai_action(self, c, action)
                ai_memory[c.name] = (state, action, prev_stability, prev_gdp)
        self._history()
        self.knowledge.update(self.countries, self.year)
        for c in [c for c in self.countries if c.alive]:
            c.internal_development()
        self.resource_market.update(self.countries)
        if random.random() < 0.1:
            self.resource_market.negotiate_trade(self)
        for mcorp in self.multinationals:
            if mcorp.alive:
                mcorp.expand(self)
        for ingo in self.ingos:
            if ingo.alive:
                ingo.act(self)
        self._refugee_crisis()
        for nsag in self.nsags:
            if nsag.alive:
                nsag.act(self)
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
        self.gdp_history.append(total_gdp)
        self.pop_history.append(total_pop)
        if len(self.env_history) > 1000:
            self.env_history = self.env_history[-500:]
        for c in self.countries:
            if c.alive and c.ai_controlled and c.name in ai_memory:
                state, action, prev_stab, prev_gdp = ai_memory.pop(c.name)
                reward = get_reward(self, c, prev_stab, prev_gdp)
                if state in q_table:
                    old_q = q_table[state][action]
                    next_state = get_ai_state(self, c)
                    next_max = max(q_table.get(next_state, {a: 0 for a in range(6)}).values())
                    q_table[state][action] = old_q + 0.1 * (reward + 0.9 * next_max - old_q)
        for c in self.countries:
            if c.alive and c.ai_controlled:
                c._prev_gdp = c.gdp
                c._prev_stability = c.stability
        for c in self.countries:
            if c.alive and c.stability < 0:
                c.stability = 0.01
            elif c.alive:
                c.stability = max(0.0, min(1.0, c.stability))
        return True

    def _history(self):
        y = self.year
        if y == 1914:
            self.log("🌍 一战爆发")
            self._script_war(["不列颠", "法兰西", "俄罗斯", "意大利", "美利坚"], ["德意志", "奥匈", "奥斯曼"], 0.5)
        if y == 1917 and random.random() < 0.95:
            rus = self.find("俄罗斯")
            if rus:
                rus.ideology = -1
                rus.government = "威权"
        if y == 1918:
            self.remove("奥匈")
            self.spawn("奥地利", "中欧", 6, 3, {}, 0.4, 2, 0, 0, "民主", 0.5, self.year + 3, "德语", "基督教", "自由主义")
            self.spawn("匈牙利", "中欧", 7, 2, {}, 0.4, 2, 0, 0, "混合", 0.4, self.year + 3, "匈牙利语", "基督教", "民族主义")
            self.spawn("捷克斯洛伐克", "中欧", 13, 5, {}, 0.5, 3, 1, 0, "民主", 0.6, self.year + 4, "捷克语", "基督教", "自由主义")
            self.remove("奥斯曼")
            self.spawn("土耳其", "中东", 14, 4, {"石油": 10}, 0.4, 2, 0, 0, "混合", 0.5, self.year + 2, "土耳其语", "伊斯兰教", "民族主义")
            for n in ["德意志", "奥地利", "匈牙利", "土耳其"]:
                c = self.find(n)
                if c:
                    c.war_defeat_penalty = 0.005
            for n in ["不列颠", "法兰西", "意大利", "美利坚"]:
                c = self.find(n)
                if c:
                    c.war_victory_bonus = 0.003
        if y == 1922 and self.find("俄罗斯") and self.find("俄罗斯").ideology < 0:
            self.find("俄罗斯").name = "苏联"
            self.log("苏联成立")
        if y == 1929:
            self.log("📉 大萧条")
            for c in self.countries:
                c.material_gdp *= 0.8
        if y == 1933:
            ger = self.find("德意志")
            if ger:
                ger.ideology = -1
                ger.government = "威权"
        if y == 1939:
            self.log("🌍 二战爆发")
            self._script_war(["不列颠", "法兰西", "苏联", "美利坚", "华夏"], ["德意志", "意大利", "日本"], 0.7)
        if y == 1945:
            for n in ["美利坚", "苏联", "不列颠", "法兰西", "华夏"]:
                c = self.find(n)
                if c:
                    c.war_victory_bonus = 0.008
            for n in ["德意志", "意大利", "日本"]:
                c = self.find(n)
                if c:
                    c.war_defeat_penalty = 0.01
                    c.stability -= 0.05
                    if n != "日本":
                        c.government = "民主"
            ger = self.find("德意志")
            if ger:
                ger.name = "西德"
                self.spawn("东德", "中欧", 16, 4, {}, 0.5, 2, -1, 2, "威权", 0.6, self.year + 3, "德语", "无宗教", "共产主义")
            jap = self.find("日本")
            if jap:
                jap.ideology = 1
                jap.government = "民主"
        if y == 1947:
            ind = self.find("印度")
            if ind:
                self.spawn("巴基斯坦", "南亚", 30, 3, {}, 0.3, 1, 0, 0, "混合", 0.4, self.year + 2, "乌尔都语", "伊斯兰教", "民族主义")
        if y == 1948:
            self.spawn("以色列", "中东", 1, 2, {}, 0.6, 5, 1, 0, "民主", 0.6, self.year + 4, "希伯来语", "犹太教", "民族主义")
        if y == 1949:
            chi = self.find("华夏")
            if chi:
                chi.ideology = -1
                chi.camp = 2
                chi.government = "威权"
        if y == 1962:
            self.log("🚀 古巴导弹危机")
        if y == 1973:
            self.log("⛽ 石油危机")
            for c in self.countries:
                if "石油" not in c.resources:
                    c.material_gdp *= 0.95
        if y == 1978:
            chi = self.find("华夏")
            if chi:
                chi.ideology = 0
                chi.government = "混合"
        if y == 1989:
            self.log("🧱 柏林墙倒塌")
        if y == 1991:
            sov = self.find("苏联")
            if sov:
                sov.name = "俄罗斯"
                sov.ideology = 0
                sov.government = "混合"
                self.spawn("乌克兰", "东欧", 52, 10, {"煤炭": 30}, 0.4, 2, 0, 0, "混合", 0.5, self.year + 4, "乌克兰语", "东正教", "民族主义")
                self.spawn("白俄罗斯", "东欧", 10, 3, {}, 0.4, 1, 0, 0, "威权", 0.6, self.year + 3, "白俄罗斯语", "东正教", "威权主义")
                self.spawn("哈萨克斯坦", "中亚", 16, 2, {"石油": 20}, 0.3, 1, 0, 0, "威权", 0.7, self.year + 5, "哈萨克语", "伊斯兰教", "威权主义")
            self.remove("东德")
            wg = self.find("西德")
            if wg:
                wg.name = "德意志"
                wg.government = "民主"
        if y == 1993:
            self.log("🇪🇺 欧盟成立")
        if y == 2001:
            self.log("✈️ 911")
        if y == 2008:
            self.log("🏦 金融危机")
            for c in self.countries:
                c.material_gdp *= 0.92
        if y == 2020:
            self.log("🦠 新冠疫情")
            for c in self.countries:
                c.population *= 0.95
                c.material_gdp *= 0.94
            self.knowledge.medicine += 0.5
        if y == 2023:
            self.log("🤖 AI突破")
            self.knowledge.ai_tech += 1.5

    def _script_war(self, a_list, b_list, intensity):
        for a in a_list:
            for b in b_list:
                ca = self.find(a)
                cb = self.find(b)
                if ca and cb:
                    self._war_direct(ca, cb, intensity)

    def _war_direct(self, attacker, defender, scale):
        if attacker.constitution == "pacifist" and scale > 0:
            self.log(f"🕊️ {attacker.name} 受和平宪法约束，无法主动进攻")
            return
        allies = self.alliances.defend(defender, attacker, self.year, self)
        for ally in allies:
            self.log(f"⚔️ {ally.name} 因联盟义务加入防御 {defender.name}")
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
        alive = [c for c in self.countries if c.alive]
        if len(alive) < 2:
            return
        if self.year >= 1945 and random.random() < 0.15:
            self.log("🌐 联合国气候峰会")
            self.knowledge.global_green_policy += 0.03
        if random.random() < self.proxy_prob:
            self.proxy_war_system.attempt(self)
        for i in range(len(alive)):
            for j in range(i + 1, len(alive)):
                a, b = alive[i], alive[j]
                a.trade_partners.add(b.name)
                b.trade_partners.add(a.name)
                if self.alliances.can_war(a.name, b.name, self.year) and random.random() < self.war_prob * 0.5:
                    if self.year - a.last_war_year > 5 and self.year - b.last_war_year > 5:
                        if a.stability < 0.5 or b.stability < 0.5 or a.aggression > 0.7 or b.aggression > 0.7:
                            self._war_direct(a, b, 0.2)
                            a.last_war_year = self.year
                            b.last_war_year = self.year

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
            if 1920 <= self.year <= 2020:
                self.global_environment -= 0.05
            elif 2021 <= self.year <= 2050:
                self.global_environment -= 0.1
        waste_penalty = self.waste_accumulation * 0.001
        self.global_environment -= waste_penalty
        self.waste_accumulation *= 0.9995
        total_global_gdp = sum(c.gdp for c in alive)
        if total_global_gdp > 300000:
            self.global_environment -= 0.3
            if random.random() < 0.1:
                self.log("🌪️ 全球经济过热导致环境加速恶化")
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
        if self.expected_environment < 50:
            self.knowledge.global_green_policy += 0.005
        if self.global_environment < 15 and random.random() < 0.1:
            self.log("☠️ 局部生态崩溃")
            for c in alive:
                c.population *= 0.9
                c.stability -= 0.1
        if abs(self.expected_environment - self.global_environment) > 20:
            adjustment = (self.expected_environment - self.global_environment) * 0.001
            self.knowledge.global_green_policy += adjustment
            if abs(adjustment) > 0.005:
                self.log("⚛️ 政策过度反应")

    def _emergence(self):
        if random.random() < self.emergence_prob:
            m = random.choice(["全球气候罢课", "开源绿色能源革命", "反战和平运动", "去中心化科研浪潮",
                               "基本收入实验推广", "全球大流行病变种预警", "气候工程意外后果讨论",
                               "AI伦理国际公约", "太空资源开发倡议", "量子互联网雏形"])
            self.log(f"🌱 涌现事件：{m}")
            if "气候罢课" in m:
                self.knowledge.global_green_policy += 0.05
            elif "绿色能源" in m:
                self.knowledge.energy_tech += 0.5
            elif "和平" in m:
                for c in self.countries:
                    c.aggression *= 0.9
            elif "科研" in m:
                self.knowledge.scientific_knowledge += 0.5
            elif "基本收入" in m:
                for c in self.countries:
                    c.stability += 0.05
            elif "大流行病变种" in m:
                for c in self.countries:
                    c.population *= 0.97
                    c.material_gdp *= 0.96
                self.knowledge.medicine += 0.4
                self.log("  ↳ 引发新一轮医学研究投入")
            elif "气候工程意外" in m:
                self.global_environment += random.choice([-5, 3])
                self.knowledge.global_green_policy += 0.03
            elif "AI伦理" in m:
                for c in self.countries:
                    c.aggression *= 0.95
                self.knowledge.sociology += 0.3
            elif "太空资源" in m:
                self.knowledge.space_tech += 0.5
                self.knowledge.industry_tech += 0.2
            elif "量子互联网" in m:
                self.knowledge.quantum_tech += 0.8
                self.knowledge.information_tech += 0.5
        if self.year >= 2100 and self.knowledge.ai_tech >= 10 and self.knowledge.quantum_tech >= 10 and self.knowledge.scientific_knowledge >= 10:
            if random.random() < 0.002:
                self.knowledge.scientific_knowledge = min(15, self.knowledge.scientific_knowledge + 2)
                self.knowledge.ai_tech = min(15, self.knowledge.ai_tech + 2)
                self.knowledge.quantum_tech = min(15, self.knowledge.quantum_tech + 2)
                self.log("💡 技术奇点发生！基础科学取得突破性进展，开启新时代")

    def _random(self):
        if random.random() < 0.04:
            ev = random.choice(["大萧条", "疫情", "技术突破", "资源发现"])
            self.log(f"🌐 {ev}")
            alive = [c for c in self.countries if c.alive]
            if ev == "大萧条":
                for c in alive:
                    c.material_gdp *= 0.9
            elif ev == "疫情":
                for c in alive:
                    c.population *= 0.93
                self.knowledge.medicine += 0.2
            elif ev == "技术突破":
                tech = random.choice(["energy_tech", "information_tech", "ai_tech", "environment_tech"])
                setattr(self.knowledge, tech, min(10, getattr(self.knowledge, tech) + 1))
            elif ev == "资源发现":
                res = random.choice(["石油", "天然气", "锂", "稀土", "铀"])
                for c in random.sample(alive, min(3, len(alive))):
                    c.resources[res] = c.resources.get(res, 0) + 30

    def monte_carlo_prediction(self, num_simulations=100, years=80):
        futures = {self.year + y: [] for y in range(years + 1)}
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
        if not self.env_history:
            return
        print(" 环境趋势 (最近20年):")
        max_env = max(self.env_history[-20:])
        for val in self.env_history[-20:]:
            bar_len = int(val / max(1, max_env) * 20)
            print(f"  {val:5.1f} |{'█' * bar_len}")

    def status_report(self):
        era_name, _ = TechEra.get_era(self.knowledge.total_tech())
        print(f"\n{'=' * 60}")
        print(f" 地球模拟器 Pro++ · {self.year}年")
        print(f" 时代: {era_name} | 环境: {self.global_environment:.1f} | 清洁能源: {self.knowledge.green_ratio() * 100:.0f}%")
        print(f" 国家: {len(self.countries)} | 修复力: {self.knowledge.env_repair_rate():.2f} | 科学知识: {self.knowledge.scientific_knowledge:.2f}")
        print(f" 量子科技: {self.knowledge.quantum_tech:.2f} | 预期环境: {self.expected_environment:.1f}")
        if self.civilization_ended:
            print("【文明已终结】")
        else:
            print(f"{'=' * 60}")
            for c in sorted(self.countries, key=lambda x: x.gdp, reverse=True)[:12]:
                s = "🟢" if c.stability > 0.7 else "🟡" if c.stability > 0.4 else "🔴"
                gov_short = {"民主": "民", "威权": "威", "混合": "混"}.get(c.government, "?")
                ai_tag = "🤖" if c.ai_controlled else ""
                fed_tag = "🏛️" if c.is_federal else ""
                print(f" {ai_tag}{fed_tag}{c.name:<10} 人口{c.population:.0f}M GDP{c.gdp:.0f}B (物{c.material_gdp:.0f}/服{c.service_gdp:.0f}) 稳{c.stability:.2f} [{gov_short}] {c.main_ideology[:2]} {s}")
        print(f"{'=' * 60}")
        if hasattr(self, 'multinationals') and self.multinationals:
            print(f"🏢 跨国公司: {len(self.multinationals)} 家")
            for m in self.multinationals[:5]:
                print(f"   {m.name} (母国: {m.home_country}) 分支数: {len(m.branches)}")
        if hasattr(self, 'ingos') and self.ingos:
            print(f"🌐 国际非政府组织: {len(self.ingos)} 家")
            for ingo in self.ingos[:5]:
                print(f"   {ingo.name} (焦点: {ingo.focus}) 资源: {ingo.resources:.1f}")
        if hasattr(self, 'nsags') and self.nsags:
            print(f"💣 非国家武装团体: {len(self.nsags)} 个")
            for g in self.nsags[:5]:
                print(f"   {g.name} (类型:{g.type}) 强度:{g.strength:.1f}")
        self.show_env_trend()
        print()

    def generate_report(self, filename=None):
        if filename is None:
            filename = f"report_{self.year}.html"
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
        else:
            html += "<h2>文明状态</h2><p>文明已终结，无存活国家。</p>"
        html += f"<h2>重大战争（最近20条）</h2><ul>"
        for w in wars[-20:]:
            html += f"<li>{w}</li>"
        if not wars:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>文化变迁（最近20条）</h2><ul>"
        for ce in culture_events[-20:]:
            html += f"<li>{ce}</li>"
        if not culture_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>科技突破（最近20条）</h2><ul>"
        for te in tech_events[-20:]:
            html += f"<li>{te}</li>"
        if not tech_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>涌现事件（最近20条）</h2><ul>"
        for ee in emergence_events[-20:]:
            html += f"<li>{ee}</li>"
        if not emergence_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>跨国公司活动（最近20条）</h2><ul>"
        for ce in corp_events[-20:]:
            html += f"<li>{ce}</li>"
        if not corp_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>国际组织行动（最近20条）</h2><ul>"
        for ie in ingo_events[-20:]:
            html += f"<li>{ie}</li>"
        if not ingo_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += f"<h2>非国家武装活动（最近20条）</h2><ul>"
        for ne in nsag_events[-20:]:
            html += f"<li>{ne}</li>"
        if not nsag_events:
            html += "<li>无记录</li>"
        html += "</ul>"
        html += "<p><em>本报告由地球模拟器 Pro++ 自动生成</em></p></body></html>"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"人类世报告已保存至 {filename}")
        return html

    def generate_biography(self, country_name, filename=None):
        country = self.find(country_name)
        if not country:
            return None
        if filename is None:
            filename = f"biography_{country_name}_{self.year}.html"
        events = [e for e in self.events_log if country_name in e]
        html = f"""<html><head><meta charset="utf-8"><title>{country_name}传记 {self.year}</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:auto;padding:20px;}}h1{{color:#333;}}h2{{border-bottom:1px solid #aaa;}}.stat{{display:flex;gap:20px;flex-wrap:wrap;}}.card{{background:#f5f5f5;padding:10px;border-radius:5px;min-width:120px;}}</style></head>
<body><h1>{country_name}国家传记</h1><p><b>年份：</b>{self.year} &nbsp; | &nbsp; <b>状态：</b>{'存活' if country.alive else '灭亡'}</p></body></html>"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        return html