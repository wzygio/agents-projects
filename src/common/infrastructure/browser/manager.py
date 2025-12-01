# 文件路径: src/common/infrastructure/browser/manager.py
import logging
from playwright.sync_api import sync_playwright, Browser, Page
from src.config import config  # 假设 config 中有 headless, timeout 等配置

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
            
            # 【核心修改】
            # 原代码: self._browser = self._playwright.chromium.launch(
            # 修改为: 指定 channel="msedge"
            self._browser = self._playwright.chromium.launch(
                channel="msedge",  # <--- 加上这一行，使用电脑自带的 Edge
                headless=headless_mode, 
                slow_mo=slow_mo,
                args=['--start-maximized'] 
            )

        if self._context is None:
            # 创建上下文，设置视口大小为0表示自适应
            self._context = self._browser.new_context(viewport={'width': 1920, 'height': 1080})
        
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