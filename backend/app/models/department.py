"""
模块名称：department.py
所属层级：数据模型层（models）
功能说明：可维护的科室参考字典；第二批迁移种入 Lifan 已审定的 69 个科室。

修改历史：
    - 2026-09-24  v1.0  第二轮第二批新增
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Department(Base):
    """科室字典。排序号固定保存，避免每个客户端各自实现拼音排序。"""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
