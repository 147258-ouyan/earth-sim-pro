"""
地球模拟器 Pro++ Streamlit 前端 (场景对比增强版 · 修复环境图表负值)
运行方式：streamlit run app.py
"""
import streamlit as st
import pandas as pd
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pydeck as pdk
from earth_sim.world import World

# ---------- 页面配置 ----------
st.set_page_config(page_title="地球模拟器 Pro++", layout="wide")
st.title("🌍 地球模拟器 Pro++")
st.markdown("调节参数，观察文明的命运。支持真实历史校准、世界地图、双场景对比。")

# ---------- 侧边栏：全局控制 ----------
st.sidebar.header("⚙️ 全局设置")
compare_mode = st.sidebar.checkbox("🔁 场景对比模式（同时运行两条世界线）", value=False)

years_to_run = st.sidebar.number_input("模拟年数", min_value=10, max_value=500, value=100, step=10)

auto_mode = st.sidebar.checkbox("🎬 自动推演动画", value=False)
auto_speed = 0.2
if auto_mode:
    auto_speed = st.sidebar.slider("动画速度（秒/年）", 0.05, 1.0, 0.2, 0.05)

use_real_data = st.sidebar.checkbox("📊 使用真实历史数据校准 (1900-2020)", value=True)

# ---------- 场景参数配置 ----------
if compare_mode:
    st.sidebar.subheader("🌍 场景 A 参数")
    war_prob_a = st.sidebar.slider("战争概率 A", 0.0, 0.2, 0.01, key="war_a")
    proxy_prob_a = st.sidebar.slider("代理人战争概率 A", 0.0, 0.1, 0.01, key="proxy_a")
    emergence_prob_a = st.sidebar.slider("涌现事件概率 A", 0.0, 0.2, 0.03, key="emerg_a")
    green_policy_a = st.sidebar.slider("初始绿色政策 A", 0.0, 1.0, 0.1, key="green_a")

    st.sidebar.subheader("🌏 场景 B 参数")
    war_prob_b = st.sidebar.slider("战争概率 B", 0.0, 0.2, 0.05, key="war_b")
    proxy_prob_b = st.sidebar.slider("代理人战争概率 B", 0.0, 0.1, 0.03, key="proxy_b")
    emergence_prob_b = st.sidebar.slider("涌现事件概率 B", 0.0, 0.2, 0.05, key="emerg_b")
    green_policy_b = st.sidebar.slider("初始绿色政策 B", 0.0, 1.0, 0.5, key="green_b")
else:
    st.sidebar.subheader("⚙️ 全局参数")
    war_prob = st.sidebar.slider("战争概率", 0.0, 0.2, 0.01)
    proxy_prob = st.sidebar.slider("代理人战争概率", 0.0, 0.1, 0.01)
    emergence_prob = st.sidebar.slider("涌现事件概率", 0.0, 0.2, 0.03)

# ---------- 世界初始化 ----------
if not compare_mode:
    if "world" not in st.session_state:
        st.session_state.world = World(apply_historical=use_real_data)
    world = st.session_state.world
else:
    if "world_a" not in st.session_state:
        st.session_state.world_a = World(apply_historical=use_real_data)
    if "world_b" not in st.session_state:
        st.session_state.world_b = World(apply_historical=use_real_data)
    world_a = st.session_state.world_a
    world_b = st.session_state.world_b

if st.sidebar.button("🔄 重置世界到 1900 年"):
    if not compare_mode:
        st.session_state.world = World(apply_historical=use_real_data)
        world = st.session_state.world
    else:
        st.session_state.world_a = World(apply_historical=use_real_data)
        st.session_state.world_b = World(apply_historical=use_real_data)
        world_a = st.session_state.world_a
        world_b = st.session_state.world_b
    st.success("世界已重置到 1900 年")

