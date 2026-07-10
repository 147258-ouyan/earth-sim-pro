import numpy as np
import random

class Individual:
    def __init__(self, age, wealth, education):
        self.age = age; self.wealth = wealth; self.education = education
        self.satisfaction = 0.5; self.alive = True

    def update(self, country, env_factor):
        self.age += 1
        if self.age > 85: self.alive = False; return
        if self.wealth > 100: country.service_gdp += self.wealth * 0.01
        else: country.material_gdp += self.wealth * 0.02
        per_capita = country.gdp / max(1, country.population)
        self.satisfaction = (self.education * 0.3 + country.stability * 0.3 +
                             min(1, per_capita / 100) * 0.2 +
                             (country.world.global_environment / 100) * 0.2)
        if self.satisfaction < 0.2 and random.random() < 0.001:
            country.stability -= 0.0001
            country.world.log(f"😞 {country.name} 民众不满情绪上升")

class Household:
    def __init__(self, country):
        self.members = []
        for _ in range(random.randint(2, 5)):
            age = random.randint(0, 80); wealth = random.uniform(1, 200); edu = random.uniform(0.1, 1.0)
            self.members.append(Individual(age, wealth, edu))
        self.country = country

    def update(self, country, env_factor):
        alive_members = [m for m in self.members if m.alive]
        if len(alive_members) < 1: return False
        for m in alive_members: m.update(country, env_factor)
        young_adults = [m for m in alive_members if 20 < m.age < 40]
        if young_adults and random.random() < 0.05 * len(young_adults):
            new_wealth = np.mean([m.wealth for m in alive_members])
            new_edu = np.mean([m.education for m in alive_members]) * random.uniform(0.8, 1.2)
            self.members.append(Individual(0, new_wealth, new_edu))
        return True