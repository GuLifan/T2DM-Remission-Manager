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

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
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
    # 数据库沿用历史字段名；医生界面统一显示“住院号”
    medical_record_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 当前科室必填；联系方式选填，不强制医生编造缺失信息
    department: Mapped[str] = mapped_column(String(128), default="内分泌科")
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 创建者本批只记录不执行业务权限；第三批再启用账号隔离守卫
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # 批量导入患者必须先完善资料；手工建档默认已完善
    profile_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    # 测试患者标记：测试跳转与模拟日期只能作用于此类患者
    is_test_patient: Mapped[bool] = mapped_column(Boolean, default=False)

    # 最新身高、体重与 BMI 快照；第二批不建趋势表，不参与临床准入
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)

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
