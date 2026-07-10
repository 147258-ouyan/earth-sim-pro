import numpy as np
import pandas as pd
import random
from earth_sim.world import World

# ---------- 加载真实数据 ----------
real_data = pd.read_csv("historical_data_real.csv")
real_gdp = real_data.groupby("year")["gdp"].sum().values
real_pop = real_data.groupby("year")["population"].sum().values
real_co2 = real_data.groupby("year")["co2"].sum().values

# ---------- 目标函数 ----------
def run_simulation(params):
    """运行一次模拟，返回与真实数据的综合误差"""
    w = World(
        war_prob=params[0],
        proxy_prob=params[0] * 0.5,
        emergence_prob=params[1],
        apply_historical=False  # 关闭强制校准，让模型自由运行
    )
    # 手动设置关键初值
    w.knowledge.energy_tech = params[2]
    w.knowledge.environment_tech = params[3]
    for c in w.countries:
        c.research_budget = params[4]

    # 运行到2020年 (121年)
    for _ in range(121):
        w.run_year()

    sim_gdp = np.array(w.gdp_history)
    sim_pop = np.array(w.pop_history)
    sim_env = np.array(w.env_history)  # 环境健康度作为 CO2 的代理

    # 对齐长度
    min_len = min(len(real_gdp), len(sim_gdp))

    gdp_error = np.sqrt(np.mean((real_gdp[:min_len] - sim_gdp[:min_len])**2)) / np.mean(real_gdp)
    pop_error = np.sqrt(np.mean((real_pop[:min_len] - sim_pop[:min_len])**2)) / np.mean(real_pop)

    # 注意：环境健康度与 CO2 排放是负相关，我们简单取倒数关系
    if len(real_co2) >= min_len:
        co2_error = np.sqrt(np.mean((real_co2[:min_len] - (100 - sim_env[:min_len]) * 10)**2)) / np.mean(real_co2)
    else:
        co2_error = 0

    return (gdp_error + pop_error + co2_error) / 3.0

# ---------- 遗传算法 ----------
pop_size = 20
generations = 20
mutation_rate = 0.1
param_bounds = [
    (0.001, 0.05),   # war_prob
    (0.01, 0.1),     # emergence_prob
    (0.0, 1.0),      # energy_tech 初值
    (0.0, 1.0),      # environment_tech 初值
    (0.1, 10.0),     # research_budget 初值
]

population = []
for _ in range(pop_size):
    ind = [np.random.uniform(low, high) for (low, high) in param_bounds]
    population.append(ind)

best_error_history = []
for gen in range(generations):
    errors = [run_simulation(ind) for ind in population]
    best_idx = np.argmin(errors)
    best_error_history.append(errors[best_idx])
    print(f"Gen {gen+1}/{generations} | Best error: {errors[best_idx]:.4f} | Params: {[round(x,4) for x in population[best_idx]]}")

    fitness = [1.0 / (e + 1e-9) for e in errors]
    total_fit = sum(fitness)
    prob = [f / total_fit for f in fitness]
    selected_idx = np.random.choice(len(population), size=pop_size, p=prob)
    selected = [population[i] for i in selected_idx]

    offspring = []
    for i in range(0, pop_size, 2):
        p1, p2 = selected[i], selected[i+1]
        cross_point = random.randint(1, len(param_bounds)-1)
        c1 = p1[:cross_point] + p2[cross_point:]
        c2 = p2[:cross_point] + p1[cross_point:]
        offspring.extend([c1, c2])

    for ind in offspring:
        if random.random() < mutation_rate:
            gene = random.randint(0, len(param_bounds)-1)
            ind[gene] = random.uniform(*param_bounds[gene])

    population = offspring

best_params = population[np.argmin([run_simulation(ind) for ind in population])]
print("\n✅ 最优参数:")
print(f"war_prob = {best_params[0]:.4f}")
print(f"emergence_prob = {best_params[1]:.4f}")
print(f"energy_tech 初值 = {best_params[2]:.4f}")
print(f"environment_tech 初值 = {best_params[3]:.4f}")
print(f"research_budget 初值 = {best_params[4]:.4f}")