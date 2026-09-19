"""
模块名称：meta.py
所属层级：数据模型层（models）
功能说明：应用元数据表（键值），用于记录数据库初始化时间、当前 schema 版本等。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppMeta(Base):
    """应用元数据（键值表）。"""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
