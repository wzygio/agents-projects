import pyautogui
import pyperclip
import time
import keyboard

def locate_and_click(image_path, region=None, retries=3, confidence=0.8, interval=0.05, optional=False):
    """
    在界面上通过图片匹配定位目标位置，并点击。
    
    :param image_path: 目标图片的路径
    :param retries: 图片匹配失败时的重试次数
    :param confidence: 匹配的置信度
    :param region: 匹配范围，格式为 (left, top, width, height)
    """
    if not image_path:
        raise ValueError("图片路径无效，请检查配置文件！")
    print(f"正在匹配图片：{image_path}")
    
    for attempt in range(retries):
        try:
            location = pyautogui.locateCenterOnScreen(
                image_path,
                confidence=confidence,
                region=region
            )
            if location:
                print(f"图片匹配成功，位置：{location}")
                x, y = location
                pyautogui.click(x, y)
                time.sleep(interval) # 等待点击完成
                return
        except pyautogui.ImageNotFoundException:
            pass
        
        print(f"第 {attempt + 1} 次匹配失败，等待 1 秒后重试...")
        time.sleep(1)
    
    if optional:
        print(f"未能匹配到图片 {image_path}，但忽略错误并继续执行...")
        return False  # 返回 False 表示匹配失败
    else:
        raise Exception(f"图片匹配失败，请检查图片路径或界面状态：{image_path}")

def locate_any_and_click(image_paths, region=None, retries=3, confidence=0.8):
    """
    在界面上通过图片匹配定位目标位置，并点击（支持多张图片）。
    
    :param image_paths: 图片路径列表
    :param retries: 每张图片匹配失败时的重试次数
    :param confidence: 匹配的置信度
    :param region: 匹配范围，格式为 (left, top, width, height)
    """
    if not isinstance(image_paths, list) or len(image_paths) == 0:
        raise ValueError("图片路径列表无效，请提供至少一张图片路径！")
    
    print(f"正在匹配多张图片：{image_paths}")
    
    for attempt in range(retries):
        for image_path in image_paths:
            try:
                location = pyautogui.locateCenterOnScreen(
                    image_path,
                    confidence=confidence,
                    region=region
                )
                if location:
                    print(f"图片匹配成功，位置：{location}")
                    x, y = location
                    pyautogui.click(x, y)
                    return
            except pyautogui.ImageNotFoundException:
                continue
        
        print(f"第 {attempt + 1} 次匹配失败，等待 1 秒后重试...")
        time.sleep(1)
    
    raise Exception(f"所有图片匹配失败，请检查图片路径或界面状态：{image_paths}")

def paste_text(text, interval=0.05):
    """
    将指定文本复制到剪贴板并粘贴。
    
    :param text: 要输入的文本
    """
    print(f"正在复制文本到剪贴板：{text}")  # 打印正在复制文本的提示信息
    pyperclip.copy(text)  # 将文本复制到剪贴板
    
    print("正在粘贴文本...")  # 打印正在粘贴文本的提示信息
    pyautogui.hotkey('ctrl', 'v')  # 模拟 Ctrl + V 粘贴
    time.sleep(interval)  # 等待粘贴完成

def type_chinese(text, interval=0.05):
    """
    使用 keyboard 库输入中文文本。
    
    :param text: 要输入的文本
    :param interval: 每个字符之间的输入间隔（秒）
    """
    print(f"正在输入中文文本：{text}")
    for char in text:
        keyboard.write(char)  # 输入单个字符
        time.sleep(interval)

def type_and_search(search_icon_image, search_box_image, text, interval=0.05):
    """
    找到搜索框并输入文本。
    
    :param search_box_image: 搜索框图片路径
    :param text: 要输入的文本
    :param interval: 每个字符之间的输入间隔（秒）
    """
    print(f"正在匹配搜索图标图片：{search_box_image}")
    locate_and_click(search_icon_image) # 先点击搜索图标
    time.sleep(interval) # 等待搜索图标被点击

    print(f"正在匹配搜索框图片：{search_box_image}")
    locate_and_click(search_box_image) # 再点击搜索框
    time.sleep(interval) # 等待搜索框被点击

    print("已点击搜索框，开始输入文本...")
    type_chinese(text) # 输入中文文本
    print(f"已输入文本：{text}")

    time.sleep(3) # 等待搜索完成

def auto_type_segments(text, interval=0.05, delimiter="enter"):
    """
    将字符串按空格分割，并依次输入每段内容。
    
    :param text: 要输入的完整字符串
    :param interval: 每个字符之间的输入间隔（秒）
    :param delimiter: 分隔符类型，可选值为 "space"（空格）或 "enter"（回车）
    """

    # 依次输入每个片段
    for i, segment in enumerate(text):
        pyautogui.write(segment, interval=interval)  # 输入当前片段
        
        # 根据分隔符类型模拟按键
        if delimiter == "space":
            pyautogui.press('space')  # 按下空格键
        elif delimiter == "enter":
            pyautogui.press('enter')  # 按下回车键
        else:
            raise ValueError("无效的分隔符类型，请选择 'space' 或 'enter'")
        
        print(f"已输入第 {i+1} 段内容：{segment}")
        
        time.sleep(interval)

def switch_to_english_input(chinese_icon_path="resources/chinese_input_icon.png"):
    """
    切换到英文输入法（如果当前不是英文输入法）。
    """
    if __detect_input_method(chinese_icon_path):
        print("当前是中文输入法，切换到英文输入法...")
        pyautogui.press('shift')  # 按下 Shift 键切换输入法
        time.sleep(0.5)  # 等待切换完成
    else:
        print("当前已经是英文输入法，无需切换")
            

def switch_to_chinese_input(chinese_icon_path="resources/chinese_input_icon.png"):
    """
    切换到中文输入法（如果当前不是中文输入法）。
    """
    if not __detect_input_method(chinese_icon_path):
        print("当前是英文输入法，切换到中文输入法...")
        pyautogui.press('shift')  # 按下 Shift 键切换输入法
        time.sleep(0.5)  # 等待切换完成
    else:
        print("当前已经是中文输入法，无需切换")


def __detect_input_method(chinese_icon_path="resources/chinese_input_icon.png", confidence=0.6):
    """
    检测当前输入法是否为中文输入法。
    
    :param chinese_icon_path: 中文输入法图标的路径
    :param confidence: 匹配的置信度
    :return: True 表示中文输入法，False 表示非中文输入法
    """
    print(f"正在检测图片：{chinese_icon_path}")
    try:
        location = pyautogui.locateOnScreen(chinese_icon_path, confidence=confidence)
        if location:
            print("当前输入法为中文输入法")
            return True
        else:
            print("当前输入法为非中文输入法（例如英文输入法）")
            return False
    except pyautogui.ImageNotFoundException:
        print(f"未能找到图片：{chinese_icon_path}，请检查图片路径或界面状态")
        return False


