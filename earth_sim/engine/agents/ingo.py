import random

class INGO:
    def __init__(self, name, focus, influence=0.2):
        self.name = name; self.focus = focus; self.influence = influence
        self.resources = 50.0; self.alive = True

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