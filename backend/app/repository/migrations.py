"""
模块名称：migrations.py
所属层级：数据访问层（repository）
功能说明：在应用启动时执行 Alembic 迁移（首次运行自动建库）。

为什么不用 create_all：直接按模型建表无法演进既有数据库（新增列不会补上），
临床数据不允许丢失，必须走可追踪的迁移脚本（见 `_SPEC/07` 第五节）。

主要函数：
    - run_migrations()：把数据库升级到最新结构。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR, get_settings

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """把数据库结构升级到最新版本（幂等，可重复调用）。"""
    settings = get_settings()
    # 数据库目录必须先存在，否则 Alembic 连接会失败
    settings.ensure_dirs()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # 显式传入连接串：避免 alembic.ini 中硬编码路径，便于便携版切换数据目录
    config.set_main_option("sqlalchemy.url", settings.database_url)
    logger.info("执行数据库迁移：%s", settings.db_path)
    command.upgrade(config, "head")
