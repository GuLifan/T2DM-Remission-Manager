"""
模块名称：base.py
所属层级：数据模型层（models）
功能说明：定义 ORM 基类。所有模型继承 Base，Alembic 依据 Base.metadata 推断表结构。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """全部 ORM 模型的基类。"""
