import os

def wash_file(input_path, output_path):
    """
    读取任意文本文件（尝试多种编码），并将其清洗为标准的 UTF-8 格式文件。
    主要用于解决编码报错和文件加密剥离问题。
    """
    # 1. 定义可能出现的编码格式 (按优先级排列)
    # Spotfire 导出常见编码：UTF-16 (带BOM), GBK (中文环境), UTF-8
    encodings_to_try = ['utf-8', 'gbk', 'gb18030', 'utf-16', 'cp1252']
    
    content = None
    success_encoding = None

    # 2. 尝试读取
    print(f"正在尝试读取文件: {input_path}")
    for enc in encodings_to_try:
        try:
            with open(input_path, mode='r', encoding=enc) as f:
                content = f.read()
                success_encoding = enc
                print(f"✅ 成功使用 [{enc}] 编码读取！")
                break
        except UnicodeDecodeError:
            print(f"   跳过 [{enc}] 编码...")
        except Exception as e:
            print(f"❌ 读取发生其他错误: {e}")
            return

    if content is None:
        print("❌ 失败：所有编码都无法读取该文件。可能它不是文本文件。")
        return

    # 3. 写入新文件 (强制转换为 utf-8)
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, mode='w', encoding='utf-8') as f_out:
            f_out.write(content)
        
        print(f"✅ 文件已清洗并保存至: {output_path}")
        print("   (现在你可以将这个新文件上传给我了)")
        
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

# --- 执行区 ---
if __name__ == "__main__":
    # 修改这里：你的源文件路径 (刚才报错的那个文件)
    # 无论是 .txt, .csv 还是 .dxp 导出的其他文本格式，统统可以处理
    source_file = r"C:\Users\V0141351\Desktop\复制内容" 
    
    # 修改这里：你想生成的新文件路径
    target_file = r"C:\Users\V0141351\Desktop\output.txt"
    
    wash_file(source_file, target_file)