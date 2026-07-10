import sys
import os
import traceback

def main():
    try:
        import streamlit.web.cli as stcli

        # 找到 app.py 的位置（开发环境或打包后）
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后，数据文件解压在 sys._MEIPASS
            app_dir = sys._MEIPASS
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        app_path = os.path.join(app_dir, 'app.py')

        if not os.path.exists(app_path):
            raise FileNotFoundError(f"找不到 app.py，请检查路径：{app_path}")

        # 启动 Streamlit
        sys.argv = [
            "streamlit", "run", app_path,
            "--global.developmentMode=false",
            "--server.headless=true",
            "--server.port=8501"
        ]
        sys.exit(stcli.main())

    except Exception:
        # 将错误信息写入桌面文件，方便查看
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        error_log = os.path.join(desktop, "earth_sim_error.txt")
        with open(error_log, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        # 同时弹窗提示（可选）
        input(f"程序启动失败，错误日志已保存到：{error_log}\n按 Enter 退出...")

if __name__ == "__main__":
    main()