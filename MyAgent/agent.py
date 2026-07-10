# agent.py（最终版：生成带友好提示的脚本 + 自动测试 + 自动打包exe + 自动压缩zip）
import subprocess
import tempfile
import os
import sys
import zipfile
import re
from deepseek_utils import ask_deepseek

def generate_script(requirement: str) -> str:
    prompt = f"""根据以下需求，写一个完整的Python脚本，包含所有必要的import。
必须遵守以下规则：
1. 代码第一行必须是 # -*- coding: utf-8 -*-，以防中文乱码。
2. 脚本启动时立刻打印“程序已启动，正在处理，请稍候...”。
3. 无论执行成功或失败，在脚本末尾加上 input("按回车键退出...") 让窗口停留。
4. 必须兼容当前文件夹下没有对应文件的情况：如果没有找到文件，打印一条友好的提示（例如“未找到任何 .xlsx 文件，请将本程序放在包含Excel的文件夹内。”），然后按回车退出，绝对不要报错崩溃。
5. 如果处理成功，打印“处理完成！结果已保存为 [文件名]。”。
仅输出Python代码，用```python```包裹，不要解释。
需求：{requirement}"""

    reply = ask_deepseek(prompt)
    if "```python" in reply:
        code = reply.split("```python")[1].split("```")[0].strip()
    elif "```" in reply:
        code = reply.split("```")[1].split("```")[0].strip()
    else:
        code = reply.strip()
    return code

def run_script(code: str, timeout=30):
    """在临时文件里执行代码，自动跳过 input 语句，防止测试时卡住"""
    # 把 input("...") 替换成空字符串，保留其他逻辑
    code_for_test = re.sub(r'input\s*\(.*?\)', '""', code)

    fd, temp_path = tempfile.mkstemp(suffix='.py')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(code_for_test)
        result = subprocess.run(
            ["python", temp_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )
        success = result.returncode == 0
        output = (result.stdout or '') + (result.stderr or '')
        return success, output.strip()
    except subprocess.TimeoutExpired:
        return False, "脚本执行超时"
    finally:
        os.unlink(temp_path)

def package_script(script_path: str) -> str:
    """将脚本打包成独立exe，返回exe路径"""
    print("📦 正在打包成 exe ...")
    dist_dir = os.path.join(os.path.dirname(script_path), "outputs")
    os.makedirs(dist_dir, exist_ok=True)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--onefile", "--distpath", dist_dir, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120
        )
        if result.returncode == 0:
            exe_name = os.path.splitext(os.path.basename(script_path))[0] + ".exe"
            exe_path = os.path.join(dist_dir, exe_name)
            print(f"✅ 打包完成：{exe_path}")
            return exe_path
        else:
            print("❌ 打包失败：")
            print(result.stdout + result.stderr)
            return ""
    except Exception as e:
        print(f"❌ 打包异常：{e}")
        return ""

def zip_file(file_path: str) -> str:
    """将文件压缩为同名的 .zip 文件，返回压缩包路径"""
    zip_path = file_path + ".zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, arcname=os.path.basename(file_path))
    print(f"📁 已压缩为：{zip_path}")
    return zip_path

def auto_build_and_package(requirement: str) -> str:
    """
    全自动：生成脚本 → 测试修复 → 打包 exe → 压缩 zip
    返回最终 zip 文件路径，失败返回 None
    """
    print(f"📌 需求：{requirement}")
    code = generate_script(requirement)
    print("⚙️  生成代码...")

    # 测试与修复
    final_code = None
    for i in range(3):
        success, output = run_script(code)
        if success:
            print(f"✅ 第{i+1}次运行成功")
            final_code = code
            break
        else:
            print(f"❌ 第{i+1}次运行失败：{output}")
            if i < 2:
                print("🔧 请求AI修复...")
                code = generate_script(
                    f"修复以下代码错误，仅输出修正后的代码：\n```python\n{code}\n```\n错误信息：{output}"
                )

    if not final_code:
        print("⚠️ 已达最大修复次数，脚本生成失败")
        return None

    # 保存最终脚本（保留原始input语句，不删）
    script_path = "final_script.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(final_code)
    print(f"🎉 可用脚本已保存为 {script_path}")

    # 打包成 exe
    exe_path = package_script(script_path)
    if not exe_path:
        return None

    # 压缩成 zip
    zip_path = zip_file(exe_path)
    return zip_path

if __name__ == "__main__":
    req = input("请输入你的脚本需求：")
    auto_build_and_package(req)