# 文件路径: src/config.py
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

# --- 1. 定义路径 ---
# 自动定位项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- 2. 定义 YAML 读取器 (这是 Pydantic 支持 YAML 的标准写法) --- 
class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """自定义源：让 Pydantic 能够读取 config/config.yaml"""
    def get_field_value(self, field: Field, field_name: str) -> tuple[Any, str, bool]: # type: ignore
        return super().get_field_value(field, field_name)

    def __call__(self) -> Dict[str, Any]:
        # 尝试读取 config.yaml
        config_file = PROJECT_ROOT / "config" / "anomaly_monitor_config.yaml"
        if not config_file.exists():
            return {}
        
        with open(config_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

# --- 3. 定义数据模型 (The "What") ---
# 对应 YAML 中的 browser: 节点
class BrowserConfig(BaseModel):
    headless: bool = False
    timeout: int = 30000
    slow_mo: int = 50

# 对应 YAML 中的 path: 节点
class PathConfig(BaseModel):
    data_raw_dir: str = "data/raw"
    data_input_dir: str = "data/input"
    log_dir: str = "logs"
    # 如果 YAML 里没有，这里可以写默认值

# 对应 YAML 中的 daily_report: 节点
class DailyReportConfig(BaseModel):
    portal_url: str = ""
    inputs: Dict[str, Any] = {} # 复杂结构可以先用 Dict，或者继续定义子 Model

# --- 4. 主配置类 (整合所有) ---
class AppConfig(BaseSettings):
    # 嵌套模型
    browser: BrowserConfig = BrowserConfig()
    path: PathConfig = PathConfig()
    daily_report: DailyReportConfig = DailyReportConfig()
    
    # 顶层配置 (直接从环境变量读取)
    # Field(alias=...) 允许你用不同的名字映射环境变量
    mes_username: Optional[str] = Field(default=None, alias="MES_USERNAME")
    mes_password: Optional[str] = Field(default=None, alias="MES_PASSWORD")
    
    # 全局快捷属性 (Computed Properties)
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    # 配置 Pydantic 的行为
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", # 同时也读取 .env
        env_file_encoding='utf-8',
        extra='ignore' # 忽略 YAML 里多余的未知字段，不报错
    )

    # 注册我们刚才写的 YAML 读取器
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,     # 优先级 1: 环境变量
            dotenv_settings,  # 优先级 2: .env 文件
            YamlConfigSettingsSource(settings_cls), # 优先级 3: config.yaml
        )

# --- 5. 实例化 (单例模式) ---
# 在这里直接实例化，其他文件 import 这个 config 对象即可
try:
    config = AppConfig()
except Exception as e:
    # 如果配置校验失败（比如必填项缺失），启动时就会直接报错，避免运行时才崩溃
    print(f"❌ 严重错误: 配置加载失败! {e}")
    raise