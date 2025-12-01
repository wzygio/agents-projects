# 文件路径: src/daily_report/services/report_downloader.py
import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到环境变量，确保可以导入 src 模块
# (仅在独立运行时需要，如果通过 main.py 调用则不需要，保留以防万一)
try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 

from src.config import config, PROJECT_ROOT
from src.common.infrastructure.browser.manager import BrowserManager
from src.daily_report.infrastructure.web.oled_portal import OLEDPortalPage

class DailyReportDownloader:
    """
    日报下载自动化服务
    职责：读取配置 -> 启动浏览器 -> 调度页面操作 -> 异常处理
    """
    
    def __init__(self):
        self._setup_logging()
        self.browser_manager = BrowserManager()
        self.page = None
        self.portal = None

    def _setup_logging(self):
        """配置日志，优先使用配置文件中的级别"""
        # [修改] 直接使用 config.log_level
        log_level_str = config.log_level.upper()
        
        logging.basicConfig(
            level=getattr(logging, log_level_str),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def start(self):
        """启动浏览器和初始化页面对象"""
        try:
            self.page = self.browser_manager.start_browser()
            if self.page is None:
                raise Exception("浏览器启动失败")
                
            self.portal = OLEDPortalPage(self.page)
            if self.portal is None:
                raise Exception("Portal 初始化失败")
                
            logging.info("浏览器和 Portal 初始化成功")
        except Exception as e:
            logging.error(f"初始化失败: {e}")
            self.page = None
            self.portal = None
            raise

    def stop(self):
        """停止任务并释放资源"""
        self.browser_manager.stop_browser()

    def _setup_download_listener(self):
        """
        [新增] 配置自动下载监听器
        即便是在手动操作期间，只要有下载发生，这里都会自动接管并保存文件。
        """
        # 确保下载目录存在
        download_dir = config.download_path

        def handle_download(download):
            try:
                # 使用建议的文件名
                suggested_filename = download.suggested_filename
                final_path = download_dir / suggested_filename
                
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
        """
        执行核心业务工作流
        """
        logging.info(">>> [启动] 日报下载自动化任务 <<<")
        
        try:
            self.start()

            # 检查初始化是否成功
            if self.portal is None:
                logging.error("Portal 初始化失败")
                return
            
            self._setup_download_listener()

            # 1. [新增] 跳转到系统主页
            target_url = config.portal_url
            if not target_url:
                logging.error("未配置 portal_url，无法继续任务。")
                return

            username = config.username
            password = config.password
            
            # 跳转到系统主页
            self.portal.navigate_to_home(target_url)

            # 2. [新增] 执行登录
            if username and password:
                self.portal.login(username, password)
            else:
                logging.warning("未配置账号密码，跳过自动登录步骤（可能导致后续操作失败）。")
            
            # 获取配置
            report_config_list = config.reports 
            # 获取全局默认的产品型号
            global_models = config.product_models

            # 循环处理
            for i, report_item in enumerate(report_config_list):
                report_name = report_item.get("name")
                # 获取是否跳过输入的标记 (默认为 False，即不跳过)
                should_skip_input = report_item.get("skip_input", False)
                
                logging.info(f"--- 正在处理第 {i + 1}/{len(report_config_list)} 个报表: {report_name} ---")
                
                try:
                    # 1. 搜索并进入报表
                    self.portal.search_and_enter_report(report_item)
                    
                    # 2. 灵活控制：判断是否需要输入型号
                    if should_skip_input:
                        logging.info(f"配置标记为 [skip_input]，跳过产品型号输入步骤。")
                    else:
                        # 如果没有标记跳过，则执行输入
                        # (未来如果不同报表需要不同型号，也可以在这里读取 report_item.get('models'))
                        self.portal.fill_product_models(global_models)
                    
                    # 3. 状态闭环
                    self.portal.reset_search_state()
                    
                    time.sleep(1) # 稍微缓冲

                except Exception as inner_e:
                    logging.error(f"处理报表 [{report_name}] 时发生错误: {inner_e}")
                    try:
                        self.portal.reset_search_state()
                    except:
                        pass
                    continue

                logging.info(f"报表 [{report_name}] 处理完成。")
        except Exception as e:
            logging.error(f"自动化任务主要流程崩溃: {e}")
        finally:
            # 【步骤 2】 替换 input() 为无限循环等待
            # 这样 Python 进程保持活跃，能够响应浏览器的下载事件
            try:
                while True:
                    # 每 1 秒“呼吸”一次，保持连接
                    self.page.wait_for_timeout(1000)
            except KeyboardInterrupt:
                logging.info("接收到退出指令，正在关闭...")
                self.stop()

if __name__ == "__main__":
    downloader = DailyReportDownloader()
    downloader.execute_workflow()