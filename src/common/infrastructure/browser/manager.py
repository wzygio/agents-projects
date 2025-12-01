# 文件路径: src/common/infrastructure/browser/manager.py
import logging
from playwright.sync_api import sync_playwright, Page
from src.config import config

class BrowserManager:
    _instance = None
    _playwright = None
    _browser = None
    _context = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def start_browser(self) -> Page:
        """
        启动浏览器并返回一个新的页面对象
        """
        if self._playwright is None:
            logging.info("正在启动 Playwright 引擎...")
            self._playwright = sync_playwright().start()

        if self._browser is None:
            headless_mode = getattr(config, 'headless', False) 
            slow_mo = getattr(config, 'slow_mo', 50)
            
            logging.info(f"正在启动浏览器 (Headless: {headless_mode})...")
            
            # 【核心修改 1】 添加一系列参数，禁用浏览器的安全检查
            # 这些参数能解决 .crdownload 卡住和无法下载的问题
            launch_args = [
                '--start-maximized',                      # 最大化
                '--disable-blink-features=AutomationControlled', # 试图隐藏机器人特征
                '--safebrowsing-disable-download-protection',    # 【关键】禁用下载保护
                '--safebrowsing-disable-extension-blacklist',    # 禁用扩展黑名单
                '--disable-infobars',                            # 隐藏"受自动测试软件控制"条
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]

            self._browser = self._playwright.chromium.launch(
                channel="msedge",  # 使用 Edge
                headless=headless_mode, 
                slow_mo=slow_mo,
                args=launch_args,  # 注入参数
                downloads_path="./downloads_temp" # 指定 Playwright 内部缓存路径(可选)
            )

        if self._context is None:
            # 【核心修改 2】 在创建上下文时，显式允许下载
            self._context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True  # 【关键】告诉上下文：允许下载文件
            )
        
        page = self._context.new_page()
        logging.info("浏览器页面已创建。")
        return page

    def stop_browser(self):
        """
        关闭浏览器和引擎
        """
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logging.info("浏览器资源已释放。")