"""
模块名称：event.py
所属层级：数据模型层（models）
功能说明：临床事件流水（只增不改）。每一次医生决策或系统自动动作都留下一条事件，
          用于回答"谁、在什么时候、基于什么输入、得出了什么结论、把状态从哪带到哪"。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Event(Base):
    """临床事件流水（只增不改）。"""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 所属患者
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    # 操作者：医生决策事件记医生账号；系统自动事件记系统账号（见 repository/system_user.py）
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 事件来源：doctor（医生操作）/ system（系统自动，如自动进入观察期）
    source: Mapped[str] = mapped_column(String(16), default="doctor")
    # 触发的规则 ID（工程标识，前台不显示）
    rule_id: Mapped[str] = mapped_column(String(32), index=True)
    # 状态迁移：源状态与目标状态（前台只显示中文名称）
    source_state: Mapped[str] = mapped_column(String(8))
    target_state: Mapped[str] = mapped_column(String(8))
    # 输出模板 ID 与当时展示给医生的自然语言结论
    template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output_text: Mapped[str] = mapped_column(Text)
    # 本次输入快照（JSON 字符串）：包含被忽略的分支与原因，保证可追溯
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 事件编号（幂等用）：客户端重复提交时用于识别同一次操作
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
