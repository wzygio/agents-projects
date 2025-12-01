# 文件路径: src/daily_report/infrastructure/web/oled_portal.py
import logging
from playwright.sync_api import Page, Frame
from src.config import config

class OLEDPortalPage:
    def __init__(self, page: Page):
        self.page = page
        self.default_timeout = config.timeout 
        
        # --- 1. 主页/登录页元素 (这些通常在主 Frame) ---
        self.SELECTOR_LOGIN_USER = "input[placeholder='用户名']"
        self.SELECTOR_LOGIN_PWD = "input[placeholder='密码']"
        self.SELECTOR_LOGIN_BTN = "div.login-button"
        self.SELECTOR_SEARCH_ICON = "div.platform-search-font"       
        self.SELECTOR_SEARCH_INPUT = "input.bi-input[type='text']" 
        self.SELECTOR_CANCEL_BTN = "div.bi-icon-change-button" 
        self.SELECTOR_CLEAR_SEARCH_BTN = "div.close-font"

        # --- 2. 报表内部元素 (这些在 Iframe 里) ---
        # 【关键修改】使用 widgetname 属性，这是帆软报表控件的唯一标识
        # 对应你截图中的 <div widgetname="CMCBPRODCODE">
        self.SELECTOR_PRODUCT_WRAPPER = "div[widgetname='CMCBPRODCODE']"
        # 具体的输入框在 Wrapper 内部
        self.SELECTOR_PRODUCT_INPUT = f"{self.SELECTOR_PRODUCT_WRAPPER} input.fr-trigger-texteditor"

    def navigate_to_home(self, url: str):
        logging.info(f"正在访问系统: {url}")
        self.page.goto(url)
        # 跳转后不需要立即检查搜索图标，因为可能需要登录

    def login(self, username, password):
        """执行登录操作"""
        logging.info("检查是否需要登录...")
        try:
            if self.page.is_visible(self.SELECTOR_LOGIN_USER):
                logging.info("检测到登录界面，开始自动登录...")
                self.page.fill(self.SELECTOR_LOGIN_USER, username)
                self.page.fill(self.SELECTOR_LOGIN_PWD, password)
                self.page.click(self.SELECTOR_LOGIN_BTN)
                logging.info("已点击登录，等待跳转...")
                
                self.page.wait_for_selector(
                    self.SELECTOR_SEARCH_ICON, 
                    state="visible", 
                    timeout=self.default_timeout
                )
                logging.info("登录成功。")
            else:
                logging.info("未检测到登录框，跳过。")
        except Exception as e:
            logging.error(f"登录失败: {e}")
            raise e

    def search_and_enter_report(self, report_config: dict):
        """
        搜索并点击报表 (支持路径校验)
        :param report_config: 包含 {'name': str, 'path': str} 的字典
        """
        report_name = report_config.get("name")
        report_path = report_config.get("path") # 可能为 None
        
        logging.info(f"准备搜索报表: {report_name} (路径: {report_path or '任意'})")

        # 1. 搜索动作
        self.page.click(self.SELECTOR_SEARCH_ICON)
        self.page.wait_for_selector(self.SELECTOR_SEARCH_INPUT, state="visible", timeout=self.default_timeout)
        self.page.fill(self.SELECTOR_SEARCH_INPUT, "")
        self.page.type(self.SELECTOR_SEARCH_INPUT, report_name, delay=100)
        
        logging.info("正在匹配搜索结果...")
        self.page.wait_for_timeout(1000)

        # 2. 【核心修改】 定位逻辑
        try:
            if report_path:
                # === 方案 A：精确匹配（名称 + 路径） ===
                # 逻辑：
                # 1. 找到所有搜索结果的行容器 (通常是 div.bi-v 或类似的通用容器)
                #    这里我们用一个比较宽泛的定位: 包含 report_name 的 div
                # 2. 过滤：保留包含 report_path 的那个
                
                # 这里的策略是：先找到包含报表名字的区域，再看这个区域附近有没有对应的路径
                # 这是一个非常强大的 Playwright 组合拳
                target_report = self.page.locator("div") \
                    .filter(has_text=report_name) \
                    .filter(has_text=report_path) \
                    .last # 如果有多个匹配，通常取最后一个或者是具体的某一个
                
                # 确认找到后再点击里面的名字，防止点到路径文字上
                target_report.get_by_text(report_name).click(timeout=1000)
                
            else:
                # === 方案 B：模糊匹配（仅名称） ===
                # 保持原来的逻辑，直接点名字
                self.page.get_by_text(report_name).first.click(timeout=1000)

            logging.info(f"已点击报表: {report_name}")
            
        except Exception as e:
            logging.error(f"无法定位报表: {report_name} (路径: {report_path})。错误: {e}")
            raise e
        
        # 3. 等待加载
        self.page.wait_for_timeout(5000)

    def get_report_frame(self) -> Frame:
        """
        [修改版] 获取当前激活（可见）的报表 Iframe
        """
        logging.info("正在定位当前活动的报表 Frame...")
        
        # 遍历页面上所有的 frame
        for frame in self.page.frames:
            # 跳过主页面
            if frame == self.page.main_frame:
                continue
            
            try:
                # 【核心修复】
                # 1. 获取 frame 对应的 HTML 元素 (<iframe ...>)
                frame_element = frame.frame_element()
                
                # 2. 检查这个 iframe 标签本身是否可见
                # 如果是后台标签页，这个 iframe 通常是 hidden 或 display: none
                if not frame_element.is_visible():
                    continue

                # 3. 再次确认这个 frame 里有没有我们要的控件
                if frame.locator(self.SELECTOR_PRODUCT_WRAPPER).count() > 0:
                    logging.info(f"成功锁定可见的报表 Frame: {frame.name or 'Unknown'}")
                    return frame
                    
            except Exception:
                # 忽略那些甚至无法访问元素的 frame（可能是跨域广告等）
                continue
        
        # 如果找不到，抛出更明确的错误，不要返回 main_frame 碰运气了
        error_msg = "未找到包含目标控件的可见 Iframe。请确认报表是否加载完成，或控件名称 widgetname 是否变更。"
        logging.error(error_msg)
        raise Exception(error_msg)

    def fill_product_models(self, models: list):
        """输入产品型号 (支持多选)"""
        if not models:
            return

        logging.info(f"开始录入产品型号: {models}")
        
        # 1. [核心修改] 获取正确的 Frame (上下文)
        frame = self.get_report_frame()
        
        try:
            # 2. 确保控件可见 (是在 frame 里找，不是 page 里找)
            frame.wait_for_selector(
                self.SELECTOR_PRODUCT_WRAPPER, 
                state="visible", 
                timeout=self.default_timeout
            )
            
            # 3. 点击包装器 (Wrapper) 激活输入框
            # 帆软特性：必须先点一下外壳，Input 才会准备好接收键盘事件
            frame.click(self.SELECTOR_PRODUCT_WRAPPER)
            
            # 4. 循环输入
            for model in models:
                # 定位内部的 Input
                frame.type(self.SELECTOR_PRODUCT_INPUT, model, delay=100)
                # 等待一秒
                frame.wait_for_timeout(1000)
                frame.press(self.SELECTOR_PRODUCT_INPUT, "Tab")
                
                # 稍作缓冲等待标签生成
                frame.wait_for_timeout(300)

            logging.info("产品型号录入完成。")
            
        except Exception as e:
            logging.error(f"填写产品型号失败 (请检查控件 widgetname 是否变更): {e}")
            raise e

    def reset_search_state(self):
        """重置搜索状态"""
        try:
            if self.page.is_visible(self.SELECTOR_CLEAR_SEARCH_BTN):
                self.page.click(self.SELECTOR_CLEAR_SEARCH_BTN)
                self.page.wait_for_selector(self.SELECTOR_SEARCH_ICON, state="visible", timeout=5000)
        except:
            pass