"""
模块名称：env.py
所属层级：数据库迁移（migrations）
功能说明：Alembic 运行环境。连接串与目标元数据都从应用代码读取，
          保证"迁移脚本"与"ORM 模型"始终指向同一个数据库与同一份表定义。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.models import Base

# Alembic 配置对象（读取 alembic.ini）
config = context.config

# 日志配置：沿用 alembic.ini 中的定义
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据：所有 ORM 模型的表定义
target_metadata = Base.metadata

# 连接串由应用配置决定（开发态 data/runtime，便携版用户数据目录）
settings = get_settings()
# 目录必须先存在，否则 SQLite 会报 "unable to open database file"
settings.ensure_dirs()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 便于人工核对生成的 SQL
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # 类型变化也纳入比对，避免结构漂移
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
