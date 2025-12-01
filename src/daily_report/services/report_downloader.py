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

from src.config import config
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
            # 【核心修改】 防止浏览器关闭
            # 我们移除了 self.stop()，并添加了 input() 阻塞
            print("\n" + "="*50)
            print(" ✅ 自动化脚本运行完毕！")
            
            # 这行代码会“卡住”程序，直到你按下回车
            input() 
            
            logging.info("正在清理资源并退出...")
            self.stop()

if __name__ == "__main__":
    downloader = DailyReportDownloader()
    downloader.execute_workflow()