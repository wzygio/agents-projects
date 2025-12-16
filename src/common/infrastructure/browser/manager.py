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
        if self._playwright is None:
            logging.info("正在启动 Playwright 引擎...")
            self._playwright = sync_playwright().start()

        if self._browser is None:
            headless_mode = getattr(config, 'headless', False) 
            slow_mo = getattr(config, 'slow_mo', 50)
            
            logging.info(f"正在启动浏览器 (Headless: {headless_mode})...")
            
            # 【核心修改】 注入去安全化参数
            # 这些参数组合在一起，可以最大程度避免 "保留/放弃" 的弹窗
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--safebrowsing-disable-download-protection',  # 禁用下载保护
                '--safebrowsing-disable-extension-blacklist',
                '--disable-infobars',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]

            self._browser = self._playwright.chromium.launch(
                channel="msedge", 
                headless=headless_mode, 
                slow_mo=slow_mo,
                args=launch_args 
            )

        if self._context is None:
            # 【核心修改】 在上下文层面也允许下载
            self._context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True  # 这一行至关重要
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