import random

class Ecosystem:
    def __init__(self):
        self.forest_cover = 100.0
        self.ocean_health = 100.0
        self.freshwater = 100.0
        self.biodiversity = 100.0

    @property
    def overall_health(self):
        return (self.forest_cover + self.ocean_health +
                self.freshwater + self.biodiversity) / 4

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
            # 防止负值
            self.forest_cover = max(0, self.forest_cover)
            self.ocean_health = max(0, self.ocean_health)
            self.freshwater = max(0, self.freshwater)
            self.biodiversity = max(0, self.biodiversity)
            self.forest_cover = max(0, self.forest_cover - 10)