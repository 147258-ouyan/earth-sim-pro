"""
地球模拟器 Pro++ 在线演示版
功能：单场景推演、蒙特卡洛预测、敏感性分析
获取桌面专业版（含双场景对比、Tornado图、实验矩阵、PDF报告等）请访问你的下载页面
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import copy

# 字体设置：尝试加载中文字体文件，否则可能显示方块
try:
    import matplotlib.font_manager as fm
    font_path = 'chinese_font.ttf'   # 请将此字体文件上传到仓库根目录
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    matplotlib.rcParams['font.family'] = prop.get_name()
except:
    matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS', 'Noto Sans CJK SC']

matplotlib.rcParams['axes.unicode_minus'] = False

from earth_sim.world import World

# ---------- 页面配置 ----------
st.set_page_config(page_title="地球模拟器 Pro++ 在线演示", layout="wide")
st.title("🌍 地球模拟器 Pro++ 在线演示")
st.markdown("调节参数，观察文明的命运。**想要更多功能？请下载桌面专业版！**")
st.info("📥 **桌面专业版** 包含双场景对比、Tornado图、实验矩阵、时间线回放、PDF报告、AI新闻等全部功能，点击[此处](#)下载（请替换为你的下载链接）。")

# ---------- 侧边栏参数 ----------
st.sidebar.header("⚙️ 参数设置")
war_prob = st.sidebar.slider("战争概率", 0.0, 0.2, 0.01, 0.005)
green_policy = st.sidebar.slider("绿色政策力度", 0.0, 1.0, 0.1, 0.01)
years_to_run = st.sidebar.number_input("模拟年数", 10, 200, 50, step=10)

# ---------- 初始化世界 ----------
if "world" not in st.session_state:
    st.session_state.world = World()
world = st.session_state.world

# ---------- 运行模拟 ----------
if st.sidebar.button("▶️ 开始模拟"):
    world.params["war_prob"] = war_prob
    world.params["global_green_policy"] = green_policy

    progress_bar = st.progress(0)
    status_text = st.empty()
    for i in range(years_to_run):
        world.run_year()
        progress_bar.progress((i + 1) / years_to_run)
        status_text.text(f"当前年份: {world.year}")

    st.success(f"模拟完成！当前年份: {world.year}")

    # ---------- 环境曲线 ----------
    st.subheader("📊 环境健康度")
    years = list(range(1900, world.year + 1))
    env = world.env_history[:len(years)]
    st.line_chart(pd.DataFrame({"年份": years, "环境": env}).set_index("年份"))

    # ---------- GDP 前三 ----------
    st.subheader("💰 GDP 前三强")
    top3 = sorted([c for c in world.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
    gdp_data = {"国家": [c.name for c in top3], "GDP(B)": [c.gdp for c in top3]}
    st.bar_chart(pd.DataFrame(gdp_data).set_index("国家"))

    # ---------- 国家详情 ----------
    st.subheader("🏛️ 国家详情")
    country_list = []
    for c in sorted(world.countries, key=lambda x: x.gdp, reverse=True)[:12]:
        country_list.append({
            "国家": c.name,
            "人口(M)": f"{c.population:.0f}",
            "GDP(B)": f"{c.gdp:.0f}",
            "稳定度": f"{c.stability:.2f}",
            "政体": c.government
        })
    st.dataframe(pd.DataFrame(country_list))

# ---------- 蒙特卡洛预测 ----------
st.sidebar.header("📊 蒙特卡洛预测")
mc_sims = st.sidebar.number_input("模拟次数", 10, 200, 50, key="mc_sims")
mc_years = st.sidebar.number_input("预测年数", 10, 100, 30, key="mc_years")

if st.sidebar.button("开始蒙特卡洛预测"):
    st.write("正在运行蒙特卡洛模拟，请稍候...")
    progress = st.progress(0)
    futures = []
    for i in range(mc_sims):
        w = copy.deepcopy(world)
        for _ in range(mc_years):
            w.run_year()
        futures.append(w.global_environment)
        progress.progress((i + 1) / mc_sims)

    mean = np.mean(futures)
    p10 = np.percentile(futures, 10)
    p90 = np.percentile(futures, 90)

    st.write(f"均值: {mean:.1f}  90%区间: [{p10:.1f}, {p90:.1f}]")
    fig, ax = plt.subplots()
    ax.hist(futures, bins=20, color='skyblue', edgecolor='black')
    ax.axvline(mean, color='red', linestyle='dashed', label=f'均值:{mean:.1f}')
    ax.set_title("环境健康度分布")
    ax.legend()
    st.pyplot(fig)

# ---------- 敏感性分析 ----------
st.sidebar.header("📈 敏感性分析")
sens_param = st.sidebar.selectbox("选择参数", ["war_prob", "emission_intensity", "global_green_policy", "mat_base"])
sens_min = st.sidebar.number_input("最小值", value=0.0, step=0.001)
sens_max = st.sidebar.number_input("最大值", value=0.1, step=0.01)
sens_steps = st.sidebar.number_input("步数", 2, 50, 10, key="sens_steps")

if st.sidebar.button("开始敏感性分析"):
    st.write("正在运行敏感性分析...")
    values = np.linspace(sens_min, sens_max, sens_steps)
    results = []
    progress = st.progress(0)
    for i, val in enumerate(values):
        w = copy.deepcopy(world)
        w.params[sens_param] = val
        for _ in range(50):
            w.run_year()
        results.append(w.global_environment)
        progress.progress((i + 1) / sens_steps)

    fig, ax = plt.subplots()
    ax.plot(values, results, 'o-', color='purple')
    ax.set_xlabel(sens_param)
    ax.set_ylabel("最终环境健康度")
    ax.set_title("敏感性分析")
    st.pyplot(fig)

# ---------- 底部引流 ----------
st.markdown("---")
st.markdown("## 🚀 想获得完整功能？")
st.markdown("下载 **桌面专业版**，解锁双场景对比、Tornado 图、实验矩阵、时间线回放、PDF 报告、AI 新闻等全部高级功能！")
st.markdown("📥 点击[此处](#)下载（请替换为你的实际下载链接）")
