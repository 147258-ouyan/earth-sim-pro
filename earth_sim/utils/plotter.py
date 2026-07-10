from collections import deque
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt

class LivePlotter:
    def __init__(self, world, max_points=200, interactive=True):
        self.world = world
        self.max_points = max_points
        self.interactive = interactive
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(14, 5))
        self.fig.suptitle('地球模拟器 Pro++ 实时监控', fontsize=14)
        self.years = deque(maxlen=max_points)
        self.env_history = deque(maxlen=max_points)
        self.gdp_history = {}
        self.top_names = []

    def update(self):
        year = self.world.year
        env = self.world.global_environment
        self.years.append(year)
        self.env_history.append(env)
        alive = sorted([c for c in self.world.countries if c.alive],
                       key=lambda x: x.gdp, reverse=True)[:3]
        new_top = [c.name for c in alive]
        if new_top != self.top_names:
            for name in new_top:
                if name not in self.gdp_history:
                    self.gdp_history[name] = deque([float('nan')] * len(self.years), maxlen=self.max_points)
            self.top_names = new_top
        for name in self.top_names:
            if name not in self.gdp_history:
                self.gdp_history[name] = deque(maxlen=self.max_points)
            c = self.world.find(name)
            if c: self.gdp_history[name].append(c.gdp)
            else: self.gdp_history[name].append(float('nan'))
        self.ax1.clear(); self.ax2.clear()
        self.ax1.set_title('全球环境健康度')
        self.ax1.plot(list(self.years), list(self.env_history), 'g-', linewidth=2)
        self.ax1.set_ylim(0, 100); self.ax1.set_ylabel('环境指数'); self.ax1.grid(True, alpha=0.3)
        self.ax2.set_title('GDP 前三国家')
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
        yr_list = list(self.years)
        for i, name in enumerate(self.top_names):
            if name in self.gdp_history:
                gdp_list = list(self.gdp_history[name])
                min_len = min(len(yr_list), len(gdp_list))
                if min_len > 0:
                    self.ax2.plot(yr_list[-min_len:], gdp_list[-min_len:],
                                  label=name, color=colors[i % 3], linewidth=2)
        self.ax2.legend(); self.ax2.set_ylabel('GDP (B)'); self.ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        if self.interactive: plt.pause(0.01)