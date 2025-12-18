# 文件路径: src/daily_report/infrastructure/web/oled_portal.py
import logging, time
from playwright.sync_api import Page, Frame
from src.config import config
from datetime import datetime


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
        
        self.page.wait_for_timeout(3000)

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

    def set_date_to_today_if_morning(self):
        """
        根据时间判断是否需要重置日期。
        【修复版 V2】通过指定 table.mt (月视图) 和 table.dt (日视图) 来区分两个“确定”按钮。
        """
        
        # 1. 获取 Frame
        logging.info("正在初始化日期设置，准备获取报表 Frame...")
        frame = self.get_report_frame()
        
        # ====== 第一部分：开始日期设置逻辑 ======
        try:
            # 【步骤 1】点击“开始日期”触发器
            start_trigger = frame.locator("div[widgetname='DTSTARTDATE'] .fr-date-trigger-center")
            
            if start_trigger.count() > 0:
                start_trigger.click()
                logging.info("已点击[开始日期]触发器，等待弹窗...")
                
                # 【步骤 2】锁定当前可见的日期面板
                date_panel = frame.locator("div.fr-datepicker").filter(has_text="周").locator("visible=true").first
                date_panel.wait_for(state="visible", timeout=5000)

                # 【步骤 3】执行选月逻辑
                now = datetime.now()
                target_month_num = now.month - 2
                if target_month_num <= 0:
                    target_month_num += 12
                    
                month_map = {
                    1: "一月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
                    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月"
                }
                target_month_str = month_map[target_month_num]
                
                # 3.1 点击标题切换视图
                # 标题通常在日视图头部，但也可能在月视图，这里一般点 dt 里的即可，或者通用
                date_panel.locator("td.title").first.click()
                self.page.wait_for_timeout(300) 
                
                # 3.2 点击目标月份
                # 月份肯定在 table.mt 里
                logging.info(f"正在选择月份: {target_month_str}")
                date_panel.locator(f"table.mt td.month:has-text('{target_month_str}')").click()
                self.page.wait_for_timeout(300)
                
                # 3.3 点击第一次确定 (确认月份)
                # 【核心修复】指定 table.mt (Month Table) 下的确定按钮
                # 这样就绝对不会点到后面 table.dt 的按钮了
                date_panel.locator("table.mt td.btn.ok").click()
                self.page.wait_for_timeout(300)
                
                # 3.4 点击第二次确定 (关闭弹窗)
                # 此时应该回到了日视图，我们指定 table.dt (Date Table) 下的确定按钮
                ok_btn_final = date_panel.locator("table.dt td.btn.ok")
                if ok_btn_final.is_visible():
                    ok_btn_final.click()
                    # 等待弹窗消失
                    date_panel.wait_for(state="hidden", timeout=5000)
                
                logging.info(f"Playwright: 已将开始日期设置为：{target_month_str}")
                self.page.wait_for_timeout(1000) 

            else:
                logging.info("未检测到[开始日期]控件 (DTSTARTDATE)，跳过设置。")

        except Exception as e:
            logging.warning(f"设置开始日期时发生非致命错误: {e}")

        # ====== 第二部分：结束日期设置逻辑 ======
        now_hour = datetime.now().hour
        if now_hour <= 9:
            logging.info(f"当前时间 ({datetime.now().strftime('%H:%M')}) 早于 9:00，跳过结束日期重置。")
            return

        logging.info("当前时间晚于 9:00，开始重置[结束日期]为[今天]...")
        
        try:
            # 【步骤 1】点击“结束日期”触发器
            end_trigger = frame.locator("div[widgetname='DTENDDATE'] .fr-date-trigger-center, div[widgetname='DTDATETIME'] .fr-date-trigger-center").first
            
            end_trigger.wait_for(state="visible", timeout=30000)
            end_trigger.click()
            logging.info("已点击结束日期选择框。")

            # 【步骤 2】锁定弹窗并点击“今天”
            date_panel = frame.locator("div.fr-datepicker").filter(has_text="周").locator("visible=true").first
            date_panel.wait_for(state="visible", timeout=5000)
            
            # 点击“今天”按钮 (今天按钮只存在于日视图 table.dt 中)
            date_panel.locator("table.dt td.btn.today").click()
            
            # 【步骤 3】收尾确认
            self.page.wait_for_timeout(500)
            # 检查 table.dt 下是否有残留的确定按钮
            ok_btn = date_panel.locator("table.dt td.btn.ok")
            if ok_btn.is_visible():
                 ok_btn.click()
            
            # 再次确认弹窗已消失
            date_panel.wait_for(state="hidden", timeout=5000)
            
            logging.info("已成功设置日期为 [今天]。")

        except Exception as e:
            logging.error(f"设置日期失败: {e}")
            raise e
        
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

    def fill_special_v3_criteria(self):
        """
        【特殊处理】V3入库良率报表的筛选逻辑 (最终修正版)
        解决问题：
        1. 避免定位到输入框内的 tag，而是定位下拉菜单项。
        2. 使用 force=True 解决 pointer events intercepted (点击被拦截) 的问题。
        """
        logging.info("开始执行 V3报表 特殊筛选逻辑...")
        frame = self.get_report_frame()

        try:
            # ====== 1. 处理“产品类型” (Product Type) ======
            logging.info("正在操作：产品类型...")
            
            # 定位下拉三角 (使用 css 扩展语法 right-of)
            trigger_type = frame.locator(
                ".fr-trigger-btn-up:right-of(pre.fr-label:has-text('产品类型'), 80)"
            ).first
            
            trigger_type.wait_for(state="visible", timeout=3000)
            trigger_type.click()
            
            # --- 下拉菜单操作 ---
            # 等待“全选/不选”可见
            select_all_option = frame.get_by_text("全选/不选").first
            select_all_option.wait_for(state="visible")
            select_all_option.click()
            logging.info("已点击 [产品类型] -> 全选")
            
            # [关键修复步骤]
            # 1. 定位：不要只用 get_by_text，因为那会找到输入框里的 Tag。
            #    我们要找的是带有 .fr-checkbox-checkon (已选中状态) 类的下拉选项。
            # 2. 暴力点击：使用 force=True，跳过 Playwright 的可见性/遮挡检查，直接触发。
            logging.info("准备取消勾选 [直板LTPS_含FIAA]...")
            
            exclude_item = frame.locator(".fr-checkbox-checkon").filter(has_text="直板LTPS_含FIAA").first
            
            # 这里的 wait_for 稍微放宽一点，只要 attached 即可，防止 visible check 失败
            exclude_item.wait_for(state="attached", timeout=3000)
            
            if exclude_item.is_visible():
                exclude_item.click(force=True)  # <--- 核心修改：强制点击
                logging.info("已取消勾选 [直板LTPS_含FIAA]")
            else:
                # 如果没显示出来（可能需要滚动下拉菜单），尝试强制点击不管它显不显示
                logging.warning("选项未完全可见，尝试强制点击...")
                exclude_item.click(force=True)

            # 点击标签收起菜单
            frame.locator("pre.fr-label").filter(has_text="产品类型").first.click()
            self.page.wait_for_timeout(300) 


            # ====== 2. 处理“产品型号” (Product Model) ======
            logging.info("正在操作：产品型号...")
            
            trigger_model = frame.locator(
                ".fr-trigger-btn-up:right-of(pre.fr-label:has-text('产品型号'), 80)"
            ).first
            
            trigger_model.click()
            
            # --- 下拉菜单操作 ---
            frame.get_by_text("全选/不选").first.wait_for(state="visible")
            
            # 处理全选
            all_select_btns = frame.get_by_text("全选/不选")
            count = all_select_btns.count()
            if count > 1:
                # 倒序遍历点击，找到一个能点的就行
                clicked = False
                for i in range(count - 1, -1, -1):
                    btn = all_select_btns.nth(i)
                    if btn.is_visible():
                        btn.click(force=True) # 这里也加上 force 比较保险
                        clicked = True
                        break
                if not clicked:
                    all_select_btns.first.click(force=True)
            else:
                all_select_btns.click(force=True)
                
            logging.info("已点击 [产品型号] -> 全选")
            
            # 点击标签收起菜单
            frame.locator("pre.fr-label").filter(has_text="产品型号").first.click()
            self.page.wait_for_timeout(300)

        except Exception as e:
            logging.error(f"V3报表特殊筛选步骤失败: {e}")
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
            frame.locator("div[heavytd]").first.wait_for(state="visible", timeout=120000)
            
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
        点击原样导出，并处理可能出现的"继续"确认按钮
        """
        try:
            # 点击导出按钮
            frame = self.get_report_frame()
            frame.locator(".x-emb-export").click()
            frame.locator("div.menu-text").filter(has_text="Excel").click()
            frame.locator("div.menu-text").filter(has_text="原样导出").click()
            
            # 等待可能出现的"继续"按钮
            time.sleep(1)
            
            try:
                # 使用 Playwright 的方式定位"继续"按钮
                continue_btn = frame.locator("span.fr-core-btn-text", has_text="继续")
                if continue_btn.is_visible():
                    continue_btn.click()
                    logging.info("检测到'继续'按钮，已自动点击。")
            except Exception:
                # 如果找不到按钮或点击失败，忽略继续执行
                pass
            
            time.sleep(1)
        except Exception as e:
            logging.error(f"原样导出过程中发生错误: {e}")
            raise e


    def reset_search_state(self):
        """重置搜索状态"""
        try:
            if self.page.is_visible(self.SELECTOR_CLEAR_SEARCH_BTN):
                self.page.click(self.SELECTOR_CLEAR_SEARCH_BTN)
                self.page.wait_for_selector(self.SELECTOR_SEARCH_ICON, state="visible", timeout=3000)
        except:
            pass