import logging
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright
from typing import Optional
from packages.web_automation.src.config import BrowserConfig

class BrowserManager:
    """
    [Infrastructure Adapter]
    负责 Playwright 引擎的生命周期管理。
    实现了单例模式，并封装了 '去安全化' 的启动参数。
    """
    _instance = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: BrowserConfig):
        """
        :param config: Pydantic定义的 BrowserConfig 对象
        """
        self.config = config

    def start_browser(self) -> Page:
        """启动浏览器并返回一个新的 Page 对象"""
        
        # 1. 启动 Playwright 引擎
        if self._playwright is None:
            logging.info("正在启动 Playwright 引擎...")
            self._playwright = sync_playwright().start()

        # 2. 启动浏览器实例 (注入核心反检测参数)
        if self._browser is None:
            logging.info(f"正在启动浏览器 (Headless: {self.config.headless})...")
            
            # 【核心修改】 去安全化参数 (Anti-Detection)
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled', # 隐藏自动化特征
                '--safebrowsing-disable-download-protection',    # 禁用下载保护
                '--safebrowsing-disable-extension-blacklist',
                '--disable-infobars',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]

            self._browser = self._playwright.chromium.launch(
                channel="chrome",  # 优先使用本地 Chrome，比 Chromium 更稳定
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=launch_args,
                timeout=self.config.timeout
            )

        # 3. 创建上下文 (Context)
        if self._context is None:
            # 【核心修改】 在上下文层面允许下载，并设置视口
            self._context = self._browser.new_context(
                viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
                accept_downloads=True,  # 允许自动下载
                no_viewport=True        # 配合 maximized 参数
            )
        
        # 4. 创建页面
        page = self._context.new_page()
        # 设置默认超时
        page.set_default_timeout(self.config.timeout)
        
        logging.info("浏览器页面已就绪。")
        return page

    def stop_browser(self):
        """释放所有浏览器资源"""
        try:
            if self._context:
                self._context.close()
                self._context = None
            
            if self._browser:
                self._browser.close()
                self._browser = None
                
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
                
            logging.info("浏览器资源已安全释放。")
        except Exception as e:
            logging.error(f"关闭浏览器资源时出错: {e}")