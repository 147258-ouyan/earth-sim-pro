import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from earth_sim.world import World
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 加载真实数据并按年份聚合
real = pd.read_csv("historical_data_real.csv")
gdp_series = real.groupby("year")["gdp"].sum()
pop_series = real.groupby("year")["population"].sum()
if "co2" in real.columns:
    co2_series = real.groupby("year")["co2"].sum()
else:
    co2_series = None

# 找出三个指标都有数据的公共年份（1900-2020）
common_years = gdp_series.index.intersection(pop_series.index)
if co2_series is not None:
    common_years = common_years.intersection(co2_series.index)
common_years = common_years[(common_years >= 1900) & (common_years <= 2020)]
common_years = sorted(common_years)

real_gdp = gdp_series.loc[common_years].values
real_pop = pop_series.loc[common_years].values
if co2_series is not None:
    real_env = 100 - co2_series.loc[common_years].values / 10   # 环境代理：排放越低，环境越好
else:
    real_env = None

# 加载校准好的参数（如果有）
try:
    with open("best_params.json", "r") as f:
        best_params = json.load(f)
    print("已加载 best_params.json")
except FileNotFoundError:
    best_params = {}
    print("未找到 best_params.json，使用默认参数")

# 运行模拟
world = World(params=best_params, apply_historical=False)
gdp_hist, pop_hist, env_hist = [], [], []
N = len(common_years)
for _ in range(N):
    world.run_year()
    total_gdp = sum(c.gdp for c in world.countries if c.alive)
    total_pop = sum(c.population for c in world.countries if c.alive)
    gdp_hist.append(total_gdp)
    pop_hist.append(total_pop)
    env_hist.append(world.global_environment)

# 绘图对比
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

axes[0].plot(common_years, real_gdp, label="真实 GDP", color='black')
axes[0].plot(common_years, gdp_hist, label="模拟 GDP", color='blue')
axes[0].set_title("全球 GDP 对比")
axes[0].legend()

axes[1].plot(common_years, real_pop, label="真实人口", color='black')
axes[1].plot(common_years, pop_hist, label="模拟人口", color='green')
axes[1].set_title("全球人口对比")
axes[1].legend()

if real_env is not None:
    axes[2].plot(common_years, real_env, label="真实环境（代理）", color='black')
axes[2].plot(common_years, env_hist, label="模拟环境健康度", color='red')
axes[2].set_title("环境健康度对比")
axes[2].legend()

plt.tight_layout()
plt.savefig("fit_report.png", dpi=150)
print("拟合报告已保存为 fit_report.png")