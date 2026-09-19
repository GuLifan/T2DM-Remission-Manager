"""
模块名称：patient.py
所属层级：数据模型层（models）
功能说明：患者档案模型，承载当前状态、阶段与观察期时间锚点。
          字段含义与 `_SPEC/04_字段与输出模板` 的 F 编号对应关系见字段注释。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Patient(Base):
    """患者档案（最小集：姓名、性别、出生日期、病历号 + 流程状态）。"""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 基本信息
    name: Mapped[str] = mapped_column(String(64))
    gender: Mapped[str] = mapped_column(String(8))
    birth_date: Mapped[date] = mapped_column(Date)
    # 病历号唯一：避免同一患者被重复建档
    medical_record_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 当前流程状态（ST00–ST99）；前台只显示中文名称，不显示代码
    current_state: Mapped[str] = mapped_column(String(8), default="ST00", index=True)
    # 当前管理阶段（血糖稳定 / 缓解诱导）与阶段目标、干预组合
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage_goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interventions: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 下次正式复评日期（由服务层按默认 12 周或医生指定生成）
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 观察期时间锚点：停药日期（F036）、生活方式开始（F038）、代谢手术（F039）
    last_med_stop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lifestyle_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    surgery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 最早可判定日期（F040，系统计算，不允许医生手工修改）
    earliest_judge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 缓解确认日期（F052，医生确认形成结论时写入）
    remission_confirmed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 最近一次医生确认的用药状态：是否有降糖作用药物（F053）与主要用途（F054）
    has_glucose_lowering_drug: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    drug_purpose: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 建档与更新时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
