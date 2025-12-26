import logging
import re
import time
from typing import Any
from pathlib import Path
from typing import List

from packages.web_automation.src.config import WebAutomationConfig
from packages.web_automation.src.infrastructure.browser_manager import BrowserManager
from packages.web_automation.src.infrastructure.playwright_adapter import OLEDPortalAdapter

# 假设 HLDataLoader 在 anomaly_monitor 包中，这里为了演示业务逻辑，先保留引用
# 实际生产中建议通过参数注入 DataFrame，而不是在 Service 里自己去 Load 数据
# from packages.anomaly_monitor.src.infrastructure.loader import HLDataLoader 

logger = logging.getLogger("DownloadService")

class DownloadService:
    """
    [Application Service]
    负责编排日报下载的业务流程。
    """
    
    def __init__(self, global_config: WebAutomationConfig):
        """
        :param global_config: 可以是全局 AppConfig 对象，也可以是字典
        """

        # 2. 使用 Adapter Config 转换为内部配置对象
        self.config = global_config
        self.download_dir = Path(self.config.download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Infrastructure
        self.browser_manager = BrowserManager(self.config.browser)
        self.page = None
        self.portal_adapter = None

    def _setup_download_listener(self):
        """配置下载监听"""
        if not self.page: return

        def handle_download(download):
            try:
                original_name = download.suggested_filename
                safe_name = re.sub(r'[\\/*?:"<>|]', "_", original_name)
                final_path = self.download_dir / safe_name
                
                logger.info(f"⬇️ 开始下载: {original_name}")
                download.save_as(final_path)
                logger.info(f"💾 保存成功: {final_path}")
            except Exception as e:
                logger.error(f"❌ 下载失败: {e}")

        self.page.on("download", handle_download)

    def run_download_tasks(self, product_models: List[str]):
        """
        执行下载任务的主入口
        :param product_models: 需要筛选的产品型号列表 (从外部传入)
        """
        logger.info(">>> 启动下载服务 <<<")
        
        try:
            # 1. 启动浏览器
            self.page = self.browser_manager.start_browser()
            self.portal_adapter = OLEDPortalAdapter(self.page, self.config.browser.timeout)
            self._setup_download_listener()

            # 2. 登录
            self.portal_adapter.navigate_to_home(self.config.daily_report.portal_url)
            if self.config.daily_report.username:
                self.portal_adapter.login(self.config.daily_report.username, self.config.daily_report.password)

            # 3. 遍历下载任务
            for i, report in enumerate(self.config.daily_report.reports):
                logger.info(f"--- 处理报表 [{i+1}/{len(self.config.daily_report.reports)}]: {report.name} ---")
                
                try:
                    # 3.1 进入报表
                    self.portal_adapter.search_and_enter_report(report.name, report.path)
                    
                    # 3.2 业务操作 (日期、筛选)
                    self.portal_adapter.set_date_to_today_if_morning()
                    
                    if report.name == "V3入库良率by品类趋势与良率管控报表":
                        self.portal_adapter.fill_special_v3_criteria()
                    elif product_models:
                        self.portal_adapter.fill_product_models(product_models)
                    
                    # 3.3 导出
                    self.portal_adapter.click_query()
                    self.portal_adapter.wait_for_report_load()
                    self.portal_adapter.export_excel_original()
                    
                    # 3.4 重置
                    self.portal_adapter.reset_search_state()
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"报表 {report.name} 处理出错: {e}")
                    self.portal_adapter.reset_search_state()
                    continue

        except Exception as e:
            logger.critical(f"下载服务崩溃: {e}")
            raise
        finally:
            self._handle_shutdown()

    def _handle_shutdown(self):
        """退出策略"""
        if self.config.browser.headless:
            logger.info("任务结束，正在关闭浏览器...")
            self.browser_manager.stop_browser()
        else:
            logger.info("任务结束。浏览器保持开启 (非Headless模式)。")