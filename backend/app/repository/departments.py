"""
模块名称：departments.py
所属层级：数据访问层（repository）
功能说明：科室参考字典查询；排序由数据库种子数据统一维护。

修改历史：
    - 2026-09-24  v1.0  第二轮第二批新增
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department


def list_active(db: Session) -> list[Department]:
    """返回启用科室，按审定顺序排列。"""
    statement = select(Department).where(Department.is_active.is_(True)).order_by(Department.sort_order)
    return list(db.scalars(statement).all())


def is_active_name(db: Session, name: str) -> bool:
    """判断科室名是否存在且启用，供手工建档与批量导入共用。"""
    statement = select(Department.id).where(Department.name == name, Department.is_active.is_(True))
    return db.scalar(statement) is not None
