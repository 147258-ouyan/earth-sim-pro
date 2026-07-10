import sys
import os
import json
import numpy as np
import itertools
import csv
import shapefile
import webbrowser
import tempfile

# ---------- 字体设置 ----------
import matplotlib
matplotlib.use('QtAgg')

import matplotlib.font_manager as fm
import shutil

cache_dir = matplotlib.get_cachedir()
if os.path.exists(cache_dir):
    try:
        shutil.rmtree(cache_dir)
    except:
        pass

font_path_candidates = [
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\msyhbd.ttf',
    r'C:\Windows\Fonts\msyhl.ttc',
]
for fp in font_path_candidates:
    if os.path.exists(fp):
        fm.fontManager.addfont(fp)
        prop = fm.FontProperties(fname=fp)
        font_name = prop.get_name()
        matplotlib.rcParams['font.family'] = font_name
        matplotlib.rcParams['font.sans-serif'] = [font_name, 'Microsoft YaHei', 'SimHei']
        break
else:
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']

matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QSplitter, QProgressBar, QMessageBox,
    QCheckBox, QComboBox, QSpinBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QLineEdit, QSplashScreen
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QLinearGradient
from earth_sim.world import World
from scipy.stats import skew, kurtosis, shapiro
from PySide6.QtWidgets import QFileDialog
from scipy.stats import gaussian_kde
import matplotlib.pyplot as plt
# PDF 报告相关
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
import tempfile
import datetime

# ---------- 国家坐标 ----------
COUNTRY_COORDS = {
    "华夏": (35.0, 105.0), "美利坚": (38.0, -97.0), "俄罗斯": (60.0, 90.0),
    "不列颠": (54.0, -2.0), "法兰西": (46.0, 2.0), "德意志": (51.0, 10.0),
    "日本": (36.0, 138.0), "意大利": (42.8, 12.5), "印度": (20.0, 78.0),
    "巴西": (-10.0, -55.0), "加拿大": (60.0, -95.0), "澳大利亚": (-25.0, 135.0),
    "阿根廷": (-34.0, -64.0), "南非": (-29.0, 24.0), "土耳其": (39.0, 35.0),
    "巴基斯坦": (30.0, 70.0), "以色列": (31.0, 35.0),
}

