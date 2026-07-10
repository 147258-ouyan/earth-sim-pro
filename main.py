from earth_sim.world import World
from earth_sim.utils.plotter import LivePlotter

if __name__ == "__main__":
    print("🌍 地球模拟器 Pro++ 深度现实版")
    world = World()
    plotter = LivePlotter(world)
    world.status_report()
    while True:
        cmd = input("命令: next/run N/predict/report/quit > ").strip()
        if cmd == "quit":
            break
        elif cmd == "next":
            world.run_year()
            world.status_report()
            plotter.update()
        elif cmd.startswith("run "):
            n = int(cmd.split()[1])
            for _ in range(n):
                world.run_year()
                plotter.update()
            world.status_report()
        elif cmd == "predict":
            futures = world.monte_carlo_prediction(50, 80)
            for y, (mean, p10, p90) in futures.items():
                print(f"{y}: 环境均值 {mean:.1f} (90%区间: {p10:.1f}-{p90:.1f})")
        elif cmd == "report":
            world.generate_report()
        else:
            print("?")