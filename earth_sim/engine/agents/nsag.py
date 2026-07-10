import random

class NonStateArmedGroup:
    def __init__(self, name, group_type, base_country, strength=10.0):
        self.name = name; self.type = group_type; self.base_country = base_country
        self.strength = strength; self.alive = True

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