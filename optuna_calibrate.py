"""
深度校准脚本：使用 Optuna 自动寻找最优参数
运行：python optuna_calibrate.py
生成 best_params.json 供 generate_fit_report.py 使用
"""
import json
import numpy as np
import pandas as pd
import optuna
import warnings
from earth_sim.world import World

warnings.filterwarnings('ignore')

# ========== 1. 加载真实数据，并自动对齐可用年份 ==========
real = pd.read_csv("historical_data_real.csv")
gdp_series = real.groupby("year")["gdp"].sum()
pop_series = real.groupby("year")["population"].sum()
if "co2" in real.columns:
    co2_series = real.groupby("year")["co2"].sum()
else:
    co2_series = None

# 找出三个指标都有数据的年份（交集）
common_years = gdp_series.index.intersection(pop_series.index)
if co2_series is not None:
    common_years = common_years.intersection(co2_series.index)

# 只保留 1900-2020 之间的年份
common_years = common_years[(common_years >= 1900) & (common_years <= 2020)]
common_years = sorted(common_years)

# 提取对齐后的真实数据数组
real_gdp = gdp_series.loc[common_years].values
real_pop = pop_series.loc[common_years].values
if co2_series is not None:
    real_co2 = co2_series.loc[common_years].values
else:
    real_co2 = None

N_YEARS = len(common_years)  # 实际要模拟的年数
print(f"真实数据共有 {N_YEARS} 年（{common_years[0]} - {common_years[-1]}），将对齐模拟 {N_YEARS} 年。")


# ========== 2. 定义 Optuna 目标函数 ==========
def objective(trial):
    # 采样关键参数
    params = {
        "mat_base": trial.suggest_float("mat_base", 0.01, 0.04),
        "mat_industry_coef": trial.suggest_float("mat_industry_coef", 0.005, 0.02),
        "serv_base": trial.suggest_float("serv_base", 0.02, 0.04),
        "serv_info_coef": trial.suggest_float("serv_info_coef", 0.004, 0.015),
        "birth_rate_young": trial.suggest_float("birth_rate_young", 0.04, 0.08),
        "death_old_base": trial.suggest_float("death_old_base", 0.1, 0.16),
        "institutional_entropy_divisor": trial.suggest_float("institutional_entropy_divisor", 3e7, 1e8),
        "emission_intensity": trial.suggest_float("emission_intensity", 1e-5, 1e-4, log=True),
        "war_prob": trial.suggest_float("war_prob", 0.005, 0.05),
    }

    # 创建世界并运行 N_YEARS 年
    world = World(params=params, apply_historical=False)
    gdp_hist, pop_hist, env_hist = [], [], []
    for _ in range(N_YEARS):
        world.run_year()
        total_gdp = sum(c.gdp for c in world.countries if c.alive)
        total_pop = sum(c.population for c in world.countries if c.alive)
        gdp_hist.append(total_gdp)
        pop_hist.append(total_pop)
        env_hist.append(world.global_environment)

    gdp_arr = np.array(gdp_hist)
    pop_arr = np.array(pop_hist)

    # 计算归一化误差
    gdp_err = np.mean(np.abs(gdp_arr - real_gdp) / (real_gdp + 1e-6))
    pop_err = np.mean(np.abs(pop_arr - real_pop) / (real_pop + 1e-6))
    total_err = (gdp_err + pop_err) / 2.0

    # 如果有 CO₂ 数据，加入环境误差（权重稍低）
    if real_co2 is not None:
        proxy_co2 = 100 - np.array(env_hist)  # 环境越好，排放越低（简单代理）
        co2_err = np.mean(np.abs(proxy_co2 - real_co2) / (real_co2 + 1e-6))
        total_err = (gdp_err + pop_err + co2_err * 0.5) / 2.5

    return total_err


# ========== 3. 启动优化 ==========
if __name__ == "__main__":
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42)
    )
    # 可以先设置 n_trials=20 测试，正式校准再加大到 100-200
    study.optimize(objective, n_trials=20, n_jobs=1)

    print("\n最优参数：")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")
    print(f"最优误差：{study.best_value:.4f}")

    # 保存最优参数
    with open("best_params.json", "w") as f:
        json.dump(study.best_params, f, indent=4)
    print("最优参数已保存至 best_params.json")

    # 保存全部试验记录
    df = study.trials_dataframe()
    df.to_csv("optuna_results.csv", index=False)