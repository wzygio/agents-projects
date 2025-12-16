# 文件路径: src/daily_report/infrastructure/web/oled_portal.py
import logging
from playwright.sync_api import Page, Frame
from src.config import config

# 移除所有 Selenium 引用 (By, WebDriverWait, EC)

class OLEDPortalPage:
    # 移除 driver 参数，纯 Playwright 不需要 driver
    def __init__(self, page: Page):
        self.page = page
        self.default_timeout = float(config.timeout) if isinstance(config.timeout, (int, float, str)) and str(config.timeout).replace('.', '').isdigit() else 30000
        
        # --- 1. 主页/登录页元素 (这些通常在主 Frame) ---
        self.SELECTOR_LOGIN_USER = "input[placeholder='用户名']"
        self.SELECTOR_LOGIN_PWD = "input[placeholder='密码']"
        self.SELECTOR_LOGIN_BTN = "div.login-button"
        self.SELECTOR_SEARCH_ICON = "div.platform-search-font"       
        self.SELECTOR_SEARCH_INPUT = "input.bi-input[type='text']" 
        self.SELECTOR_CANCEL_BTN = "div.bi-icon-change-button" 
        self.SELECTOR_CLEAR_SEARCH_BTN = "div.close-font"

        # --- 2. 报表内部元素 (这些在 Iframe 里) ---
        self.SELECTOR_PRODUCT_WRAPPER = "div[widgetname='CMCBPRODCODE']"
        self.SELECTOR_PRODUCT_INPUT = f"{self.SELECTOR_PRODUCT_WRAPPER} input.fr-trigger-texteditor"

    def navigate_to_home(self, url: str):
        logging.info(f"正在访问系统: {url}")
        self.page.goto(url)

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
        """搜索并点击报表"""
        report_name = report_config.get("name")
        if not report_name:
            raise ValueError("报表配置不完整，缺少 'name'")
        
        report_path = report_config.get("path")
        logging.info(f"准备搜索报表: {report_name} (路径: {report_path or '任意'})")

        # 1. 搜索动作
        self.page.click(self.SELECTOR_SEARCH_ICON)
        self.page.wait_for_selector(self.SELECTOR_SEARCH_INPUT, state="visible", timeout=self.default_timeout)
        self.page.fill(self.SELECTOR_SEARCH_INPUT, "")
        self.page.type(self.SELECTOR_SEARCH_INPUT, report_name, delay=100)
        
        logging.info("正在匹配搜索结果...")
        self.page.wait_for_timeout(1000)

        # 2. 定位逻辑
        try:
            if report_path:
                target_report = self.page.locator("div") \
                    .filter(has_text=report_name) \
                    .filter(has_text=report_path) \
                    .last
                
                target_report.get_by_text(report_name).click(timeout=1000)
            else:
                self.page.get_by_text(report_name).first.click(timeout=1000)

            logging.info(f"已点击报表: {report_name}")
            
        except Exception as e:
            logging.error(f"无法定位报表: {report_name}。错误: {e}")
            raise e
        
        self.page.wait_for_timeout(5000)

    def get_report_frame(self) -> Frame:
        """获取当前激活的报表 Iframe"""
        logging.info("正在定位当前活动的报表 Frame...")
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            
            try:
                frame_element = frame.frame_element()
                if not frame_element.is_visible():
                    continue

                if frame.locator(self.SELECTOR_PRODUCT_WRAPPER).count() > 0:
                    return frame
            except Exception:
                continue
        
        error_msg = "未找到包含目标控件的可见 Iframe。"
        logging.error(error_msg)
        raise Exception(error_msg)

    def fill_product_models(self, models: list):
        """输入产品型号"""
        if not models:
            return

        logging.info(f"开始录入产品型号: {models}")
        frame = self.get_report_frame()
        
        try:
            frame.wait_for_selector(self.SELECTOR_PRODUCT_WRAPPER, state="visible", timeout=self.default_timeout)
            frame.click(self.SELECTOR_PRODUCT_WRAPPER)
            
            for model in models:
                frame.type(self.SELECTOR_PRODUCT_INPUT, model, delay=100)
                frame.wait_for_timeout(1000)
                frame.press(self.SELECTOR_PRODUCT_INPUT, "Tab")
                frame.wait_for_timeout(300)

            logging.info("产品型号录入完成。")
        except Exception as e:
            logging.error(f"填写产品型号失败: {e}")
            raise e

    # ==========================================
    # 下面是重写后的 纯 Playwright 查询导出逻辑
    # ==========================================

    def click_query(self):
        """
        1. 点击查询按钮
        对应元素: <button ...>查询</button>
        """
        logging.info("点击查询按钮...")
        frame = self.get_report_frame()
        try:
            # Playwright 写法：在 frame 中查找 button 标签且包含文本 "查询"
            # 使用 exact=False 防止匹配不到带空格的文本，或者使用正则表达式
            query_btn = frame.locator("button", has_text="查询")
            query_btn.click()
        except Exception as e:
            logging.error(f"点击查询按钮失败: {e}")
            raise e

    def wait_for_report_load(self):
        """
        2. 等待结果出现 (通用版)
        逻辑优化：不再等待特定的文本（如 'Yield TrendChart'），
        而是等待报表特有的结构元素出现。
        
        依据：报表内容单元格通常包含 'heavytd' 属性或位于 td 标签内。
        """
        logging.info("等待报表数据渲染 (检测通用结构)...")
        frame = self.get_report_frame()
        try:
            # --- 方案 A (推荐): 检测帆软特有的 heavytd 属性 ---
            # 这个属性存在于您提供的两个示例中，是报表正文单元格的强特征。
            # state="visible" 确保元素不仅存在于DOM中，而且肉眼可见
            frame.locator("div[heavytd]").first.wait_for(state="visible", timeout=60000)
            
            # --- 方案 B (备选): 如果方案 A 超时，也可以尝试检测 id 包含行列坐标的 td ---
            # 帆软报表的 td id 通常格式为 "B1-0-xxx", "A1-0-xxx"
            # frame.locator("td[id*='-0-']").first.wait_for(state="visible", timeout=60000)
            
            logging.info(">> 报表结构已加载完成 (检测到 heavytd 元素)。")
            
            # 稍微多等一点点时间，确保表格渲染完全（有时候第一个格子出来了，后面的还在刷）
            self.page.wait_for_timeout(1000)
            
        except Exception as e:
            logging.error(f"等待报表加载超时。这可能是因为查询无数据，或者页面结构发生了变化。错误: {e}")
            raise e

    def export_excel_original(self):
        """
        3. 导出 -> Excel -> 原样导出
        """
        logging.info("开始执行导出操作...")
        frame = self.get_report_frame()
        try:
            # --- 步骤 3: 点击导出按钮 ---
            # 对应元素 class: x-emb-export
            logging.info("点击导出图标...")
            frame.locator(".x-emb-export").click()

            # --- 步骤 4: 点击 Excel 选项 ---
            # 对应元素: <div class="menu-text">Excel</div>
            # 注意：帆软的下拉菜单有时会渲染在 Main Frame 而不是 Iframe 里
            # 我们先尝试在 Frame 里找，如果找不到（比如报错），逻辑可能需要调整为 self.page.locator
            # 但根据经验，通常在同级 DOM。
            logging.info("选择 Excel...")
            # 使用 locator 配合 filter 精确定位
            frame.locator("div.menu-text").filter(has_text="Excel").click()

            # --- 步骤 5: 点击 原样导出 选项 ---
            # 对应元素: <div class="menu-text">原样导出</div>
            logging.info("选择 原样导出...")
            frame.locator("div.menu-text").filter(has_text="原样导出").click()
            
            logging.info(">> 导出指令已发送。")
            
        except Exception as e:
            logging.error(f"导出流程失败: {e}")
            raise e

    def reset_search_state(self):
        """重置搜索状态"""
        try:
            if self.page.is_visible(self.SELECTOR_CLEAR_SEARCH_BTN):
                self.page.click(self.SELECTOR_CLEAR_SEARCH_BTN)
                self.page.wait_for_selector(self.SELECTOR_SEARCH_ICON, state="visible", timeout=5000)
        except:
            pass