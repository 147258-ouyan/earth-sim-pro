# client_chat.py（修复版：不会死循环追问）
from deepseek_utils import ask_deepseek
from agent import auto_build_and_package
import os

def clarify_requirement(user_input: str) -> str:
    prompt = f"""你是一个专业的接单助手。客户说："{user_input}"
判断标准：
1. 如果客户已经说清楚了：要做什么操作（合并、拆分、提取）、文件类型（Excel/CSV等）、基本条件（列名是否一致、放在哪个文件夹等），就视为需求充分。
2. 需求充分时，必须输出 "OK: 结构化需求描述"，不要继续追问。
3. 只有在关键信息缺失（如不知道操作类型、不知道文件格式）时，才输出 "ASK: 一个具体的追问"。
4. 追问必须用客户能听懂的大白话，且一次只问一个最关键的问题。
5. 禁止反复追问同一个问题，禁止过度细化细节，能写代码就立刻输出OK。"""
    reply = ask_deepseek(prompt, system="你是一个严谨且高效的需求分析师，知道何时该停止提问。")
    return reply.strip() if reply else ""

def generate_usage_guide(zip_path: str) -> str:
    filename = os.path.basename(zip_path).replace(".zip", "")
    guide = f"""
您好，您需要的自动化工具已经制作完成！

📦 文件：{filename}.zip
🖥️ 使用方法：
1. 下载并解压文件，得到一个 exe 程序。
2. 将程序复制到您需要处理的文件夹里（例如存放那些 Excel 的地方）。
3. 双击运行程序，按照屏幕提示操作即可。
4. 完成后程序会提示“按回车键退出”。

⚠️ 注意：程序运行时请勿关闭黑窗口，处理完毕后会自动生成结果文件。

如有任何问题，随时联系我。
    """
    return guide.strip()

def chat_loop():
    print("🤖 AI接单助手已启动，输入客户需求，或 'quit' 退出。")
    requirement = input("客户需求：").strip()

    while requirement.lower() != 'quit':
        reply = clarify_requirement(requirement)
        if not reply:
            print("⚠️ AI未返回有效结果，请重试。")
            requirement = input("客户需求：").strip()
            continue

        if reply.startswith("OK:"):
            structured = reply[3:].strip()
            print(f"✅ 需求已理解：{structured}")
            print("⚙️  正在全自动生成工具...")
            zip_path = auto_build_and_package(structured)
            if zip_path:
                print("\n" + "="*40)
                print("🎉 交付物已就绪！")
                usage = generate_usage_guide(zip_path)
                print(usage)
                print(f"📎 实际文件位置：{zip_path}")
                print("="*40)
                print("\n（模拟自动发送给客户）")
            else:
                print("❌ 生成失败，请检查错误信息。")
            break

        elif reply.startswith("ASK:"):
            question = reply[4:].strip()
            print(f"❓ 需追问：{question}")
            requirement = input("客户补充：").strip()
        else:
            print("🤔 AI暂时无法理解，请重新描述。")
            requirement = input("客户需求：").strip()

if __name__ == "__main__":
    chat_loop()