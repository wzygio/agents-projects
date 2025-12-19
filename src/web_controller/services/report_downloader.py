# 文件路径: src/daily_report/services/report_downloader.py
import sys, os, logging, re
import time
import traceback
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    # 动态添加项目根目录到 sys.path，防止导包错误
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 

from src.config import config, PROJECT_ROOT
from src.common.utils.log_utils import setup_logging 
from src.common.infrastructure.hl_data_loader import HLDataLoader
from src.web_controller.infrastructure.web.oled_portal import OLEDPortalPage

# 初始化模块级日志记录器
logger = logging.getLogger("ReportDownloader")

class DailyReportDownloader:
    
    def __init__(self):
        setup_logging("report_downloader.log")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.portal = None
        self.loader = HLDataLoader()
        self.is_headless = bool(config.get('common.HEADLESS_MODE', False))
        
        # 设定下载目录
        self.download_dir = PROJECT_ROOT / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📂 锁定下载目标路径: {self.download_dir}")

    # ==========================================
    # [新增] 数据驱动核心逻辑
    # ==========================================
    def get_high_input_products(self, mwdl_data: pd.DataFrame) -> list:
        """
        【工具函数】提取高投入量的产品型号列表
        逻辑规范:
        1. 筛选范围: date_type == "DAY" (日报数据)
        2. 阈值条件: input_qty > 1000
        3. 提取目标: prod_code
        4. 去重: 返回唯一的产品列表
        """
        # --- 0. 防御性检查 ---
        if mwdl_data is None or mwdl_data.empty:
            logger.warning("⚠️ 输入数据为空，无法提取产品列表")
            return []

        # --- 1. 列名适配 ---
        # 优先匹配 date_type, 其次 data_type
        if 'date_type' in mwdl_data.columns:
            col_type = 'date_type'
        elif 'data_type' in mwdl_data.columns:
            col_type = 'data_type'
        else:
            logger.error("❌ 缺少关键列: date_type 或 data_type")
            return []

        # 确保 input_qty 和 prod_code 存在
        if 'input_qty' not in mwdl_data.columns or 'prod_code' not in mwdl_data.columns:
            logger.error("❌ 数据表缺少 'input_qty' 或 'prod_code' 列")
            return []

        # --- 2. 数据清洗与类型转换 ---
        df_clean = mwdl_data.copy()
        # 确保投入量是数字，无法转换的填充0
        df_clean['input_qty'] = pd.to_numeric(df_clean['input_qty'], errors='coerce').fillna(0)
        
        # 确保列名为字符串并去空格
        df_clean[col_type] = df_clean[col_type].astype(str).str.strip()
        df_clean['prod_code'] = df_clean['prod_code'].astype(str).str.strip()

        # --- 3. 核心筛选逻辑 ---
        # 条件: 日期类型为 DAY 且 投入量 > 1000
        mask = (df_clean[col_type] == 'DAY') & (df_clean['input_qty'] > 1000)
        filtered_df = df_clean[mask]
        
        # --- 4. 提取与去重 ---
        product_list = filtered_df['prod_code'].unique().tolist()
        product_list.sort() # 排序
        
        logger.info(f"✅ 已基于规则提取高投入产品型号: {len(product_list)} 个")
        logger.info(f"   列表详情: {product_list}")
        
        return product_list

        
    def start_browser_engine(self):
        """
        启动浏览器引擎
        根据 config.HEADLESS_MODE 决定是否显示浏览器界面
        """
        try:
            logger.info("🚀 正在启动 Playwright 引擎...")
            self.playwright = sync_playwright().start()
            
            # 读取配置中的运行模式
            
            mode_str = "静默/后台模式" if self.is_headless else "显示/前台模式"
            logger.info(f"当前运行配置: [{mode_str}]")

            # 启动浏览器
            self.browser = self.playwright.chromium.launch(
                headless=self.is_headless,
                args=["--start-maximized"],  # 最大化窗口
                channel="chrome"             # 使用本地 Chrome，更稳定
            )
            
            # 创建上下文 (设置视口大小，防止页面显示不全)
            self.context = self.browser.new_context(no_viewport=True)
            self.page = self.context.new_page()
            
            # 初始化业务页面对象
            logger.info("正在初始化 Portal 页面对象...")
            self.portal = OLEDPortalPage(self.page)
            
            logger.info("✅ 浏览器与页面对象初始化成功。")
            
        except Exception as e:
            logger.critical("❌ 浏览器启动阶段发生致命错误！")
            logger.error(traceback.format_exc())
            raise e

    def stop_browser_engine(self):
        """优雅关闭浏览器资源"""
        try:
            if self.context: self.context.close()
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
            logger.info("🛑 浏览器引擎已关闭。")
        except Exception as e:
            logger.error(f"关闭浏览器时发生错误: {e}")

    def _setup_download_listener(self):
        """配置全局下载监听"""
        if not self.page:
            return
        
        def handle_download(download):
            try:
                # 获取建议文件名并清洗非法字符
                original_name = download.suggested_filename
                safe_name = re.sub(r'[\\/*?:"<>|]', "_", original_name)
                final_path = self.download_dir / safe_name
                
                logger.info(f"⬇️ 检测到下载请求: {original_name}")
                
                # 保存文件
                download.save_as(final_path)
                
                logger.info(f"💾 文件保存成功: {final_path}")
                print(f"   >>> [下载完成] {safe_name}") # 控制台显眼提示
                
            except Exception as e:
                logger.error(f"❌ 保存文件失败: {e}")

        self.page.on("download", handle_download)

    def execute_workflow(self):
        """主执行逻辑"""
        logger.info("="*50)
        logger.info(">>> [启动] 日报下载自动化任务 <<<")
        logger.info("="*50)
        
        try:
            # 1. 启动浏览器
            self.start_browser_engine()
            
            # 2. 挂载下载监听器
            self._setup_download_listener()

            # 检查 portal 是否成功初始化
            if self.portal is None:
                logger.error("❌ Portal 对象初始化失败，无法继续执行任务")
                return

            # 3. 导航与登录
            target_url = str(config.portal_url)
            self.portal.navigate_to_home(target_url)

            if config.username and config.password:
                self.portal.login(config.username, config.password)
            
            # 4. 获取任务配置
            report_config_list = config.reports 
            # global_models = config.product_models
            # models_list = list(global_models) if isinstance(global_models, (list, tuple)) else []
            df_main = self.loader.load_raw_dataframe('mwdl_raw')
            models_list = self.get_high_input_products(df_main)

            # 5. 遍历报表处理
            for i, report_item in enumerate(report_config_list):
                report_name = report_item.get("name")
                logger.info(f"\n--- [任务 {i+1}/{len(report_config_list)}] 正在处理: {report_name} ---")
                
                try:
                    # 5.1 搜索并进入报表
                    self.portal.search_and_enter_report(report_item)
                    
                    # 5.2 设置日期 (仅在9点前执行，函数内部已包含判断逻辑)
                    self.portal.set_date_to_today_if_morning()
                    
                    # 5.3 填写筛选条件 (区分特殊报表和普通报表)
                    if report_name == "V3入库良率by品类趋势与良率管控报表":
                        logger.info("检测到 V3 特殊报表，使用特定筛选逻辑...")
                        self.portal.fill_special_v3_criteria()
                    else:
                        self.portal.fill_product_models(models_list)
                    
                    # 5.4 查询与导出
                    self.portal.click_query()
                    self.portal.wait_for_report_load()
                    self.portal.export_excel_original()
                    
                    # 5.5 重置状态以便进行下一次搜索
                    self.portal.reset_search_state()
                    
                    # 短暂休息，防止操作过快
                    time.sleep(1) 

                except Exception as inner_e:
                    logger.error(f"⚠️ 报表 [{report_name}] 处理失败: {inner_e}")
                    # 尝试重置状态，继续下一个任务
                    try: self.portal.reset_search_state()
                    except: pass
                    continue

            logger.info("\n✅ 所有任务队列执行完毕。")

        except Exception as e:
            logger.critical(f"❌❌❌ 任务流程发生严重崩溃: {e}")
            logger.error(traceback.format_exc())
            
        finally:
            # 6. 结束逻辑：根据配置决定是否关闭浏览器
            self._handle_shutdown()

    def _handle_shutdown(self):
        """根据模式决定退出策略"""
        logger.info("-" * 30)
   
        if self.is_headless:
            # 静默模式：直接关闭
            logger.info("当前为[静默模式]，正在自动关闭浏览器...")
            self.stop_browser_engine()
        else:
            # 显示模式：保持开启，等待人工确认
            logger.info("当前为[显示模式]，浏览器将保持开启以便调试。")
            print("\n" + "="*40)
            print("   任务已结束。浏览器保持开启。")
            print("   按回车键 (Enter) 退出程序并关闭浏览器...")
            print("="*40 + "\n")
            
            try:
                input() # 阻塞等待用户输入
            except KeyboardInterrupt:
                pass
            
            logger.info("接收到退出指令，正在关闭资源...")
            self.stop_browser_engine()

if __name__ == "__main__":
    downloader = DailyReportDownloader()
    downloader.execute_workflow()