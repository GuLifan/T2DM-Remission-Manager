"""
模块名称：audit.py
所属层级：数据模型层（models）
功能说明：系统审计日志。记录登录、登出、登录失败、建档、事件写入、依据检索、
          导出与管理操作，用于排查与责任追溯。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """系统审计日志（只增不改）。"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 操作者：未登录场景（如登录失败）允许为空
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # 动作标识：login / logout / login_failed / patient_create / event_write / evidence_search / export
    action: Mapped[str] = mapped_column(String(32), index=True)
    # 作用对象类型与主键（如 patient/12）
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 细节（JSON 字符串）：不得写入患者完整病历内容
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
