"""
蒙特卡洛并行预测脚本
功能：并行运行 N 次模拟，输出环境健康度的概率分布
使用：python monte_carlo.py --sims 100 --years 80 --workers 4
"""
import numpy as np
import argparse
from earth_sim.world import World
from multiprocessing import Pool
import time
import json


def run_single_simulation(seed):
    """运行一次模拟，返回每年的环境健康度"""
    np.random.seed(seed)
    import random
    random.seed(seed)

    w = World(apply_historical=True)  # 使用历史校准
    env_history = []

    # 运行到2025年（历史校准阶段）
    for _ in range(126):  # 1900 -> 2026
        w.run_year()

    # 记录2026年的环境值
    env_history.append(w.global_environment)

    # 自由推演到2100年
    for _ in range(74):  # 2026 -> 2100
        w.run_year()
        env_history.append(w.global_environment)

    return {
        'seed': seed,
        'env_2026': env_history[0],
        'env_2050': env_history[24],
        'env_2075': env_history[49],
        'env_2100': env_history[-1],
        'env_min': min(env_history),
        'env_max': max(env_history),
        'final_countries': len(w.countries),
        'final_gdp_total': sum(c.gdp for c in w.countries if c.alive),
        'final_pop_total': sum(c.population for c in w.countries if c.alive)
    }


def main():
    parser = argparse.ArgumentParser(description='地球模拟器 Pro++ 蒙特卡洛预测')
    parser.add_argument('--sims', type=int, default=100, help='模拟次数 (默认100)')
    parser.add_argument('--years', type=int, default=80, help='预测年数 (默认80)')
    parser.add_argument('--workers', type=int, default=4, help='并行进程数 (默认4)')
    args = parser.parse_args()

    print(f"🚀 开始蒙特卡洛模拟：{args.sims} 次 × {args.years} 年，{args.workers} 核并行")
    start_time = time.time()

    seeds = list(range(args.sims))

    with Pool(processes=args.workers) as pool:
        results = pool.map(run_single_simulation, seeds)

    elapsed = time.time() - start_time
    print(f"✅ 完成！耗时 {elapsed:.1f} 秒")

    # 统计分析
    env_2026 = [r['env_2026'] for r in results]
    env_2050 = [r['env_2050'] for r in results]
    env_2075 = [r['env_2075'] for r in results]
    env_2100 = [r['env_2100'] for r in results]
    final_countries = [r['final_countries'] for r in results]

    stats = {
        'env_2026': {
            'mean': np.mean(env_2026),
            'median': np.median(env_2026),
            'p10': np.percentile(env_2026, 10),
            'p90': np.percentile(env_2026, 90),
            'min': np.min(env_2026),
            'max': np.max(env_2026)
        },
        'env_2050': {
            'mean': np.mean(env_2050),
            'median': np.median(env_2050),
            'p10': np.percentile(env_2050, 10),
            'p90': np.percentile(env_2050, 90),
            'min': np.min(env_2050),
            'max': np.max(env_2050)
        },
        'env_2075': {
            'mean': np.mean(env_2075),
            'median': np.median(env_2075),
            'p10': np.percentile(env_2075, 10),
            'p90': np.percentile(env_2075, 90),
            'min': np.min(env_2075),
            'max': np.max(env_2075)
        },
        'env_2100': {
            'mean': np.mean(env_2100),
            'median': np.median(env_2100),
            'p10': np.percentile(env_2100, 10),
            'p90': np.percentile(env_2100, 90),
            'min': np.min(env_2100),
            'max': np.max(env_2100),
            'collapse_prob': sum(1 for v in env_2100 if v < 15) / len(env_2100)
        },
        'final_countries_mean': np.mean(final_countries),
        'total_sims': args.sims,
        'elapsed_seconds': elapsed
    }

    print("\n📊 环境健康度概率分布：")
    print(
        f"  2026年: 均值 {stats['env_2026']['mean']:.1f}, 90%区间 [{stats['env_2026']['p10']:.1f}, {stats['env_2026']['p90']:.1f}]")
    print(
        f"  2050年: 均值 {stats['env_2050']['mean']:.1f}, 90%区间 [{stats['env_2050']['p10']:.1f}, {stats['env_2050']['p90']:.1f}]")
    print(
        f"  2075年: 均值 {stats['env_2075']['mean']:.1f}, 90%区间 [{stats['env_2075']['p10']:.1f}, {stats['env_2075']['p90']:.1f}]")
    print(
        f"  2100年: 均值 {stats['env_2100']['mean']:.1f}, 90%区间 [{stats['env_2100']['p10']:.1f}, {stats['env_2100']['p90']:.1f}]")
    print(f"  2100年生态崩溃概率: {stats['env_2100']['collapse_prob'] * 100:.1f}%")
    print(f"  平均存活国家数: {stats['final_countries_mean']:.1f}")

    # 保存结果
    with open('monte_carlo_results.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print("\n📁 详细结果已保存至 monte_carlo_results.json")


if __name__ == '__main__':
    main()