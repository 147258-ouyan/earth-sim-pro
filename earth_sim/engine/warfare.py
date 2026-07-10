from __future__ import annotations
from typing import TYPE_CHECKING
import random
if TYPE_CHECKING:
    from earth_sim.world import World

class ProxyWarSystem:
    def __init__(self, alliances): self.alliances = alliances

    def attempt(self, world: 'World'):
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