import json
from earth_sim.world import World

def run_to_year(w, target):
    while w.year < target:
        w.run_year()

w = World()
run_to_year(w, 1914)
with open("preset_1914.json", "w", encoding="utf-8") as f:
    json.dump(w.to_dict(), f)

run_to_year(w, 1939)
with open("preset_1939.json", "w", encoding="utf-8") as f:
    json.dump(w.to_dict(), f)

run_to_year(w, 1991)
with open("preset_1991.json", "w", encoding="utf-8") as f:
    json.dump(w.to_dict(), f)

run_to_year(w, 2020)
with open("preset_2020.json", "w", encoding="utf-8") as f:
    json.dump(w.to_dict(), f)

print("预设场景已生成！")