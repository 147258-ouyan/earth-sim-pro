# -*- coding: utf-8 -*-
import os
import sys

def main():
    print("程序已启动，正在处理，请稍候...")
    
    # 获取当前文件夹路径
    current_dir = os.getcwd()
    
    try:
        # 获取当前文件夹下所有文件和文件夹
        items = os.listdir(current_dir)
        
        if not items:
            print("当前文件夹为空，没有可列出的内容。")
        else:
            # 将文件名写入文件清单.txt
            with open("文件清单.txt", "w", encoding="utf-8") as f:
                for item in items:
                    f.write(item + "\n")
            print("处理完成！结果已保存为 文件清单.txt。")
    
    except Exception as e:
        print(f"处理过程中出现错误：{e}")
    
    input("按回车键退出...")

if __name__ == "__main__":
    main()