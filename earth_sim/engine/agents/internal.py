import random

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
        candidates = [c for c in world.countries if c.alive and c.name != self.home_country and c.name not in self.branches]
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