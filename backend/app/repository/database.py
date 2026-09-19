"""
模块名称：database.py
所属层级：数据访问层（repository）
功能说明：创建 SQLite 引擎与会话工厂，并提供 FastAPI 依赖。

关键约定：
    - 启用 WAL 日志模式：单机读写并存时更稳。
    - 启用外键约束：SQLite 默认关闭，必须显式打开（事件必须挂在真实患者与账号上）。
    - 不使用 Base.metadata.create_all 改结构；表结构一律由 Alembic 迁移管理。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
# 首次导入时确保数据目录存在，避免连接 SQLite 时目录缺失
settings.ensure_dirs()

# SQLite 引擎：check_same_thread=False 允许多线程共享（FastAPI 线程池中使用）
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """每次建立物理连接时配置 SQLite 行为。

    为什么必须做：外键约束在 SQLite 中默认关闭，若不显式打开，
    events.patient_id 指向不存在的患者也不会报错，会破坏可追溯性。
    """
    cursor = dbapi_connection.cursor()
    # WAL：读写并存时减少锁等待
    cursor.execute("PRAGMA journal_mode=WAL")
    # 外键约束：保证事件必须挂在真实患者与账号上
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 会话工厂：autoflush=False 便于显式控制落库时机；expire_on_commit=False 便于提交后继续读属性
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：提供请求级数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
