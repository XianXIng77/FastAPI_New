from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """统一读取配置；环境变量优先于项目根目录的 .env。"""

    database_url: str = Field(min_length=1)
    db_pool_size: int = Field(default=10, ge=0)
    db_max_overflow: int = Field(default=20, ge=-1)
    db_pool_pre_ping: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