# ---------- 模拟线程（支持快照记录）----------
class SimulationThread(QThread):
    progress = Signal(int)
    finished = Signal()
    year_changed = Signal(int)
    snapshot_taken = Signal(int)

    def __init__(self, world_a, world_b, years, record_snapshots=False):
        super().__init__()
        self.world_a = world_a
        self.world_b = world_b
        self.years = years
        self.record_snapshots = record_snapshots
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        if self.record_snapshots:
            if not hasattr(self.world_a, 'snapshots'):
                self.world_a.snapshots = []
            self.world_a.snapshots.append(self.world_a.to_dict())

        for i in range(self.years):
            if not self._is_running:
                break
            self.world_a.run_year()
            if self.world_b is not None:
                self.world_b.run_year()

            if self.record_snapshots:
                step = 1 if self.years <= 500 else 5
                if (i + 1) % step == 0 or (i + 1) == self.years:
                    self.world_a.snapshots.append(self.world_a.to_dict())
                    self.snapshot_taken.emit(self.world_a.year)

            self.progress.emit((i + 1) * 100 // self.years)
            self.year_changed.emit(self.world_a.year)
        self.finished.emit()

# ---------- 蒙特卡洛线程 ----------
class MonteCarloThread(QThread):
    progress = Signal(int)
    finished = Signal(dict)

    def __init__(self, world, num_sims, years):
        super().__init__()
        self.world = world
        self.num_sims = num_sims
        self.years = years
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        import copy
        futures = {self.world.year + self.years: []}
        for i in range(self.num_sims):
            if not self._is_running:
                break
            w = copy.deepcopy(self.world)
            for _ in range(self.years):
                w.run_year()
            last_year = self.world.year + self.years
            futures[last_year].append(w.global_environment)
            self.progress.emit((i + 1) * 100 // self.num_sims)
        if futures[last_year]:
            result = {
                "mean": np.mean(futures[last_year]),
                "p10": np.percentile(futures[last_year], 10),
                "p90": np.percentile(futures[last_year], 90),
                "hist_data": futures[last_year]
            }
        else:
            result = None
        self.finished.emit(result)

# ---------- 集合预测线程 ----------
class EnsembleThread(QThread):
    progress = Signal(int)
    finished = Signal(dict)

    def __init__(self, world, num_sims, years):
        super().__init__()
        self.world = world
        self.num_sims = num_sims
        self.years = years
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        import copy
        all_paths = []
        for i in range(self.num_sims):
            if not self._is_running:
                break
            w = copy.deepcopy(self.world)
            env_path = []
            for _ in range(self.years):
                w.run_year()
                env_path.append(w.global_environment)
            all_paths.append(env_path)
            self.progress.emit((i + 1) * 100 // self.num_sims)
        if all_paths:
            paths_array = np.array(all_paths)
            median = np.median(paths_array, axis=0)
            lower10 = np.percentile(paths_array, 10, axis=0)
            upper90 = np.percentile(paths_array, 90, axis=0)
            lower25 = np.percentile(paths_array, 25, axis=0)
            upper75 = np.percentile(paths_array, 75, axis=0)
            result = {
                "years": list(range(self.world.year, self.world.year + self.years)),
                "median": list(median),
                "lower10": list(lower10),
                "upper90": list(upper90),
                "lower25": list(lower25),
                "upper75": list(upper75),
            }
        else:
            result = None
        self.finished.emit(result)

# ---------- 敏感性分析线程 ----------
class SensitivityThread(QThread):
    progress = Signal(int)
    finished = Signal(dict)
    log = Signal(str)

    def __init__(self, world, param_name, param_min, param_max, steps, years):
        super().__init__()
        self.world = world
        self.param_name = param_name
        self.param_min = param_min
        self.param_max = param_max
        self.steps = steps
        self.years = years
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        import copy
        values = np.linspace(self.param_min, self.param_max, self.steps)
        results = []
        for i, val in enumerate(values):
            if not self._is_running:
                break
            w = copy.deepcopy(self.world)
            w.params[self.param_name] = val
            for _ in range(self.years):
                w.run_year()
            final_env = w.global_environment
            results.append(final_env)
            self.progress.emit((i + 1) * 100 // self.steps)
            self.log.emit(f"参数 {self.param_name}={val:.4f} → 环境 {final_env:.1f}")
        self.finished.emit({"values": list(values), "results": results})

# ---------- Matplotlib 画布 ----------
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(fig)
        self.setParent(parent)
        self.axes = fig.add_subplot(111)

    def clear_axes(self):
        self.axes.clear()
        self.draw()

# ---------- 政策冲击对话框 ----------
class PolicyShockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("政策冲击预设 · 叙事模式")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        self.template_combo = QComboBox()
        self.template_combo.addItem("自定义")
        self.template_combo.addItem("中美关税提高50%")
        self.template_combo.addItem("欧盟碳税翻倍")
        self.template_combo.addItem("全球科技封锁加剧")
        self.template_combo.addItem("绿色政策大倒退")
        self.template_combo.addItem("全球和平红利")
        self.template_combo.currentIndexChanged.connect(self.apply_template)
        layout.addWidget(QLabel("选择预设模板（可选）:"))
        layout.addWidget(self.template_combo)

        layout.addWidget(QLabel("✍️ 或用自然语言描述你想要的世界:"))
        self.narrative_edit = QTextEdit()
        self.narrative_edit.setMaximumHeight(80)
        self.narrative_edit.setPlaceholderText("例如：碳排放翻倍，第三次世界大战爆发...")
        layout.addWidget(self.narrative_edit)

        parse_btn = QPushButton("🧠 AI 解析叙事并应用")
        parse_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; padding: 8px; border-radius: 5px; }")
        parse_btn.clicked.connect(self.parse_narrative)
        layout.addWidget(parse_btn)

        form_group = QGroupBox("高级：手动微调参数")
        form = QFormLayout(form_group)
        self.war_prob_spin = QLineEdit("0.0166")
        self.emission_intensity_spin = QLineEdit("0.000012")
        self.green_policy_spin = QLineEdit("0.1")
        self.research_budget_spin = QLineEdit("0.8")
        self.trade_barrier_spin = QLineEdit("0.0")
        self.mat_base_spin = QLineEdit("0.024")
        self.birth_rate_spin = QLineEdit("0.062")
        form.addRow("战争概率:", self.war_prob_spin)
        form.addRow("排放强度:", self.emission_intensity_spin)
        form.addRow("绿色政策:", self.green_policy_spin)
        form.addRow("科研预算系数:", self.research_budget_spin)
        form.addRow("贸易壁垒:", self.trade_barrier_spin)
        form.addRow("经济增长率基础:", self.mat_base_spin)
        form.addRow("人口出生率:", self.birth_rate_spin)
        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_template(self, index):
        templates = {
            1: {"war_prob": "0.05", "emission_intensity": "0.000015", "green_policy": "0.05", "research_budget": "0.5", "trade_barrier": "0.5", "mat_base": "0.02", "birth_rate": "0.06"},
            2: {"war_prob": "0.01", "emission_intensity": "0.000008", "green_policy": "0.3", "research_budget": "1.0", "trade_barrier": "0.1", "mat_base": "0.025", "birth_rate": "0.062"},
            3: {"war_prob": "0.02", "emission_intensity": "0.00002", "green_policy": "0.05", "research_budget": "0.3", "trade_barrier": "0.8", "mat_base": "0.02", "birth_rate": "0.06"},
            4: {"war_prob": "0.01", "emission_intensity": "0.00003", "green_policy": "0.02", "research_budget": "0.2", "trade_barrier": "0.3", "mat_base": "0.018", "birth_rate": "0.05"},
            5: {"war_prob": "0.005", "emission_intensity": "0.000005", "green_policy": "0.5", "research_budget": "2.0", "trade_barrier": "0.0", "mat_base": "0.03", "birth_rate": "0.07"},
        }
        if index in templates:
            t = templates[index]
            self.war_prob_spin.setText(t["war_prob"])
            self.emission_intensity_spin.setText(t["emission_intensity"])
            self.green_policy_spin.setText(t["green_policy"])
            self.research_budget_spin.setText(t["research_budget"])
            self.trade_barrier_spin.setText(t["trade_barrier"])
            self.mat_base_spin.setText(t["mat_base"])
            self.birth_rate_spin.setText(t["birth_rate"])

    def parse_narrative(self):
        narrative = self.narrative_edit.toPlainText().strip()
        if not narrative:
            QMessageBox.warning(self, "提示", "请输入一段描述世界的文字")
            return
        prompt = f"""你是一个世界参数解析器。根据用户描述，提取以下参数的值(浮点数)，以JSON返回。
参数列表：
- war_prob (0.0-0.2, 默认0.0166)
- emission_intensity (0.0-0.0001, 默认0.000012)
- global_green_policy (0.0-1.0, 默认0.1)
- research_budget (0.1-30, 默认0.8)
- trade_barrier (0.0-1.0, 默认0.0)
- mat_base (0.01-0.04, 默认0.024)
- birth_rate_young (0.01-0.1, 默认0.062)

描述：{narrative}

只返回JSON对象，例如：{{"war_prob":0.05, "emission_intensity":0.00002, ...}}"""
        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if not api_key:
                QMessageBox.warning(self, "提示", "未设置 DeepSeek API Key，请点击左侧“API 设置”按钮进行设置")
                return
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200, temperature=0.3
            )
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rstrip("```")
            params = json.loads(result_text)
            for key, spin in [("war_prob", self.war_prob_spin), ("emission_intensity", self.emission_intensity_spin),
                              ("global_green_policy", self.green_policy_spin), ("research_budget", self.research_budget_spin),
                              ("trade_barrier", self.trade_barrier_spin), ("mat_base", self.mat_base_spin),
                              ("birth_rate_young", self.birth_rate_spin)]:
                if key in params:
                    spin.setText(str(params[key]))
            QMessageBox.information(self, "解析成功", f"AI已设置：{json.dumps(params, indent=2, ensure_ascii=False)}")
        except Exception as e:
            QMessageBox.warning(self, "解析失败", f"AI解析出错：{e}")

    def get_params(self):
        return {
            "war_prob": float(self.war_prob_spin.text()),
            "emission_intensity": float(self.emission_intensity_spin.text()),
            "global_green_policy": float(self.green_policy_spin.text()),
            "research_budget": float(self.research_budget_spin.text()),
            "trade_barrier": float(self.trade_barrier_spin.text()),
            "mat_base": float(self.mat_base_spin.text()),
            "birth_rate_young": float(self.birth_rate_spin.text()),
        }

# ---------- 实验矩阵对话框 ----------
class MatrixDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实验矩阵设置")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        self.param_checkboxes = {}
        self.param_values_edits = {}
        params = [
            ("war_prob", "战争概率"),
            ("emission_intensity", "排放强度"),
            ("global_green_policy", "绿色政策"),
            ("research_budget_per_capita", "科研预算"),
            ("trade_barrier", "贸易壁垒"),
            ("mat_base", "经济增长基础"),
        ]
        form = QFormLayout()
        for key, name in params:
            cb = QCheckBox(name)
            cb.setChecked(False)
            self.param_checkboxes[key] = cb
            edit = QLineEdit("")
            edit.setPlaceholderText("用逗号分隔取值，如: 0.01,0.02,0.03")
            self.param_values_edits[key] = edit
            form.addRow(cb, edit)
        layout.addLayout(form)

        self.years_spin = QSpinBox()
        self.years_spin.setRange(10, 200)
        self.years_spin.setValue(30)
        layout.addWidget(QLabel("预测年数:"))
        layout.addWidget(self.years_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_params(self):
        selected = {}
        for key, cb in self.param_checkboxes.items():
            if cb.isChecked():
                text = self.param_values_edits[key].text().strip()
                if text:
                    try:
                        vals = [float(v.strip()) for v in text.split(",")]
                        if vals:
                            selected[key] = vals
                    except:
                        QMessageBox.warning(self, "格式错误", f"参数 {key} 取值格式错误")
                        return None
        return selected

    def get_years(self):
        return self.years_spin.value()

# ---------- API 设置对话框 ----------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 设置")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("DeepSeek API Key（用于 AI 分析）："))
        self.ds_key_edit = QLineEdit()
        self.ds_key_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.ds_key_edit)

        layout.addWidget(QLabel("天行数据 API Key（用于获取国内新闻，在 https://www.tianapi.com 注册）："))
        self.news_key_edit = QLineEdit()
        self.news_key_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.news_key_edit)

        settings = QSettings("EarthSim", "ProPlusPlus")
        saved_ds = settings.value("deepseek_api_key", "")
        saved_news = settings.value("newsapi_key", "")
        if saved_ds:
            self.ds_key_edit.setText(saved_ds)
        if saved_news:
            self.news_key_edit.setText(saved_news)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_settings(self):
        settings = QSettings("EarthSim", "ProPlusPlus")
        settings.setValue("deepseek_api_key", self.ds_key_edit.text().strip())
        settings.setValue("newsapi_key", self.news_key_edit.text().strip())
        self.accept()

    @staticmethod
    def get_api_key(service="deepseek"):
        settings = QSettings("EarthSim", "ProPlusPlus")
        if service == "deepseek":
            key = settings.value("deepseek_api_key", "")
        elif service == "newsapi":
            key = settings.value("newsapi_key", "")
        else:
            key = ""
        if not key:
            try:
                with open("api_key.txt", "r") as f:
                    key = f.read().strip()
            except:
                pass
        return key

# ---------- 主窗口 ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("地球模拟器 Pro++ · 桌面版")
        self.resize(1600, 900)
        QApplication.setFont(QFont("Microsoft YaHei", 10))

        self.world_a = World()
        self.world_b = World()
        self.compare_mode = False
        self.simulation_running = False
        self.sim_thread = None
        self.mc_thread = None
        self.snapshots = []
        self.replay_enabled = False
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_splitter = QSplitter(Qt.Horizontal)

        # ===== 左侧面板 =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.compare_checkbox = QCheckBox("🔁 场景对比模式")
        self.compare_checkbox.stateChanged.connect(self.toggle_compare_mode)
        left_layout.addWidget(self.compare_checkbox)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(["1900 初始世界", "1914 一战前夕", "1939 二战前夕", "1991 冷战结束", "2020 疫情时期"])
        self.scenario_combo.currentIndexChanged.connect(self.load_preset)
        left_layout.addWidget(self.scenario_combo)

        self.settings_btn = QPushButton("🔑 API 设置")
        self.settings_btn.setStyleSheet("QPushButton { background-color: #607D8B; color: white; padding: 8px; border-radius: 5px; }")
        self.settings_btn.clicked.connect(self.open_settings)
        left_layout.addWidget(self.settings_btn)

        self.policy_btn = QPushButton("⚡ 政策冲击预设")
        self.policy_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 8px; border-radius: 5px; }")
        self.policy_btn.clicked.connect(self.open_policy_dialog)
        left_layout.addWidget(self.policy_btn)

        self.label_A = QLabel("🔹 场景 A 参数")
        left_layout.addWidget(self.label_A)
        self.war_a = self.create_slider("战争概率", 0, 20, 1, 100)
        self.proxy_a = self.create_slider("代理人战争概率", 0, 10, 1, 100)
        self.emerg_a = self.create_slider("涌现事件概率", 0, 20, 3, 100)
        self.green_a = self.create_slider("初始绿色政策", 0, 100, 10, 100)
        for w in [self.war_a, self.proxy_a, self.emerg_a, self.green_a]:
            left_layout.addWidget(w)

        self.label_B = QLabel("🔸 场景 B 参数")
        left_layout.addWidget(self.label_B)
        self.war_b = self.create_slider("战争概率", 0, 20, 5, 100)
        self.proxy_b = self.create_slider("代理人战争概率", 0, 10, 3, 100)
        self.emerg_b = self.create_slider("涌现事件概率", 0, 20, 5, 100)
        self.green_b = self.create_slider("初始绿色政策", 0, 100, 50, 100)
        for w in [self.war_b, self.proxy_b, self.emerg_b, self.green_b]:
            left_layout.addWidget(w)

        self.years_container = self.create_slider("模拟年数", 10, 200, 50, 1)
        left_layout.addWidget(self.years_container)

        btn_style = "QPushButton { padding: 8px; border-radius: 5px; color: white; font-weight: bold; }"
        self.start_btn = QPushButton("▶️ 开始模拟")
        self.start_btn.setStyleSheet(btn_style + "background-color: #4CAF50;")
        self.start_btn.clicked.connect(self.start_simulation)

        self.reset_btn = QPushButton("🔄 重置世界")
        self.reset_btn.setStyleSheet(btn_style + "background-color: #f44336;")
        self.reset_btn.clicked.connect(self.reset_world)

        self.report_btn = QPushButton("📄 导出完整报告")
        self.report_btn.setStyleSheet(btn_style + "background-color: #2196F3;")
        self.report_btn.clicked.connect(self.export_report)

        self.compare_report_btn = QPushButton("📊 生成对比报告")
        self.compare_report_btn.setStyleSheet(btn_style + "background-color: #FF5722;")
        self.compare_report_btn.clicked.connect(self.generate_compare_report)
        self.compare_report_btn.setEnabled(False)

        self.progress_bar = QProgressBar()
        self.current_year_label = QLabel("当前年份: 1900")
        self.current_year_label.setAlignment(Qt.AlignCenter)

        self.record_checkbox = QCheckBox("💾 记录历史快照（用于回放）")
        self.record_checkbox.stateChanged.connect(self.toggle_record_snapshots)
        left_layout.addWidget(self.record_checkbox)

        self.replay_slider = QSlider(Qt.Horizontal)
        self.replay_slider.setMinimum(1900)
        self.replay_slider.setMaximum(1900)
        self.replay_slider.setValue(1900)
        self.replay_slider.setEnabled(False)
        self.replay_slider.valueChanged.connect(self.replay_to_year)
        left_layout.addWidget(self.replay_slider)
        self.replay_label = QLabel("回放年份: 1900")
        left_layout.addWidget(self.replay_label)

        left_layout.addWidget(self.start_btn)
        left_layout.addWidget(self.reset_btn)
        left_layout.addWidget(self.report_btn)
        left_layout.addWidget(self.compare_report_btn)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(self.current_year_label)

        self.save_btn = QPushButton("💾 保存当前世界")
        self.save_btn.clicked.connect(self.save_current_world)
        left_layout.addWidget(self.save_btn)

        self.matrix_btn = QPushButton("📊 实验矩阵")
        self.matrix_btn.clicked.connect(self.run_experiment_matrix)
        left_layout.addWidget(self.matrix_btn)

        self.load_btn = QPushButton("📂 加载存档")
        self.load_btn.clicked.connect(self.load_archive)
        left_layout.addWidget(self.load_btn)

        self.ai_summary_label = QLabel("")
        self.ai_summary_label.setWordWrap(True)
        left_layout.addWidget(self.ai_summary_label)

        left_layout.addStretch()
        main_splitter.addWidget(left_panel)

        # ===== 右侧标签页 =====
        self.tabs = QTabWidget()

        # --- 环境曲线 ---
        env_widget = QWidget()
        env_layout = QHBoxLayout(env_widget)
        self.env_canvas_a = MplCanvas(self, width=5, height=3)
        self.env_canvas_b = MplCanvas(self, width=5, height=3)
        self.env_canvas_b.hide()
        env_layout.addWidget(self.env_canvas_a)
        env_layout.addWidget(self.env_canvas_b)
        self.tabs.addTab(env_widget, "环境曲线")

        # --- GDP 前三 ---
        gdp_widget = QWidget()
        gdp_layout = QHBoxLayout(gdp_widget)
        self.gdp_canvas_a = MplCanvas(self, width=5, height=3)
        self.gdp_canvas_b = MplCanvas(self, width=5, height=3)
        self.gdp_canvas_b.hide()
        gdp_layout.addWidget(self.gdp_canvas_a)
        gdp_layout.addWidget(self.gdp_canvas_b)
        self.tabs.addTab(gdp_widget, "GDP 前三")

        # --- 国家详情 ---
        table_widget = QWidget()
        table_layout = QHBoxLayout(table_widget)
        self.table_a = QTableWidget()
        self.table_b = QTableWidget()
        self.table_b.hide()
        table_layout.addWidget(self.table_a)
        table_layout.addWidget(self.table_b)
        self.tabs.addTab(table_widget, "国家详情")

        # --- 事件日志 ---
        log_widget = QWidget()
        log_layout = QHBoxLayout(log_widget)
        self.log_a = QTextEdit()
        self.log_a.setReadOnly(True)
        self.log_b = QTextEdit()
        self.log_b.setReadOnly(True)
        self.log_b.hide()
        log_layout.addWidget(self.log_a)
        log_layout.addWidget(self.log_b)
        self.tabs.addTab(log_widget, "事件日志")

        # --- 世界地图（保留静态气泡图 + 交互按钮）---
        map_widget = QWidget()
        map_layout = QVBoxLayout(map_widget)
        self.map_canvas = MplCanvas(self, width=8, height=6)
        map_layout.addWidget(self.map_canvas)
        self.map_legend_label = QLabel("🟢 稳定  🟡 一般  🔴 不稳定  点大小∝GDP")
        map_layout.addWidget(self.map_legend_label)
        self.open_map_btn = QPushButton("🌍 打开交互世界地图（浏览器）")
        self.open_map_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px; border-radius: 5px; font-weight: bold; }")
        self.open_map_btn.clicked.connect(self.open_interactive_map)
        map_layout.addWidget(self.open_map_btn)
        self.tabs.addTab(map_widget, "世界地图")

        # --- 蒙特卡洛预测 ---
        mc_widget = QWidget()
        mc_layout = QVBoxLayout(mc_widget)
        mc_controls = QHBoxLayout()
        mc_controls.addWidget(QLabel("模拟次数:"))
        self.mc_sims_spin = QSpinBox()
        self.mc_sims_spin.setRange(10, 500)
        self.mc_sims_spin.setValue(50)
        mc_controls.addWidget(self.mc_sims_spin)
        mc_controls.addWidget(QLabel("预测年数:"))
        self.mc_years_spin = QSpinBox()
        self.mc_years_spin.setRange(10, 200)
        self.mc_years_spin.setValue(80)
        mc_controls.addWidget(self.mc_years_spin)
        self.mc_start_btn = QPushButton("开始蒙特卡洛预测")
        self.mc_start_btn.clicked.connect(self.start_monte_carlo)
        mc_controls.addWidget(self.mc_start_btn)
        self.mc_stop_btn = QPushButton("停止")
        self.mc_stop_btn.clicked.connect(self.stop_monte_carlo)
        self.mc_stop_btn.setEnabled(False)
        mc_controls.addWidget(self.mc_stop_btn)
        mc_layout.addLayout(mc_controls)

        self.mc_progress = QProgressBar()
        mc_layout.addWidget(self.mc_progress)
        self.mc_result_label = QLabel("")
        mc_layout.addWidget(self.mc_result_label)
        self.mc_export_btn = QPushButton("📥 导出模拟数据 (CSV)")
        self.mc_export_btn.clicked.connect(self.export_monte_carlo_data)
        self.mc_export_btn.setEnabled(False)
        mc_layout.addWidget(self.mc_export_btn)
        self.mc_canvas = MplCanvas(self, width=8, height=5)
        mc_layout.addWidget(self.mc_canvas)
        self.tabs.addTab(mc_widget, "蒙特卡洛预测")

        # --- 集合预测 ---
        ensemble_widget = QWidget()
        ensemble_layout = QVBoxLayout(ensemble_widget)
        en_controls = QHBoxLayout()
        en_controls.addWidget(QLabel("模拟次数:"))
        self.en_sims_spin = QSpinBox()
        self.en_sims_spin.setRange(10, 200)
        self.en_sims_spin.setValue(30)
        en_controls.addWidget(self.en_sims_spin)
        en_controls.addWidget(QLabel("预测年数:"))
        self.en_years_spin = QSpinBox()
        self.en_years_spin.setRange(10, 200)
        self.en_years_spin.setValue(50)
        en_controls.addWidget(self.en_years_spin)
        self.en_start_btn = QPushButton("开始集合预测")
        self.en_start_btn.clicked.connect(self.start_ensemble)
        en_controls.addWidget(self.en_start_btn)
        self.en_stop_btn = QPushButton("停止")
        self.en_stop_btn.clicked.connect(self.stop_ensemble)
        self.en_stop_btn.setEnabled(False)
        en_controls.addWidget(self.en_stop_btn)
        ensemble_layout.addLayout(en_controls)

        self.en_progress = QProgressBar()
        ensemble_layout.addWidget(self.en_progress)
        self.en_canvas = MplCanvas(self, width=8, height=5)
        ensemble_layout.addWidget(self.en_canvas)
        self.tabs.addTab(ensemble_widget, "集合预测")

        # --- 敏感性分析 ---
        sens_widget = QWidget()
        sens_layout = QVBoxLayout(sens_widget)

        self.sens_param_map = {
            "战争概率 (war_prob)": "war_prob",
            "排放强度 (emission_intensity)": "emission_intensity",
            "绿色政策 (global_green_policy)": "global_green_policy",
            "经济增长基础 (mat_base)": "mat_base",
            "青年生育率 (birth_rate_young)": "birth_rate_young",
            "科研预算系数 (research_budget_per_capita)": "research_budget_per_capita",
        }

        sens_controls_top = QHBoxLayout()
        sens_controls_top.addWidget(QLabel("参数:"))
        self.sens_param_combo = QComboBox()
        for display_name, internal_name in self.sens_param_map.items():
            self.sens_param_combo.addItem(display_name, internal_name)
        sens_controls_top.addWidget(self.sens_param_combo)
        sens_layout.addLayout(sens_controls_top)

        sens_controls = QHBoxLayout()
        sens_controls.addWidget(QLabel("最小值:"))
        self.sens_min_spin = QLineEdit("0.0")
        sens_controls.addWidget(self.sens_min_spin)

        sens_controls.addWidget(QLabel("最大值:"))
        self.sens_max_spin = QLineEdit("0.1")
        sens_controls.addWidget(self.sens_max_spin)

        sens_controls.addWidget(QLabel("步数:"))
        self.sens_steps_spin = QSpinBox()
        self.sens_steps_spin.setRange(2, 100)
        self.sens_steps_spin.setValue(10)
        sens_controls.addWidget(self.sens_steps_spin)

        sens_controls.addWidget(QLabel("预测年数:"))
        self.sens_years_spin = QSpinBox()
        self.sens_years_spin.setRange(10, 200)
        self.sens_years_spin.setValue(50)
        sens_controls.addWidget(self.sens_years_spin)

        self.sens_start_btn = QPushButton("开始敏感性分析")
        self.sens_start_btn.clicked.connect(self.start_sensitivity)
        sens_controls.addWidget(self.sens_start_btn)

        self.sens_stop_btn = QPushButton("停止")
        self.sens_stop_btn.clicked.connect(self.stop_sensitivity)
        self.sens_stop_btn.setEnabled(False)
        sens_controls.addWidget(self.sens_stop_btn)
        sens_layout.addLayout(sens_controls)

        self.sens_progress = QProgressBar()
        sens_layout.addWidget(self.sens_progress)

        self.sens_log = QTextEdit()
        self.sens_log.setReadOnly(True)
        self.sens_log.setMaximumHeight(80)
        sens_layout.addWidget(self.sens_log)

        self.sens_canvas = MplCanvas(self, width=8, height=5)
        sens_layout.addWidget(self.sens_canvas)

        self.tornado_btn = QPushButton("🌪️ 生成 Tornado 图")
        self.tornado_btn.clicked.connect(self.generate_tornado)
        sens_layout.addWidget(self.tornado_btn)

        self.tabs.addTab(sens_widget, "敏感性分析")

        # --- AI 新闻 ---
        news_widget = QWidget()
        news_layout = QVBoxLayout(news_widget)
        self.news_text = QTextEdit()
        self.news_text.setReadOnly(True)
        news_layout.addWidget(self.news_text)
        self.news_refresh_btn = QPushButton("🔄 刷新 AI 新闻")
        self.news_refresh_btn.clicked.connect(self.generate_ai_news)
        news_layout.addWidget(self.news_refresh_btn)
        self.tabs.addTab(news_widget, "AI新闻")
        # --- 现实新闻 ---
        real_news_widget = QWidget()
        real_news_layout = QVBoxLayout(real_news_widget)
        self.real_news_text = QTextEdit()
        self.real_news_text.setReadOnly(True)
        real_news_layout.addWidget(self.real_news_text)
        self.real_news_refresh_btn = QPushButton("🔄 刷新现实新闻")
        self.real_news_refresh_btn.clicked.connect(self.fetch_real_news)
        real_news_layout.addWidget(self.real_news_refresh_btn)
        self.tabs.addTab(real_news_widget, "现实新闻")
        # --- 现实冲击（手动输入新闻）---
        shock_widget = QWidget()
        shock_layout = QVBoxLayout(shock_widget)

        shock_layout.addWidget(QLabel("📰 在此粘贴任意国际新闻（可多段）："))
        self.manual_news_edit = QTextEdit()
        self.manual_news_edit.setMaximumHeight(100)
        self.manual_news_edit.setPlaceholderText(
            "例如：\n"
            "- 中美贸易谈判取得突破性进展...\n"
            "- 欧盟宣布2035年全面禁售燃油车...\n"
            "- 全球气温再创新高，极端气候频发...\n"
            "- 美联储意外宣布降息50个基点..."
        )
        shock_layout.addWidget(self.manual_news_edit)

        self.manual_analyze_btn = QPushButton("🧠 AI 分析新闻并生成冲击")
        self.manual_analyze_btn.clicked.connect(self.analyze_manual_news)
        shock_layout.addWidget(self.manual_analyze_btn)

        self.shock_apply_btn = QPushButton("⚡ 应用此冲击到当前模拟")
        self.shock_apply_btn.clicked.connect(self.apply_real_world_shock)
        self.shock_apply_btn.setEnabled(False)
        shock_layout.addWidget(self.shock_apply_btn)

        self.shock_text = QTextEdit()
        self.shock_text.setReadOnly(True)
        shock_layout.addWidget(self.shock_text)

        self.tabs.addTab(shock_widget, "现实冲击")

        main_splitter.addWidget(self.tabs)
        main_splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(central)
        layout.addWidget(main_splitter)

        self.toggle_compare_mode(False)
        self.update_displays()

    def create_slider(self, name, min_val, max_val, default, divisor=1):
        container = QWidget()
        layout = QVBoxLayout(container)
        display_val = default / divisor if divisor != 1 else default
        label = QLabel(f"{name}: {display_val:.2f}" if divisor != 1 else f"{name}: {display_val}")
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        if divisor != 1:
            slider.valueChanged.connect(lambda val, l=label, d=divisor: l.setText(f"{name}: {val / d:.2f}"))
        else:
            slider.valueChanged.connect(lambda val, l=label: l.setText(f"{name}: {val}"))
        layout.addWidget(label)
        layout.addWidget(slider)
        container._slider = slider
        container._label = label
        container._divisor = divisor
        return container

    def get_slider_value(self, container):
        return container._slider.value() / container._divisor if container._divisor != 1 else container._slider.value()

    def toggle_compare_mode(self, state):
        self.compare_mode = state
        visible = state
        for w in [self.label_B, self.war_b, self.proxy_b, self.emerg_b, self.green_b,
                  self.env_canvas_b, self.gdp_canvas_b, self.table_b, self.log_b]:
            w.setVisible(visible)

    def toggle_record_snapshots(self, state):
        if self.simulation_running:
            self.record_checkbox.setChecked(not state)
        else:
            self.snapshots = []

    def load_preset(self, index):
        if index == 0:
            self.reset_world()
            return
        presets = ["1914", "1939", "1991", "2020"]
        filename = f"preset_{presets[index-1]}.json"
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.world_a = World.from_dict(state)
                self.world_b = World()
                self.current_year_label.setText(f"当前年份: {self.world_a.year}")
                self.progress_bar.setValue(0)
                self.log_a.clear()
                self.log_b.clear()
                self.update_displays()
                QMessageBox.information(self, "完成", f"已加载 {presets[index-1]} 场景")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载失败: {e}")
        else:
            QMessageBox.warning(self, "提示", f"预设文件 {filename} 不存在")

    def open_policy_dialog(self):
        dialog = PolicyShockDialog(self)
        if dialog.exec():
            params = dialog.get_params()
            mapping = {
                "war_prob": "war_prob",
                "emission_intensity": "emission_intensity",
                "global_green_policy": "global_green_policy",
                "research_budget": "research_budget_per_capita",
                "trade_barrier": "trade_barrier",
                "mat_base": "mat_base",
                "birth_rate_young": "birth_rate_young",
            }
            for key, val in params.items():
                if key in mapping:
                    self.world_a.params[mapping[key]] = val
            QMessageBox.information(self, "政策冲击", "参数已应用！可点击“开始模拟”。")

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def start_simulation(self):
        if self.simulation_running:
            QMessageBox.warning(self, "提示", "模拟已在运行中")
            return
        self.world_a.params["war_prob"] = self.get_slider_value(self.war_a)
        self.world_a.params["proxy_prob"] = self.get_slider_value(self.proxy_a)
        self.world_a.params["emergence_prob"] = self.get_slider_value(self.emerg_a)
        self.world_a.params["global_green_policy"] = self.get_slider_value(self.green_a)
        wb = None
        if self.compare_mode:
            self.world_b.params["war_prob"] = self.get_slider_value(self.war_b)
            self.world_b.params["proxy_prob"] = self.get_slider_value(self.proxy_b)
            self.world_b.params["emergence_prob"] = self.get_slider_value(self.emerg_b)
            self.world_b.params["global_green_policy"] = self.get_slider_value(self.green_b)
            wb = self.world_b
        years = self.get_slider_value(self.years_container)

        record = self.record_checkbox.isChecked()
        if record:
            self.world_a.snapshots = []

        self.sim_thread = SimulationThread(self.world_a, wb, years, record)
        self.sim_thread.progress.connect(self.progress_bar.setValue)
        self.sim_thread.year_changed.connect(self.on_year_changed)
        self.sim_thread.finished.connect(self.on_simulation_finished)
        if record:
            self.sim_thread.snapshot_taken.connect(self.update_replay_range)
        self.simulation_running = True
        self.replay_slider.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.sim_thread.start()

    def update_replay_range(self, year):
        self.replay_slider.setMaximum(year)
        self.replay_label.setText(f"回放年份: {year}")

    def on_year_changed(self, year):
        self.current_year_label.setText(f"当前年份: {year}")
        if year % 10 == 0 or year == 1900 + self.get_slider_value(self.years_container):
            self.update_displays()

    def on_simulation_finished(self):
        self.simulation_running = False
        self.start_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.update_displays()
        if self.compare_mode:
            self.compare_report_btn.setEnabled(True)
        if self.record_checkbox.isChecked() and hasattr(self.world_a, 'snapshots') and self.world_a.snapshots:
            max_year = self.world_a.year
            self.replay_slider.setMaximum(max_year)
            self.replay_slider.setValue(max_year)
            self.replay_slider.setEnabled(True)
            self.replay_label.setText(f"回放年份: {max_year}")
            self.generate_ai_summary()
            self.generate_ai_news()
            QMessageBox.information(self, "完成", f"模拟结束！已记录 {len(self.world_a.snapshots)} 个快照，可拖动滑块回放。")
        else:
            QMessageBox.information(self, "完成", "模拟结束！")

    def replay_to_year(self, year):
        if not hasattr(self.world_a, 'snapshots') or not self.world_a.snapshots:
            return
        target_snapshot = None
        for snap in self.world_a.snapshots:
            if snap['year'] == year:
                target_snapshot = snap
                break
        if target_snapshot is None:
            for snap in reversed(self.world_a.snapshots):
                if snap['year'] <= year:
                    target_snapshot = snap
                    break
        if target_snapshot:
            self.world_a = World.from_dict(target_snapshot)
            self.current_year_label.setText(f"回放年份: {self.world_a.year}")
            self.replay_label.setText(f"回放年份: {self.world_a.year}")
            self.update_displays()

    def reset_world(self):
        self.world_a = World()
        self.world_b = World()
        self.current_year_label.setText("当前年份: 1900")
        self.progress_bar.setValue(0)
        self.replay_slider.setValue(1900)
        self.replay_slider.setMaximum(1900)
        self.replay_slider.setEnabled(False)
        self.log_a.clear()
        self.log_b.clear()
        self.update_displays()

    def export_report(self):
        if self.compare_mode:
            report_a = f"report_scenario_A_{self.world_a.year}.pdf"
            report_b = f"report_scenario_B_{self.world_b.year}.pdf"
            generate_pdf_report(self.world_a, report_a)
            generate_pdf_report(self.world_b, report_b)
            os.startfile(report_a)
            os.startfile(report_b)
        else:
            report_file = f"report_{self.world_a.year}.pdf"
            generate_pdf_report(self.world_a, report_file)
            os.startfile(report_file)

    def save_current_world(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存存档", "world_save.json", "JSON Files (*.json)")
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.world_a.to_dict(), f, indent=2)
            QMessageBox.information(self, "保存成功", f"存档已保存至 {filename}")

    def load_archive(self):
        filename, _ = QFileDialog.getOpenFileName(self, "加载存档", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.world_a = World.from_dict(state)
                self.world_b = World()
                self.current_year_label.setText(f"当前年份: {self.world_a.year}")
                self.progress_bar.setValue(0)
                self.log_a.clear()
                self.log_b.clear()
                self.update_displays()
                QMessageBox.information(self, "加载成功", f"已加载存档: {self.world_a.year}年")
            except Exception as e:
                QMessageBox.warning(self, "加载失败", str(e))

    def open_interactive_map(self):
        """在默认浏览器中打开 folium 交互式世界地图"""
        try:
            import folium
            import tempfile
            import webbrowser
            m = folium.Map(location=[20, 0], zoom_start=2, tiles='OpenStreetMap',
                           width='100%', height='100%', control_scale=True)

            for c in self.world_a.countries:
                if c.alive and c.name in COUNTRY_COORDS:
                    lat, lon = COUNTRY_COORDS[c.name]
                    if c.stability < 0.4:
                        color = 'red'
                    elif c.stability < 0.7:
                        color = 'orange'
                    else:
                        color = 'green'
                    radius = max(2, np.log1p(c.gdp) * 2)
                    tooltip = f"{c.name}<br>GDP: {c.gdp:.0f}B<br>稳定度: {c.stability:.2f}"
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=radius,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.6,
                        tooltip=tooltip
                    ).add_to(m)

            with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
                f.write(m.get_root().render())
                webbrowser.open(f'file:///{f.name}')
            QMessageBox.information(self, "地图已打开", "交互式世界地图已在浏览器中打开。\n可缩放、拖动，鼠标悬停查看国家信息。")
        except Exception as e:
            QMessageBox.warning(self, "地图错误", f"无法生成地图：{e}")

    def generate_compare_report(self):
        if not self.compare_mode:
            return
        a = self.world_a
        b = self.world_b

        a_top = sorted([c for c in a.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
        b_top = sorted([c for c in b.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]

        ai_summary = ""
        api_key = SettingsDialog.get_api_key()
        if api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                prompt = f"""根据以下两个场景的对比数据，用中文写一段100字左右的专业分析摘要。
场景A（参数较温和）：
环境={a.global_environment:.1f}, GDP前三={[c.name for c in a_top]}, 人口={sum(c.population for c in a.countries if c.alive):.0f}M
场景B（参数较激进）：
环境={b.global_environment:.1f}, GDP前三={[c.name for c in b_top]}, 人口={sum(c.population for c in b.countries if c.alive):.0f}M
请指出两者差异的主要原因及对未来的启示。"""
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200, temperature=0.7
                )
                ai_summary = response.choices[0].message.content.strip()
            except Exception as e:
                ai_summary = f"AI分析失败：{e}"

        import tempfile, datetime
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.platypus import Image as RImage
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_CENTER

        font_path = r'C:\Windows\Fonts\msyh.ttc'
        if not os.path.exists(font_path):
            font_path = r'C:\Windows\Fonts\msyhl.ttc'
        if not os.path.exists(font_path):
            font_path = r'C:\Windows\Fonts\simhei.ttf'
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
        else:
            pdfmetrics.registerFont(TTFont('ChineseFont', 'Helvetica'))

        filename = f"compare_report_{a.year}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=20 * mm,
                                bottomMargin=20 * mm)
        story = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CTitle', parent=styles['Title'], fontName='ChineseFont', fontSize=20,
                                     alignment=TA_CENTER)
        heading_style = ParagraphStyle('CHeading', parent=styles['Heading2'], fontName='ChineseFont')
        body_style = ParagraphStyle('CBody', parent=styles['Normal'], fontName='ChineseFont', fontSize=10)

        story.append(Spacer(1, 50 * mm))
        story.append(Paragraph("场景对比报告", title_style))
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"年份: {a.year}", heading_style))
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph(f"生成日期: {datetime.date.today()}", body_style))
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph("由地球模拟器 Pro++ 自动生成", body_style))
        from reportlab.platypus import PageBreak
        story.append(PageBreak())

        story.append(Paragraph("一、关键指标对比", heading_style))
        story.append(Spacer(1, 5 * mm))
        table_data = [
            ["指标", "场景 A", "场景 B", "差异"],
            ["环境健康度", f"{a.global_environment:.1f}", f"{b.global_environment:.1f}",
             f"{a.global_environment - b.global_environment:.1f}"],
            ["GDP 第一", a_top[0].name if a_top else "-", b_top[0].name if b_top else "-", ""],
            ["GDP 第二", a_top[1].name if len(a_top) > 1 else "-", b_top[1].name if len(b_top) > 1 else "-", ""],
            ["GDP 第三", a_top[2].name if len(a_top) > 2 else "-", b_top[2].name if len(b_top) > 2 else "-", ""],
            ["总人口 (M)", f"{sum(c.population for c in a.countries if c.alive):.0f}",
             f"{sum(c.population for c in b.countries if c.alive):.0f}",
             f"{sum(c.population for c in a.countries if c.alive) - sum(c.population for c in b.countries if c.alive):.0f}"],
            ["清洁能源占比", f"{a.knowledge.green_ratio() * 100:.0f}%", f"{b.knowledge.green_ratio() * 100:.0f}%",
             f"{(a.knowledge.green_ratio() - b.knowledge.green_ratio()) * 100:.0f}%"],
        ]
        tbl = Table(table_data, colWidths=[1.8 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b2b2b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 10 * mm))

        if ai_summary:
            story.append(Paragraph("二、AI 分析摘要", heading_style))
            story.append(Spacer(1, 5 * mm))
            story.append(Paragraph(ai_summary, body_style))

        doc.build(story)
        os.startfile(filename)

    def update_displays(self):
        self.update_env_plot()
        self.update_gdp_plot()
        self.update_country_table()
        self.update_event_log()
        self.update_map()

    def update_env_plot(self):
        self.env_canvas_a.clear_axes()
        years = list(range(1900, self.world_a.year + 1))
        env = self.world_a.env_history[:len(years)]
        self.env_canvas_a.axes.plot(years, env, color='green')
        self.env_canvas_a.axes.set_ylim(0, 100)
        self.env_canvas_a.axes.set_title("场景A - 环境健康度")
        self.env_canvas_a.axes.grid(True, alpha=0.3)
        self.env_canvas_a.draw()
        if self.compare_mode:
            self.env_canvas_b.clear_axes()
            years_b = list(range(1900, self.world_b.year + 1))
            env_b = self.world_b.env_history[:len(years_b)]
            self.env_canvas_b.axes.plot(years_b, env_b, color='orange')
            self.env_canvas_b.axes.set_ylim(0, 100)
            self.env_canvas_b.axes.set_title("场景B - 环境健康度")
            self.env_canvas_b.axes.grid(True, alpha=0.3)
            self.env_canvas_b.draw()

    def update_gdp_plot(self):
        self.gdp_canvas_a.clear_axes()
        top3 = sorted([c for c in self.world_a.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
        self.gdp_canvas_a.axes.bar([c.name for c in top3], [c.gdp for c in top3], color=['#2196F3', '#FF9800', '#4CAF50'])
        self.gdp_canvas_a.axes.set_title("场景A - GDP前三")
        self.gdp_canvas_a.draw()
        if self.compare_mode:
            self.gdp_canvas_b.clear_axes()
            top3_b = sorted([c for c in self.world_b.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
            self.gdp_canvas_b.axes.bar([c.name for c in top3_b], [c.gdp for c in top3_b], color=['#9C27B0', '#FF5722', '#CDDC39'])
            self.gdp_canvas_b.axes.set_title("场景B - GDP前三")
            self.gdp_canvas_b.draw()

    def update_country_table(self):
        self._fill_table(self.table_a, self.world_a)
        if self.compare_mode:
            self._fill_table(self.table_b, self.world_b)

    def _fill_table(self, table, world):
        countries = sorted(world.countries, key=lambda x: x.gdp, reverse=True)[:10]
        table.setRowCount(len(countries))
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["国家", "人口(M)", "GDP(B)", "物质GDP", "服务GDP", "稳定度", "政体"])
        for i, c in enumerate(countries):
            table.setItem(i, 0, QTableWidgetItem(c.name))
            table.setItem(i, 1, QTableWidgetItem(f"{c.population:.0f}"))
            table.setItem(i, 2, QTableWidgetItem(f"{c.gdp:.0f}"))
            table.setItem(i, 3, QTableWidgetItem(f"{c.material_gdp:.0f}"))
            table.setItem(i, 4, QTableWidgetItem(f"{c.service_gdp:.0f}"))
            table.setItem(i, 5, QTableWidgetItem(f"{c.stability:.2f}"))
            table.setItem(i, 6, QTableWidgetItem(c.government))
        table.resizeColumnsToContents()

    def update_event_log(self):
        self.log_a.clear()
        for event in self.world_a.events_log[-30:]:
            self.log_a.append(event)
        if self.compare_mode:
            self.log_b.clear()
            for event in self.world_b.events_log[-30:]:
                self.log_b.append(event)

    def update_map(self):
        # 简化的大陆轮廓（经度, 纬度 坐标点列表）
        continents = {
            "africa": [
                (-17, 15), (-17, 28), (-5, 36), (10, 37), (32, 30),
                (51, 12), (43, 0), (51, -17), (35, -35), (18, -35),
                (8, -5), (-17, 15)
            ],
            "europe": [
                (-10, 36), (-10, 44), (0, 44), (5, 43), (5, 48),
                (10, 55), (20, 55), (30, 45), (40, 40), (30, 35),
                (20, 35), (10, 36), (-10, 36)
            ],
            "asia": [
                (40, 40), (50, 42), (60, 55), (70, 55), (100, 70),
                (140, 60), (160, 50), (170, 60), (180, 65), (180, 40),
                (140, 30), (120, 25), (100, 20), (80, 15), (60, 20),
                (50, 30), (40, 40)
            ],
            "north_america": [
                (-170, 65), (-140, 70), (-120, 70), (-100, 65), (-80, 60),
                (-60, 50), (-65, 40), (-80, 30), (-90, 20), (-105, 20),
                (-120, 30), (-140, 50), (-160, 60), (-170, 65)
            ],
            "south_america": [
                (-80, 10), (-70, 10), (-60, 5), (-50, 0), (-40, -5),
                (-35, -15), (-40, -25), (-50, -35), (-60, -40), (-70, -35),
                (-75, -20), (-80, -5), (-80, 10)
            ],
            "australia": [
                (115, -20), (130, -15), (145, -15), (153, -25),
                (150, -35), (140, -38), (130, -35), (115, -32),
                (113, -25), (115, -20)
            ],
            "antarctica": [
                (-180, -70), (-150, -75), (-120, -75), (-90, -75),
                (-60, -75), (-30, -72), (0, -70), (30, -72),
                (60, -70), (90, -72), (120, -70), (150, -72),
                (180, -70), (180, -90), (-180, -90), (-180, -70)
            ]
        }

        self.map_canvas.figure.clear()
        ax = self.map_canvas.figure.add_subplot(111)
        self.map_canvas.axes = ax

        # 海洋底色
        ax.set_facecolor('#a6cee3')

        # 绘制大陆
        for name, points in continents.items():
            if name == "antarctica":
                color = '#f7f7f7'  # 白色冰盖
            else:
                color = '#b2df8a'  # 绿色陆地
            poly = plt.Polygon(points, closed=True, facecolor=color, edgecolor='#4d4d4d', linewidth=0.5)
            ax.add_patch(poly)

        # 经纬度网格
        ax.grid(True, linestyle=':', alpha=0.4)

        # 地图范围
        ax.set_xlim(-180, 180)
        ax.set_ylim(-70, 85)
        ax.set_aspect('equal')

        # 国家气泡
        lons, lats, sizes, colors, labels = [], [], [], [], []
        for c in self.world_a.countries:
            if c.alive and c.name in COUNTRY_COORDS:
                lat, lon = COUNTRY_COORDS[c.name]
                lats.append(lat)
                lons.append(lon)
                sizes.append(max(20, np.log1p(c.gdp) * 25))
                if c.stability < 0.4:
                    colors.append('red')
                elif c.stability < 0.7:
                    colors.append('yellow')
                else:
                    colors.append('green')
                labels.append(c.name)

        if lons:
            ax.scatter(lons, lats, s=sizes, c=colors, alpha=0.8, edgecolors='white', linewidths=1)
            for i, name in enumerate(labels):
                ax.annotate(name, (lons[i], lats[i]), fontsize=8, ha='center', va='bottom',
                           fontweight='bold', color='black')
            ax.set_title("世界局势（点大小∝GDP，颜色=稳定度）", fontsize=12)
        else:
            ax.set_title("暂无数据")

        self.map_canvas.draw()

    def start_monte_carlo(self):
        sims = self.mc_sims_spin.value()
        years = self.mc_years_spin.value()
        import copy
        world_copy = copy.deepcopy(self.world_a)
        self.mc_thread = MonteCarloThread(world_copy, sims, years)
        self.mc_thread.progress.connect(self.mc_progress.setValue)
        self.mc_thread.finished.connect(self.show_monte_carlo_result)
        self.mc_start_btn.setEnabled(False)
        self.mc_stop_btn.setEnabled(True)
        self.mc_thread.start()

    def stop_monte_carlo(self):
        if self.mc_thread and self.mc_thread.isRunning():
            self.mc_thread.stop()
            self.mc_start_btn.setEnabled(True)
            self.mc_stop_btn.setEnabled(False)

    def start_ensemble(self):
        sims = self.en_sims_spin.value()
        years = self.en_years_spin.value()
        import copy
        world_copy = copy.deepcopy(self.world_a)
        self.en_thread = EnsembleThread(world_copy, sims, years)
        self.en_thread.progress.connect(self.en_progress.setValue)
        self.en_thread.finished.connect(self.show_ensemble_result)
        self.en_start_btn.setEnabled(False)
        self.en_stop_btn.setEnabled(True)
        self.en_thread.start()

    def stop_ensemble(self):
        if hasattr(self, 'en_thread') and self.en_thread.isRunning():
            self.en_thread.stop()
            self.en_start_btn.setEnabled(True)
            self.en_stop_btn.setEnabled(False)

    def show_ensemble_result(self, result):
        self.en_start_btn.setEnabled(True)
        self.en_stop_btn.setEnabled(False)
        if result is None:
            return
        self.en_canvas.clear_axes()
        ax = self.en_canvas.axes
        years = result["years"]
        median = result["median"]
        lower10 = result["lower10"]
        upper90 = result["upper90"]
        lower25 = result["lower25"]
        upper75 = result["upper75"]
        ax.fill_between(years, lower10, upper90, color='lightgreen', alpha=0.3, label='90%区间')
        ax.fill_between(years, lower25, upper75, color='green', alpha=0.3, label='50%区间')
        ax.plot(years, median, 'g-', linewidth=2, label='中位数')
        ax.set_ylabel("环境健康度")
        ax.set_xlabel("年份")
        ax.set_title("集合预测（环境路径）")
        ax.legend()
        self.en_canvas.draw()

    def start_sensitivity(self):
        param = self.sens_param_combo.currentData()
        try:
            pmin = float(self.sens_min_spin.text())
            pmax = float(self.sens_max_spin.text())
        except ValueError:
            QMessageBox.warning(self, "错误", "最小值和最大值必须是数字")
            return
        steps = self.sens_steps_spin.value()
        years = self.sens_years_spin.value()

        import copy
        world_copy = copy.deepcopy(self.world_a)
        self.sens_thread = SensitivityThread(world_copy, param, pmin, pmax, steps, years)
        self.sens_thread.progress.connect(self.sens_progress.setValue)
        self.sens_thread.log.connect(self.sens_log.append)
        self.sens_thread.finished.connect(self.show_sensitivity_result)
        self.sens_start_btn.setEnabled(False)
        self.sens_stop_btn.setEnabled(True)
        self.sens_log.clear()
        self.sens_thread.start()

    def stop_sensitivity(self):
        if hasattr(self, 'sens_thread') and self.sens_thread.isRunning():
            self.sens_thread.stop()
            self.sens_start_btn.setEnabled(True)
            self.sens_stop_btn.setEnabled(False)

    def show_sensitivity_result(self, result):
        self.sens_start_btn.setEnabled(True)
        self.sens_stop_btn.setEnabled(False)
        if result is None:
            return
        values = result["values"]
        results = result["results"]
        self.sens_canvas.clear_axes()
        ax = self.sens_canvas.axes
        ax.plot(values, results, 'o-', color='purple')
        ax.set_xlabel(self.sens_param_combo.currentText())
        ax.set_ylabel("最终环境健康度")
        ax.set_title("敏感性分析")
        ax.grid(True, alpha=0.3)
        self.sens_canvas.draw()

    def generate_tornado(self):
        """对关键参数生成龙卷风图"""
        import copy
        params = [
            ("战争概率", "war_prob", 0.0166, 0.005, 0.05),
            ("排放强度", "emission_intensity", 0.000012, 0.000005, 0.00005),
            ("绿色政策", "global_green_policy", 0.1, 0.02, 0.5),
            ("科研预算", "research_budget_per_capita", 0.8, 0.2, 2.0),
            ("贸易壁垒", "trade_barrier", 0.0, 0.0, 0.5),
            ("经济增长基础", "mat_base", 0.024, 0.015, 0.04),
        ]

        years = 50
        results = []
        for name, param, default, low, high in params:
            low_env = self._run_single_sim(param, low, years)
            high_env = self._run_single_sim(param, high, years)
            base_env = self._run_single_sim(param, default, years)
            results.append((name, low_env, base_env, high_env))

        self.tornado_canvas = MplCanvas(self, width=8, height=5)
        ax = self.tornado_canvas.axes
        names = [r[0] for r in results]
        low_vals = [r[1] - r[2] for r in results]
        high_vals = [r[3] - r[2] for r in results]
        y_pos = range(len(names))
        ax.barh(y_pos, low_vals, color='blue', alpha=0.6, label='低值影响')
        ax.barh(y_pos, high_vals, color='red', alpha=0.6, label='高值影响')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.axvline(0, color='black', linestyle='--')
        ax.set_xlabel("环境健康度变化")
        ax.set_title("Tornado 图 (参数重要性)")
        ax.legend()
        self.tornado_canvas.figure.tight_layout()

        self.tabs.addTab(self.tornado_canvas, "Tornado图")
        self.tabs.setCurrentWidget(self.tornado_canvas)

    def _run_single_sim(self, param, value, years):
        import copy
        w = copy.deepcopy(self.world_a)
        w.params[param] = value
        for _ in range(years):
            w.run_year()
        return w.global_environment

    def run_experiment_matrix(self):
        dialog = MatrixDialog(self)
        if not dialog.exec():
            return
        selected = dialog.get_selected_params()
        if not selected:
            return
        years = dialog.get_years()

        keys = list(selected.keys())
        values = list(selected.values())
        combos = list(itertools.product(*values))

        self.matrix_progress = QProgressBar()
        self.matrix_status = QLabel()
        self.matrix_table = QTableWidget()
        self.matrix_table.setColumnCount(len(keys) + 3)
        headers = keys + ["环境健康度", "总GDP(B)", "总人口(M)"]
        self.matrix_table.setHorizontalHeaderLabels(headers)
        self.matrix_table.setRowCount(len(combos))

        matrix_widget = QWidget()
        matrix_layout = QVBoxLayout(matrix_widget)
        matrix_layout.addWidget(self.matrix_progress)
        matrix_layout.addWidget(self.matrix_status)
        matrix_layout.addWidget(self.matrix_table)
        self.tabs.addTab(matrix_widget, "实验矩阵")
        self.tabs.setCurrentWidget(matrix_widget)

        import copy
        for i, combo in enumerate(combos):
            w = copy.deepcopy(self.world_a)
            for j, key in enumerate(keys):
                w.params[key] = combo[j]
            for y in range(years):
                w.run_year()
            env = w.global_environment
            gdp = sum(c.gdp for c in w.countries if c.alive)
            pop = sum(c.population for c in w.countries if c.alive)
            for j, val in enumerate(combo):
                self.matrix_table.setItem(i, j, QTableWidgetItem(str(val)))
            self.matrix_table.setItem(i, len(keys), QTableWidgetItem(f"{env:.1f}"))
            self.matrix_table.setItem(i, len(keys)+1, QTableWidgetItem(f"{gdp:.0f}"))
            self.matrix_table.setItem(i, len(keys)+2, QTableWidgetItem(f"{pop:.0f}"))
            self.matrix_progress.setValue((i+1)*100 // len(combos))
            self.matrix_status.setText(f"运行中: {i+1}/{len(combos)}")

    def show_monte_carlo_result(self, result):
        self.mc_start_btn.setEnabled(True)
        self.mc_stop_btn.setEnabled(False)
        if result is None:
            QMessageBox.warning(self, "取消", "蒙特卡洛模拟已取消")
            return

        mean, p10, p90, hist_data = result["mean"], result["p10"], result["p90"], result["hist_data"]
        var_95 = np.percentile(hist_data, 5)
        cvar_95 = np.mean([v for v in hist_data if v <= var_95]) if any(v <= var_95 for v in hist_data) else var_95

        # 新增统计量
        from scipy.stats import skew, kurtosis, shapiro
        std_dev = np.std(hist_data)
        skewness = skew(hist_data)
        kurt = kurtosis(hist_data)  # 超额峰度
        # 正态性检验 (Shapiro-Wilk)
        try:
            stat, p_value = shapiro(hist_data)
            normality = "近似正态" if p_value > 0.05 else f"非正态 (p={p_value:.3f})"
        except:
            normality = "检验失败"

        self.mc_result_label.setText(
            f"均值: {mean:.1f}  90%区间: [{p10:.1f}, {p90:.1f}]  VaR(95%): {var_95:.1f}  CVaR(95%): {cvar_95:.1f}\n"
            f"标准差: {std_dev:.1f}  偏度: {skewness:.2f}  超额峰度: {kurt:.2f}  正态性: {normality}"
        )

        # 绘图保持不变
        self.mc_canvas.clear_axes()
        ax = self.mc_canvas.axes
        n, bins, patches = ax.hist(hist_data, bins=20, color='skyblue', edgecolor='black', density=True)
        kde = gaussian_kde(hist_data)
        x_range = np.linspace(min(hist_data), max(hist_data), 200)
        ax.plot(x_range, kde(x_range), 'b-', linewidth=2, label='概率密度')
        ax.axvline(mean, color='red', linestyle='dashed', label=f'均值:{mean:.1f}')
        ax.axvline(p10, color='gray', linestyle='dotted', label=f'10%:{p10:.1f}')
        ax.axvline(p90, color='gray', linestyle='dotted', label=f'90%:{p90:.1f}')
        ax.axvline(var_95, color='darkred', linestyle='dashed', label=f'VaR95:{var_95:.1f}')
        ax.fill_between(x_range, kde(x_range), where=x_range <= var_95, color='red', alpha=0.3)
        ax.set_title("环境健康度分布（含尾部风险）")
        ax.legend()
        self.mc_canvas.draw()

        # 存储数据供导出使用
        self.mc_raw_data = hist_data
        self.mc_export_btn.setEnabled(True)

    def export_monte_carlo_data(self):
        if not hasattr(self, 'mc_raw_data') or self.mc_raw_data is None:
            QMessageBox.warning(self, "提示", "没有可导出的数据")
            return
        import csv
        filename = f"monte_carlo_data_{datetime.date.today()}.csv"
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["环境健康度"])
            for val in self.mc_raw_data:
                writer.writerow([val])
        QMessageBox.information(self, "导出成功", f"数据已保存至 {filename}")
        os.startfile(filename)

    def generate_ai_summary(self):
        w = self.world_a
        top3 = sorted([c for c in w.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
        env_trend = "上升" if len(w.env_history) >= 2 and w.env_history[-1] > w.env_history[0] else "下降"
        events_summary = "; ".join([e.split("] ")[-1] for e in w.events_log[-5:]]) if w.events_log else "无重大事件"
        prompt = f"""用中文写一段150字的地球模拟分析摘要。
当前年份：{w.year}
环境健康度：{w.global_environment:.1f}，总体趋势：{env_trend}
GDP前三：{', '.join([c.name for c in top3])}
近期事件：{events_summary}
请用专业口吻，指出当前世界的主要风险和机遇。"""
        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if api_key:
                client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200, temperature=0.7
                )
                summary = response.choices[0].message.content.strip()
                self.ai_summary_label.setText(f"🤖 AI分析摘要：{summary}")
        except Exception as e:
            self.ai_summary_label.setText(f"AI摘要生成失败：{e}")

    def generate_ai_news(self):
        """利用 DeepSeek 生成当前世界的虚构新闻"""
        w = self.world_a
        top3 = sorted([c for c in w.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:5]
        events = w.events_log[-10:]  # 最近10个事件
        events_text = "\n".join(events) if events else "无特殊事件"

        prompt = f"""你是一个新闻编辑，请根据以下当前世界状态，生成5条简洁的新闻标题（每条不超过30字）。
当前年份：{w.year}
环境健康度：{w.global_environment:.1f} / 100
清洁能源占比：{w.knowledge.green_ratio() * 100:.1f}%
GDP前五国家：{', '.join([c.name for c in top3])}
近期事件：
{events_text}

请直接输出新闻标题，每行一条，不要编号，不要解释。"""

        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if not api_key:
                self.news_text.setText("⚠️ 请先在左侧“API设置”中输入DeepSeek API Key")
                return
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.8
            )
            news = response.choices[0].message.content.strip()
            self.news_text.setText(f"### {w.year}年 全球新闻快讯\n\n{news}")
        except Exception as e:
            self.news_text.setText(f"AI新闻生成失败：{e}")

    def fetch_real_news(self):
        import requests
        text = ""

        # 1. 全球 GDP（最新年份）
        try:
            url_gdp = "https://api.worldbank.org/v2/country/CN;US;JP;DE;GB/indicator/NY.GDP.MKTP.CD?format=json&per_page=5&mrnev=1"
            resp = requests.get(url_gdp, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1 and data[1]:
                    text += "### 🌍 全球经济数据（最新）\n\n"
                    for rec in data[1]:
                        country = rec.get("country", {}).get("value", "未知")
                        year = rec.get("date", "????")
                        value = rec.get("value")
                        if value:
                            text += f"- {country} ({year}): GDP {value:,.0f} 美元\n"
                else:
                    text += "⚠️ 经济数据暂时为空\n"
            else:
                text += "⚠️ 世界银行服务器返回错误\n"
        except Exception as e:
            text += f"⚠️ 经济数据获取失败：{e}\n"

        # 2. CO₂ 排放（最新年份，世界银行）
        try:
            url_co2 = "https://api.worldbank.org/v2/country/CN;US;JP;DE;GB/indicator/EN.ATM.CO2E.KT?format=json&per_page=5&mrnev=1"
            resp_co2 = requests.get(url_co2, timeout=10)
            if resp_co2.status_code == 200:
                co2_data = resp_co2.json()
                if len(co2_data) > 1 and co2_data[1]:
                    text += "\n### 🌫️ 全球碳排放数据（最新）\n\n"
                    for rec in co2_data[1]:
                        country = rec.get("country", {}).get("value", "未知")
                        year = rec.get("date", "????")
                        value = rec.get("value")
                        if value:
                            text += f"- {country} ({year}): CO₂排放 {value:,.0f} 千吨\n"
                else:
                    text += "\n### 🌫️ 全球碳排放数据\n⚠️ 数据暂时为空（世界银行可能尚未更新）\n"
            else:
                text += "\n### 🌫️ 全球碳排放数据\n⚠️ 世界银行服务器返回错误\n"
        except Exception as e:
            text += f"\n### 🌫️ 全球碳排放数据\n⚠️ 获取失败：{e}\n"

        self.real_news_text.setText(text)
        
    def fetch_global_news(self):
        """从RSS源获取国际新闻标题（用于冲击分析）"""
        import feedparser

        sources = [
            ("BBC中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
            ("环球网国际", "http://world.huanqiu.com/rss/world.xml"),
        ]

        all_titles = []
        for name, url in sources:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "")
                    all_titles.append(f"[{name}] {title}")
                if all_titles:
                    break
            except:
                continue
        return all_titles

    def analyze_real_world_shock(self):
        """获取现实新闻，让 DeepSeek 分析并生成参数修改建议"""
        self.shock_text.setText("🔄 正在抓取全球新闻...")
        titles = self.fetch_global_news()
        if not titles:
            self.shock_text.setText("❌ 未能获取到新闻，请检查网络")
            return

        news_text = "\n".join(titles[:15])

        prompt = f"""你是一个全球局势分析师。根据以下最新的国际新闻，判断哪些事件可能影响全球政治、经济、环境或科技，并提取出对以下模拟参数的建议调整值（用JSON格式返回，所有值都是浮点数，不要包含其他文字）：
参数列表：
- war_prob (战争概率，0.0-0.2，默认0.0166)
- emission_intensity (排放强度，0.0-0.0001，默认0.000012)
- global_green_policy (绿色政策力度，0.0-1.0，默认0.1)
- research_budget (科研预算系数，0.1-30，默认0.8)
- trade_barrier (贸易壁垒，0.0-1.0，默认0.0)
- mat_base (经济增长基础，0.01-0.04，默认0.024)
- birth_rate_young (青年生育率，0.01-0.1，默认0.062)

如果某事件不涉及某参数，则保持默认值不变。
返回格式示例：{{"war_prob": 0.02, "emission_intensity": 0.000015, ...}}

新闻列表：
{news_text}"""

        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if not api_key:
                self.shock_text.setText("⚠️ 请先设置 DeepSeek API Key")
                return
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rstrip("```")
            self.shock_params = json.loads(result_text)
            display = "### 📊 现实世界冲击分析\n\n"
            display += f"**基于以下新闻分析得出**：\n{news_text[:500]}...\n\n"
            display += "**建议的参数调整**：\n"
            for key, val in self.shock_params.items():
                display += f"- {key}: {val}\n"
            self.shock_text.setText(display)
            self.shock_apply_btn.setEnabled(True)
        except Exception as e:
            self.shock_text.setText(f"❌ AI分析失败：{e}")

    def analyze_manual_news(self):
        """分析用户手动输入的新闻文本，生成冲击参数"""
        news_text = self.manual_news_edit.toPlainText().strip()
        if not news_text:
            QMessageBox.warning(self, "提示", "请先粘贴新闻文本")
            return

        self.shock_text.setText("🔄 正在分析...")

        prompt = f"""你是一个全球局势分析师。根据以下新闻文本，判断哪些事件可能影响全球政治、经济、环境或科技，并提取出对以下模拟参数的建议调整值（用JSON格式返回，所有值都是浮点数，不要包含其他文字）：
参数列表：
- war_prob (战争概率，0.0-0.2，默认0.0166)
- emission_intensity (排放强度，0.0-0.0001，默认0.000012)
- global_green_policy (绿色政策力度，0.0-1.0，默认0.1)
- research_budget (科研预算系数，0.1-30，默认0.8)
- trade_barrier (贸易壁垒，0.0-1.0，默认0.0)
- mat_base (经济增长基础，0.01-0.04，默认0.024)
- birth_rate_young (青年生育率，0.01-0.1，默认0.062)

如果某事件不涉及某参数，则保持默认值不变。
返回格式示例：{{"war_prob": 0.02, "emission_intensity": 0.000015, ...}}

新闻文本：
{news_text}"""

        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if not api_key:
                self.shock_text.setText("⚠️ 请先设置 DeepSeek API Key")
                return
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rstrip("```")
            self.shock_params = json.loads(result_text)
            display = "### 📊 手动新闻冲击分析\n\n"
            display += f"**分析文本**：\n{news_text[:300]}...\n\n"
            display += "**建议的参数调整**：\n"
            for key, val in self.shock_params.items():
                display += f"- {key}: {val}\n"
            self.shock_text.setText(display)
            self.shock_apply_btn.setEnabled(True)
        except Exception as e:
            self.shock_text.setText(f"❌ AI分析失败：{e}")

    def apply_real_world_shock(self):
     """将 AI 生成的参数应用到当前世界"""
     if not hasattr(self, 'shock_params') or not self.shock_params:
         return
     mapping = {
         "war_prob": "war_prob",
         "emission_intensity": "emission_intensity",
         "global_green_policy": "global_green_policy",
         "research_budget": "research_budget_per_capita",
         "trade_barrier": "trade_barrier",
         "mat_base": "mat_base",
         "birth_rate_young": "birth_rate_young",
     }
     for key, val in self.shock_params.items():
         if key in mapping:
             self.world_a.params[mapping[key]] = val
     QMessageBox.information(self, "现实冲击", "参数已更新！可点击“开始模拟”查看推演结果。")

    def analyze_manual_news(self):
        """分析用户手动输入的新闻文本，生成冲击参数"""
        news_text = self.manual_news_edit.toPlainText().strip()
        if not news_text:
            QMessageBox.warning(self, "提示", "请先粘贴新闻文本")
            return

        self.shock_text.setText("🔄 正在分析...")

        prompt = f"""你是一个全球局势分析师。根据以下新闻文本，判断哪些事件可能影响全球政治、经济、环境或科技，并提取出对以下模拟参数的建议调整值（用JSON格式返回，所有值都是浮点数，不要包含其他文字）：
参数列表：
- war_prob (战争概率，0.0-0.2，默认0.0166)
- emission_intensity (排放强度，0.0-0.0001，默认0.000012)
- global_green_policy (绿色政策力度，0.0-1.0，默认0.1)
- research_budget (科研预算系数，0.1-30，默认0.8)
- trade_barrier (贸易壁垒，0.0-1.0，默认0.0)
- mat_base (经济增长基础，0.01-0.04，默认0.024)
- birth_rate_young (青年生育率，0.01-0.1，默认0.062)

如果某事件不涉及某参数，则保持默认值不变。
返回格式示例：{{"war_prob": 0.02, "emission_intensity": 0.000015, ...}}

新闻文本：
{news_text}"""

        try:
            from openai import OpenAI
            api_key = SettingsDialog.get_api_key()
            if not api_key:
                self.shock_text.setText("⚠️ 请先设置 DeepSeek API Key")
                return
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rstrip("```")
            self.shock_params = json.loads(result_text)
            display = "### 📊 新闻冲击分析\n\n"
            display += f"**分析文本**：\n{news_text[:300]}...\n\n"
            display += "**建议的参数调整**：\n"
            for key, val in self.shock_params.items():
                display += f"- {key}: {val}\n"
            self.shock_text.setText(display)
            self.shock_apply_btn.setEnabled(True)
        except Exception as e:
            self.shock_text.setText(f"❌ AI分析失败：{e}")

# ---------- PDF 报告生成 ----------
def generate_pdf_report(world, filename="earth_report.pdf"):
    """生成专业 PDF 报告"""
    # 注册中文字体
    font_path = r'C:\Windows\Fonts\msyh.ttc'
    if not os.path.exists(font_path):
        font_path = r'C:\Windows\Fonts\msyhl.ttc'
    if not os.path.exists(font_path):
        font_path = r'C:\Windows\Fonts\simhei.ttf'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
    else:
        pdfmetrics.registerFont(TTFont('ChineseFont', 'Helvetica'))

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    story = []

    # 样式
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ChineseTitle', parent=styles['Title'], fontName='ChineseFont', fontSize=24, alignment=TA_CENTER)
    heading_style = ParagraphStyle('ChineseHeading', parent=styles['Heading2'], fontName='ChineseFont')
    body_style = ParagraphStyle('ChineseBody', parent=styles['Normal'], fontName='ChineseFont', fontSize=10)

    # 封面
    story.append(Spacer(1, 80*mm))
    story.append(Paragraph("地球模拟器 Pro++ 人类世报告", title_style))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(f"年份: {world.year}", heading_style))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(f"环境健康度: {world.global_environment:.1f} / 100", heading_style))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(f"清洁能源占比: {world.knowledge.green_ratio()*100:.0f}%", heading_style))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph(f"生成日期: {datetime.date.today()}", body_style))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("由地球模拟器 Pro++ 自动生成", body_style))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("本报告为AI推演结果，不构成任何现实预测或政策建议", body_style))

    # 分页
    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    # 环境图表
    story.append(Paragraph("一、环境健康度历史", heading_style))
    story.append(Spacer(1, 5*mm))
    # 生成临时图片
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3))
        years = list(range(1900, world.year + 1))
        env = world.env_history[:len(years)]
        ax.plot(years, env, color='green')
        ax.set_ylim(0, 100)
        ax.set_ylabel("环境指数")
        ax.set_title("全球环境健康度")
        ax.grid(True, alpha=0.3)
        fig.savefig(tmp.name, dpi=150, bbox_inches='tight')
        plt.close(fig)
        img = Image(tmp.name, width=6*inch, height=2.5*inch)
        story.append(img)
    story.append(Spacer(1, 5*mm))

    # GDP 图表
    story.append(Paragraph("二、GDP 前三强", heading_style))
    story.append(Spacer(1, 5*mm))
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        fig, ax = plt.subplots(figsize=(6, 3))
        top3 = sorted([c for c in world.countries if c.alive], key=lambda x: x.gdp, reverse=True)[:3]
        names = [c.name for c in top3]
        gdps = [c.gdp for c in top3]
        ax.bar(names, gdps, color=['#2196F3', '#FF9800', '#4CAF50'])
        ax.set_ylabel("GDP (B)")
        ax.set_title("GDP 前三强")
        fig.savefig(tmp.name, dpi=150, bbox_inches='tight')
        plt.close(fig)
        img = Image(tmp.name, width=4*inch, height=2*inch)
        story.append(img)
    story.append(Spacer(1, 5*mm))

    # 国家概况表格
    story.append(Paragraph("三、国家概况（前10）", heading_style))
    story.append(Spacer(1, 5*mm))
    table_data = [["国家", "人口(M)", "GDP(B)", "稳定度", "政体"]]
    for c in sorted(world.countries, key=lambda x: x.gdp, reverse=True)[:10]:
        table_data.append([
            c.name,
            f"{c.population:.0f}",
            f"{c.gdp:.0f}",
            f"{c.stability:.2f}",
            c.government
        ])
    tbl = Table(table_data, colWidths=[1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b2b2b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))

    # 事件日志
    story.append(Paragraph("四、近期重大事件（最近20条）", heading_style))
    story.append(Spacer(1, 5*mm))
    for event in world.events_log[-20:]:
        story.append(Paragraph(f"• {event}", body_style))

    # 构建 PDF
    doc.build(story)
    # 清理临时图片
    for tmp_name in [n for n in os.listdir(tempfile.gettempdir()) if n.startswith('tmp')]:
        try:
            os.remove(os.path.join(tempfile.gettempdir(), tmp_name))
        except:
            pass

# ---------- 启动画面 ----------
def show_splash():
    splash_pix = QPixmap("splash.png")
    if splash_pix.isNull():
        splash_pix = QPixmap(800, 400)
        painter = QPainter(splash_pix)
        gradient = QLinearGradient(0, 0, 0, 400)
        gradient.setColorAt(0, QColor("#1a237e"))
        gradient.setColorAt(1, QColor("#0d47a1"))
        painter.fillRect(0, 0, 800, 400, gradient)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Microsoft YaHei", 28))
        painter.drawText(0, 0, 800, 400, Qt.AlignCenter, "🌍 地球模拟器 Pro++\n加载中...")
        painter.end()
    splash = QSplashScreen(splash_pix)
    splash.showMessage("版本 2.0", Qt.AlignBottom | Qt.AlignRight, Qt.white)
    return splash

if __name__ == "__main__":
    app = QApplication(sys.argv)

    style_path = os.path.join(os.path.dirname(__file__), 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    splash = show_splash()
    splash.show()
    app.processEvents()
    QTimer.singleShot(3000, splash.close)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())