# ---------- 模拟执行 ----------
if st.sidebar.button("▶️ 开始模拟"):
    if compare_mode:
        # 设置场景参数
        params_a = {
            "war_prob": war_prob_a,
            "proxy_prob": proxy_prob_a,
            "emergence_prob": emergence_prob_a,
            "global_green_policy": green_policy_a,
        }
        params_b = {
            "war_prob": war_prob_b,
            "proxy_prob": proxy_prob_b,
            "emergence_prob": emergence_prob_b,
            "global_green_policy": green_policy_b,
        }
        world_a.params.update(params_a)
        world_b.params.update(params_b)

        # 并排展示实时动画
        col1, col2 = st.columns(2)
        placeholder_env_a = col1.empty()
        placeholder_gdp_a = col1.empty()
        placeholder_env_b = col2.empty()
        placeholder_gdp_b = col2.empty()

        progress_bar = st.progress(0)
        for i in range(years_to_run):
            world_a.run_year()
            world_b.run_year()
            progress_bar.progress((i + 1) / years_to_run)

            # 更新场景A图表
            with placeholder_env_a.container():
                st.subheader("场景 A - 环境健康度")
                years_a = list(range(1900, world_a.year + 1))
                env_a = world_a.env_history[:len(years_a)]
                fig_a, ax_a = plt.subplots(figsize=(8, 3))
                ax_a.plot(years_a, env_a, color='green')
                ax_a.set_ylim(0, 100)
                ax_a.set_ylabel("环境指数")
                ax_a.grid(True, alpha=0.3)
                st.pyplot(fig_a)
                plt.close(fig_a)
            with placeholder_gdp_a.container():
                st.subheader("场景 A - GDP 前三强")
                top3_a = sorted([c for c in world_a.countries if c.alive],
                                key=lambda x: x.gdp, reverse=True)[:3]
                gdp_data_a = {"国家": [c.name for c in top3_a], "GDP (B)": [c.gdp for c in top3_a]}
                st.bar_chart(pd.DataFrame(gdp_data_a).set_index("国家"))

            # 更新场景B图表
            with placeholder_env_b.container():
                st.subheader("场景 B - 环境健康度")
                years_b = list(range(1900, world_b.year + 1))
                env_b = world_b.env_history[:len(years_b)]
                fig_b, ax_b = plt.subplots(figsize=(8, 3))
                ax_b.plot(years_b, env_b, color='orange')
                ax_b.set_ylim(0, 100)
                ax_b.set_ylabel("环境指数")
                ax_b.grid(True, alpha=0.3)
                st.pyplot(fig_b)
                plt.close(fig_b)
            with placeholder_gdp_b.container():
                st.subheader("场景 B - GDP 前三强")
                top3_b = sorted([c for c in world_b.countries if c.alive],
                                key=lambda x: x.gdp, reverse=True)[:3]
                gdp_data_b = {"国家": [c.name for c in top3_b], "GDP (B)": [c.gdp for c in top3_b]}
                st.bar_chart(pd.DataFrame(gdp_data_b).set_index("国家"))

            if auto_mode:
                time.sleep(auto_speed)

        st.success(f"对比模拟完成！场景 A 年份：{world_a.year}，场景 B 年份：{world_b.year}")

        # ----------------- 详细对比结果 -----------------
        st.subheader("📊 详细对比结果")

        # 最终静态环境与 GDP
        col_env_a, col_env_b = st.columns(2)
        with col_env_a:
            st.subheader("场景 A - 环境健康度")
            years_a = list(range(1900, world_a.year + 1))
            env_a = world_a.env_history[:len(years_a)]
            fig_a, ax_a = plt.subplots(figsize=(8, 3))
            ax_a.plot(years_a, env_a, color='green')
            ax_a.set_ylim(0, 100)
            ax_a.set_ylabel("环境指数")
            ax_a.grid(True, alpha=0.3)
            st.pyplot(fig_a)
            plt.close(fig_a)

            st.subheader("场景 A - GDP 前三强")
            top3_a = sorted([c for c in world_a.countries if c.alive],
                            key=lambda x: x.gdp, reverse=True)[:3]
            gdp_data_a = {"国家": [c.name for c in top3_a], "GDP (B)": [c.gdp for c in top3_a]}
            st.bar_chart(pd.DataFrame(gdp_data_a).set_index("国家"))

        with col_env_b:
            st.subheader("场景 B - 环境健康度")
            years_b = list(range(1900, world_b.year + 1))
            env_b = world_b.env_history[:len(years_b)]
            fig_b, ax_b = plt.subplots(figsize=(8, 3))
            ax_b.plot(years_b, env_b, color='orange')
            ax_b.set_ylim(0, 100)
            ax_b.set_ylabel("环境指数")
            ax_b.grid(True, alpha=0.3)
            st.pyplot(fig_b)
            plt.close(fig_b)

            st.subheader("场景 B - GDP 前三强")
            top3_b = sorted([c for c in world_b.countries if c.alive],
                            key=lambda x: x.gdp, reverse=True)[:3]
            gdp_data_b = {"国家": [c.name for c in top3_b], "GDP (B)": [c.gdp for c in top3_b]}
            st.bar_chart(pd.DataFrame(gdp_data_b).set_index("国家"))

        # 国家详情对比
        st.subheader("🏛️ 国家详情对比")
        col_tab_a, col_tab_b = st.columns(2)
        with col_tab_a:
            st.markdown("**场景 A**")
            country_data_a = []
            for c in sorted(world_a.countries, key=lambda x: x.gdp, reverse=True)[:10]:
                country_data_a.append({
                    "国家": c.name,
                    "人口(M)": f"{c.population:.0f}",
                    "GDP(B)": f"{c.gdp:.0f}",
                    "稳定度": f"{c.stability:.2f}",
                    "政体": c.government,
                    "意识形态": c.main_ideology[:4],
                    "AI": "🤖" if c.ai_controlled else ""
                })
            st.dataframe(pd.DataFrame(country_data_a), use_container_width=True)
        with col_tab_b:
            st.markdown("**场景 B**")
            country_data_b = []
            for c in sorted(world_b.countries, key=lambda x: x.gdp, reverse=True)[:10]:
                country_data_b.append({
                    "国家": c.name,
                    "人口(M)": f"{c.population:.0f}",
                    "GDP(B)": f"{c.gdp:.0f}",
                    "稳定度": f"{c.stability:.2f}",
                    "政体": c.government,
                    "意识形态": c.main_ideology[:4],
                    "AI": "🤖" if c.ai_controlled else ""
                })
            st.dataframe(pd.DataFrame(country_data_b), use_container_width=True)

        # 事件日志对比
        st.subheader("📢 事件日志对比")
        col_log_a, col_log_b = st.columns(2)
        with col_log_a:
            st.markdown("**场景 A 最近事件**")
            if world_a.events_log:
                for event in world_a.events_log[-20:]:
                    st.text(event)
            else:
                st.text("无事件")
        with col_log_b:
            st.markdown("**场景 B 最近事件**")
            if world_b.events_log:
                for event in world_b.events_log[-20:]:
                    st.text(event)
            else:
                st.text("无事件")

        # 世界地图对比
        st.subheader("🗺️ 世界地图对比")
        col_map_a, col_map_b = st.columns(2)
        COUNTRY_COORDS = {
            "华夏": (35.0, 105.0), "美利坚": (38.0, -97.0), "俄罗斯": (60.0, 90.0),
            "不列颠": (54.0, -2.0), "法兰西": (46.0, 2.0), "德意志": (51.0, 10.0),
            "日本": (36.0, 138.0), "意大利": (42.8, 12.5), "印度": (20.0, 78.0),
            "巴西": (-10.0, -55.0), "加拿大": (60.0, -95.0), "澳大利亚": (-25.0, 135.0),
            "阿根廷": (-34.0, -64.0), "南非": (-29.0, 24.0), "土耳其": (39.0, 35.0),
            "巴基斯坦": (30.0, 70.0), "以色列": (31.0, 35.0),
        }
        with col_map_a:
            map_data_a = []
            for c in world_a.countries:
                if c.alive and c.name in COUNTRY_COORDS:
                    lat, lon = COUNTRY_COORDS[c.name]
                    if c.stability > 0.7:
                        color = [0, 255, 0, 160]
                    elif c.stability > 0.4:
                        color = [255, 255, 0, 160]
                    else:
                        color = [255, 0, 0, 160]
                    map_data_a.append({"name": c.name, "lat": lat, "lon": lon,
                                       "stability": c.stability, "gdp": c.gdp, "color": color})
            if map_data_a:
                df_map_a = pd.DataFrame(map_data_a)
                layer_a = pdk.Layer("ScatterplotLayer", df_map_a, get_position=["lon", "lat"],
                                    get_radius=300000, get_fill_color="color", pickable=True)
                st.pydeck_chart(pdk.Deck(layers=[layer_a], initial_view_state=pdk.ViewState(latitude=20, longitude=0, zoom=1),
                                         tooltip={"text": "{name}\n稳定度: {stability}\nGDP: {gdp}"}))
            else:
                st.text("无数据")
        with col_map_b:
            map_data_b = []
            for c in world_b.countries:
                if c.alive and c.name in COUNTRY_COORDS:
                    lat, lon = COUNTRY_COORDS[c.name]
                    if c.stability > 0.7:
                        color = [0, 255, 0, 160]
                    elif c.stability > 0.4:
                        color = [255, 255, 0, 160]
                    else:
                        color = [255, 0, 0, 160]
                    map_data_b.append({"name": c.name, "lat": lat, "lon": lon,
                                       "stability": c.stability, "gdp": c.gdp, "color": color})
            if map_data_b:
                df_map_b = pd.DataFrame(map_data_b)
                layer_b = pdk.Layer("ScatterplotLayer", df_map_b, get_position=["lon", "lat"],
                                    get_radius=300000, get_fill_color="color", pickable=True)
                st.pydeck_chart(pdk.Deck(layers=[layer_b], initial_view_state=pdk.ViewState(latitude=20, longitude=0, zoom=1),
                                         tooltip={"text": "{name}\n稳定度: {stability}\nGDP: {gdp}"}))
            else:
                st.text("无数据")

        # 报告下载（对比模式）—— 打包成一个 ZIP 文件
        st.subheader("📄 报告下载")
        # 先生成两个 HTML 文件到临时目录
        import tempfile, zipfile, io

        report_a_name = f"report_scenario_A_{world_a.year}.html"
        report_b_name = f"report_scenario_B_{world_b.year}.html"

        # 生成报告内容（写入临时文件）
        world_a.generate_report(report_a_name)
        world_b.generate_report(report_b_name)

        # 创建内存中的 ZIP 文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(report_a_name, arcname=report_a_name)
            zip_file.write(report_b_name, arcname=report_b_name)
        zip_buffer.seek(0)

        # 提供单个下载按钮，一次下载两份报告
        st.download_button(
            label="📥 下载完整报告（场景A + 场景B）",
            data=zip_buffer,
            file_name=f"reports_{world_a.year}.zip",
            mime="application/zip",
            key="report_zip"
        )

        # 清理临时文件（可选）
        import os

        os.remove(report_a_name)
        os.remove(report_b_name)

    else:
        # 单世界模拟
        world.params["war_prob"] = war_prob
        world.params["proxy_prob"] = proxy_prob
        world.params["emergence_prob"] = emergence_prob

        if auto_mode:
            placeholder_env = st.empty()
            placeholder_gdp = st.empty()
            progress_bar = st.progress(0)
            for i in range(years_to_run):
                world.run_year()
                progress_bar.progress((i + 1) / years_to_run)
                with placeholder_env.container():
                    st.subheader("环境健康度历史")
                    years = list(range(1900, world.year + 1))
                    env = world.env_history[:len(years)]
                    fig, ax = plt.subplots(figsize=(8, 3))
                    ax.plot(years, env, color='green')
                    ax.set_ylim(0, 100)
                    ax.set_ylabel("环境指数")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    plt.close(fig)
                with placeholder_gdp.container():
                    st.subheader("GDP 前三强")
                    top3 = sorted([c for c in world.countries if c.alive],
                                  key=lambda x: x.gdp, reverse=True)[:3]
                    gdp_data = {"国家": [c.name for c in top3], "GDP (B)": [c.gdp for c in top3]}
                    st.bar_chart(pd.DataFrame(gdp_data).set_index("国家"))
                time.sleep(auto_speed)
            st.success(f"自动推演完成！当前年份：{world.year}")
        else:
            progress_bar = st.progress(0)
            for i in range(years_to_run):
                world.run_year()
                progress_bar.progress((i + 1) / years_to_run)
            st.success(f"模拟完成！当前年份：{world.year}")

        # 最终静态结果
        st.subheader("📊 最终状态")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("环境健康度历史")
            years = list(range(1900, world.year + 1))
            env = world.env_history[:len(years)]
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(years, env, color='green')
            ax.set_ylim(0, 100)
            ax.set_ylabel("环境指数")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)
        with col2:
            st.subheader("GDP 前三强")
            top3 = sorted([c for c in world.countries if c.alive],
                          key=lambda x: x.gdp, reverse=True)[:3]
            gdp_data = {"国家": [c.name for c in top3], "GDP (B)": [c.gdp for c in top3]}
            st.bar_chart(pd.DataFrame(gdp_data).set_index("国家"))

        st.subheader("🏛️ 国家详情")
        country_list = []
        for c in sorted(world.countries, key=lambda x: x.gdp, reverse=True)[:12]:
            country_list.append({
                "国家": c.name,
                "人口 (M)": f"{c.population:.0f}",
                "GDP (B)": f"{c.gdp:.0f}",
                "物质GDP": f"{c.material_gdp:.0f}",
                "服务GDP": f"{c.service_gdp:.0f}",
                "稳定度": f"{c.stability:.2f}",
                "政体": c.government,
                "意识形态": c.main_ideology[:4],
                "AI": "🤖" if c.ai_controlled else ""
            })
        st.dataframe(pd.DataFrame(country_list))

        # 世界地图
        st.subheader("🌍 世界地图（稳定度）")
        COUNTRY_COORDS = {
            "华夏": (35.0, 105.0), "美利坚": (38.0, -97.0), "俄罗斯": (60.0, 90.0),
            "不列颠": (54.0, -2.0), "法兰西": (46.0, 2.0), "德意志": (51.0, 10.0),
            "日本": (36.0, 138.0), "意大利": (42.8, 12.5), "印度": (20.0, 78.0),
            "巴西": (-10.0, -55.0), "加拿大": (60.0, -95.0), "澳大利亚": (-25.0, 135.0),
            "阿根廷": (-34.0, -64.0), "南非": (-29.0, 24.0), "土耳其": (39.0, 35.0),
            "巴基斯坦": (30.0, 70.0), "以色列": (31.0, 35.0),
        }
        map_data = []
        for c in world.countries:
            if c.alive and c.name in COUNTRY_COORDS:
                lat, lon = COUNTRY_COORDS[c.name]
                if c.stability < 0.4:
                    color = [255, 0, 0, 160]
                elif c.stability < 0.7:
                    color = [255, 255, 0, 160]
                else:
                    color = [0, 255, 0, 160]
                map_data.append({
                    "name": c.name, "lat": lat, "lon": lon,
                    "stability": c.stability, "gdp": c.gdp, "color": color
                })
        if map_data:
            df_map = pd.DataFrame(map_data)
            layer = pdk.Layer(
                "ScatterplotLayer", df_map,
                get_position=["lon", "lat"],
                get_radius=300000,
                get_fill_color="color",
                pickable=True
            )
            view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1)
            st.pydeck_chart(pdk.Deck(
                layers=[layer], initial_view_state=view_state,
                tooltip={"text": "{name}\n稳定度: {stability}\nGDP: {gdp}"}
            ))

        # 报告下载
        report_file = f"report_{world.year}.html"
        world.generate_report(report_file)
        with open(report_file, "rb") as f:
            st.download_button(label="📥 下载完整报告", data=f, file_name=report_file, mime="text/html")

# 初始状态提示
if not compare_mode and 'world' in locals() and world.year == 1900:
    st.info("👆 请在侧边栏点击“开始模拟”来启动文明演化。")
elif compare_mode and 'world_a' in locals() and world_a.year == 1900:
    st.info("👆 已启用场景对比模式。请在侧边栏设置两组参数，然后点击“开始模拟”。")