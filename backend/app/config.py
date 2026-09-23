"""
模块名称：config.py
所属层级：应用配置层（app）
功能说明：集中管理运行配置（数据目录、数据库路径、服务端口、会话时长、日志级别）。
          开发态与便携版共用同一套代码，差异只在"数据目录"与"静态资源位置"。

主要对象：
    - Settings：配置模型（可用 ETMMS_ 前缀的环境变量覆盖）。
    - get_settings()：带缓存的配置获取入口。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 后端目录：<项目根>/backend（本文件位于 <项目根>/backend/app/config.py）
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 项目根目录：便于开发态定位 data/、frontend/dist 等
PROJECT_ROOT = BACKEND_DIR.parent


def default_data_dir() -> Path:
    """返回默认数据目录。

    为什么需要区分运行形态：便携版可能被放在只读位置（如 Program Files），
    因此打包运行（sys.frozen）时把数据库与日志写到用户数据目录；
    开发态则写工作区 `data/runtime`，便于查看与清理。
    """
    if getattr(sys, "frozen", False):
        # 便携版：%LOCALAPPDATA%\ETMMS
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / "ETMMS"
    # 开发态：<项目根>/data/runtime
    return PROJECT_ROOT / "data" / "runtime"


class Settings(BaseSettings):
    """应用配置。

    所有字段都可以用环境变量覆盖，前缀 `ETMMS_`，例如：
        ETMMS_PORT=9000
        ETMMS_DATA_DIR=D:\\tmp\\etmms
    """

    model_config = SettingsConfigDict(env_prefix="ETMMS_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    # 默认端口 8088：8080 已被本机其他开发任务占用（2026-09-20 Lifan 指定）
    port: int = 8088
    # 会话有效期（小时）；本地单机使用，默认 8 小时覆盖一个门诊班次
    session_hours: int = 8
    log_level: str = "INFO"
    # 测试后门总开关：默认关闭，交付环境不得开启
    test_mode: bool = False
    # 数据目录：数据库与日志的落盘位置
    data_dir: Path = Field(default_factory=default_data_dir)
    db_filename: str = "etmms.db"

    @property
    def db_path(self) -> Path:
        """数据库文件的绝对路径。"""
        return self.data_dir / self.db_filename

    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串（SQLite）。"""
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def frontend_dist_dir(self) -> Path:
        """前端构建产物目录（开发态与打包态的两种可能位置）。"""
        # 开发态：<项目根>/frontend/dist
        dev_path = PROJECT_ROOT / "frontend" / "dist"
        if dev_path.exists():
            return dev_path
        # 打包态：静态资源被复制到 app/static
        return Path(__file__).resolve().parent / "static"

    def ensure_dirs(self) -> None:
        """确保数据目录存在（首次运行自动创建）。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置（带缓存，避免重复读取环境变量）。"""
    return Settings()
