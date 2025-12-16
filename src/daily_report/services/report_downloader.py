# 文件路径: src/daily_report/services/report_downloader.py
import sys, os, logging
import re
import time
import traceback
from pathlib import Path

# 路径修正
try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 

from src.config import config, PROJECT_ROOT
from src.common.infrastructure.browser.manager import BrowserManager
from src.daily_report.infrastructure.web.oled_portal import OLEDPortalPage

from src.common.utils.log_utils import setup_logging
setup_logging("report_downloader.log")

class DailyReportDownloader:
    
    def __init__(self):
        self._setup_logging()
        self.browser_manager = BrowserManager()
        self.page = None
        self.portal = None
        
        self.download_dir = PROJECT_ROOT / "downloads"
        
        # 确保文件夹存在
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"📂 锁定下载目标路径: {self.download_dir}")

    def _setup_logging(self):
        log_level_str = getattr(config, 'log_level', 'INFO').upper()
        logging.basicConfig(
            level=getattr(logging, log_level_str),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def start(self):
        """启动浏览器和初始化页面对象"""
        try:
            logging.info("正在启动 Playwright 引擎...")
            self.page = self.browser_manager.start_browser()
            
            if self.page is None: 
                raise Exception("浏览器启动失败 (self.page is None)")
            
            logging.info("正在初始化 OLEDPortalPage...")
            # 【这里是崩溃的高发地】
            self.portal = OLEDPortalPage(self.page)
            
            if self.portal is None:
                raise Exception("Portal 初始化失败")

            logging.info("浏览器和 Portal 初始化成功")
            
        except Exception as e:
            # 【核心修改】 打印完整的堆栈信息！
            logging.error("❌❌❌ 发生致命错误！下面是详细报错位置：")
            logging.error("="*40)
            # 这行代码会把报错的具体行号打印出来
            traceback.print_exc() 
            logging.error("="*40)
            
            # 为了防止后面报 TargetClosedError，这里把对象置空
            self.page = None
            self.portal = None
            raise e

    def stop(self):
        self.browser_manager.stop_browser()

    def _sanitize_filename(self, filename):
        # 清洗非法字符
        return re.sub(r'[\\/*?:"<>|]', "_", filename)

    def _setup_download_listener(self):
        """
        [新增] 配置自动下载监听器
        即便是在手动操作期间，只要有下载发生，这里都会自动接管并保存文件。
        """
        # 检查 page 对象是否存在
        if self.page is None:
            logging.error("无法设置下载监听器：page 对象为 None")
            return
        
        def handle_download(download):
            try:
                # 使用建议的文件名
                suggested_filename = download.suggested_filename
                final_path = self.download_dir / suggested_filename
                
                # 保存文件
                download.save_as(final_path)
                logging.info(f"💾 [检测到下载] 文件已自动保存至: {final_path}")
                # 可以在这里打印一行显眼的提示，告诉用户去哪里找文件
                print(f"   >>> 文件已保存: {final_path}")
            except Exception as e:
                logging.error(f"保存下载文件失败: {e}")

        # 将监听器绑定到页面上
        self.page.on("download", handle_download)

    def execute_workflow(self):
        logging.info(">>> [启动] 日报下载自动化任务 <<<")
        
        try:
            self.start()
            if self.portal is None: return
            
            # 1. 先挂载监听器
            self._setup_download_listener()

            # 2. 业务流程
            target_url = config.portal_url
            if target_url:
                # 确保将 URL 转换为字符串
                url_str = str(target_url) if not isinstance(target_url, str) else target_url
                self.portal.navigate_to_home(url_str)


            username = config.username
            password = config.password
            if username and password:
                self.portal.login(username, password)
            
            report_config_list = config.reports 
            global_models = config.product_models

            for i, report_item in enumerate(report_config_list):
                report_name = report_item.get("name")
                should_skip_input = report_item.get("skip_input", False)
                
                logging.info(f"--- 正在处理: {report_name} ---")
                
                try:
                    self.portal.search_and_enter_report(report_item)
                    if not should_skip_input:
                        models_list = list(global_models) if isinstance(global_models, (list, tuple)) else []
                        self.portal.fill_product_models(models_list)
                        self.portal.click_query()
                        self.portal.wait_for_report_load()
                        self.portal.export_excel_original()
                    self.portal.reset_search_state()
                    time.sleep(1) 

                except Exception as inner_e:
                    logging.error(f"处理失败: {inner_e}")
                    try: self.portal.reset_search_state()
                    except: pass
                    continue

        except Exception as e:
            logging.error(f"崩溃: {e}")
            
        finally:
            try:
                while True:
                    self.page.wait_for_timeout(1000) if self.page else None
            except KeyboardInterrupt:
                logging.info("接收到退出指令，正在关闭...")
                self.stop()

if __name__ == "__main__":
    downloader = DailyReportDownloader()
    downloader.execute_workflow()