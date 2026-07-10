# deepseek_utils.py
import openai

client = openai.OpenAI(
    api_key="sk-8450ec174722497c9c3e58cf3dbf7f5e",   # <--- 改这里
    base_url="https://api.deepseek.com"
)

def ask_deepseek(prompt: str, system: str = "你是一个专业的Python程序员"):
    """调用DeepSeek，返回回复内容"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        stream=False
    )
    return response.choices[0].message.content