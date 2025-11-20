import time
import pyautogui
from src.config import config  # 引入全局配置对象
from src.utils import locate_and_click, auto_type_segments, switch_to_chinese_input, switch_to_english_input, locate_any_and_click, type_chinese


class AutomationWorkflow:
    def __init__(self):
        """
        初始化业务流程类，加载配置文件。
        """

    def search_and_select_report(self, input_language="zh"):
        """
        在搜索框中输入文件名，选择目标报表，并对每个报表调用 write_product_model。
        """
        print("请切换到目标界面")
        time.sleep(3)  # 等待3秒，确保用户切换到目标界面

        # 切换输入法
        if input_language == "zh":
            switch_to_chinese_input()
        elif input_language == "en":
            switch_to_english_input()
        else:
            raise ValueError(f"不支持的输入语言：{input_language}")
        
        
        report_images = config.report_images or []
        file_name_text = config.file_name_text or []
        for i, (report_image, file_name) in enumerate(zip(report_images, file_name_text)):
            print(f"开始处理第 {i + 1} 个报表...")
            
            # 第一步：找到搜索框并输入文件名
            locate_and_click(config.cancel_icon_image, config.region_top_left, optional=True) # 先点击取消按钮
            locate_and_click(config.search_icon_image, config.region_top_left) # 先点击搜索图标
            locate_and_click(config.search_box_image, config.region_top_left) # 再点击搜索框
            type_chinese(file_name) # 输入中文文本
            time.sleep(1)
            
            # 第二步：选择目标报表
            print(f"正在匹配报表图片：{report_image}")
            try:
                locate_and_click(report_image, config.region_left, confidence=0.9)
                print(f"成功找到报表图片：{report_image}")
                if report_image == "resources/report_image2.png":
                    time.sleep(6)  # 等待3秒，确保报表加载完成
                else:
                    time.sleep(3)  # 等待3秒，确保报表加载完成
            except Exception as e:
                print(f"未能找到报表图片：{report_image}，跳过当前报表。错误：{e}")
                continue
            
            # 第三步：调用 write_product_model 方法
            print("正在输入产品型号...")
            self.write_product_model(input_language="en")  # 英文输入产品型号
            time.sleep(1)
            print(f"第 {i + 1} 个报表处理完成！")

            # 第四步：点击取消按钮
            locate_and_click(config.cancel_icon_image, config.region_top_left)

    def write_product_model(self, input_language="en"):
        """
        定位并点击产品型号输入框，然后输入对应的文本。
        
        :param input_language: 输入语言（"en" 表示英文，"zh" 表示中文）
        """
        
        print("开始输入产品型号...")
        
        # 定义两张图片路径
        cancel_icons = [config.product_model_box_image, config.product_model_box_image_2]
        locate_any_and_click(cancel_icons, config.region_top)

        # 切换输入法
        if input_language == "zh":
            switch_to_chinese_input()
        elif input_language == "en":
            switch_to_english_input()
        else:
            raise ValueError(f"不支持的输入语言：{input_language}")
        
        
        # 输入产品型号文本
        auto_type_segments(config.product_model_text)
        
        print("产品型号输入完成！")

