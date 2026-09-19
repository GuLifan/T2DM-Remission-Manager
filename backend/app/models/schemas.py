"""
模块名称：schemas.py
所属层级：数据模型层（models）
功能说明：接口层使用的 Pydantic 请求/响应模式。

设计约定：
    - 响应模式只暴露前台需要的内容；**不返回密码哈希、内部状态代码等工程字段给医生界面**。
    - 日期一律使用 ISO 字符串（date 由 Pydantic 自动转换）。
    - 字段命名使用英文标识符，展示文案由前端负责（前台只出现自然语言）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现（账号、患者、事件、审计相关模式）
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# ===================== 账号与登录 =====================


class AuthStatusOut(BaseModel):
    """登录前置状态：是否还没有任何账号（首次运行需要引导创建）。"""

    needs_bootstrap: bool


class BootstrapIn(BaseModel):
    """创建首个医生账号的请求。"""

    username: str = Field(min_length=3, max_length=64, description="登录名")
    display_name: str = Field(min_length=1, max_length=64, description="界面显示姓名")
    password: str = Field(min_length=8, max_length=128, description="登录密码（至少 8 位）")


class LoginIn(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """账号信息（不含任何凭据字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str


class LoginOut(BaseModel):
    """登录成功响应。"""

    token: str
    expires_at: int = Field(description="令牌过期时间（Unix 秒）")
    user: UserOut


# ===================== 患者档案 =====================


class PatientCreateIn(BaseModel):
    """建档请求（最小集：姓名、性别、出生日期、病历号）。"""

    name: str = Field(min_length=1, max_length=64)
    gender: str = Field(pattern="^[男女]$", description="男 / 女")
    birth_date: date
    medical_record_no: str = Field(min_length=1, max_length=64, description="病历号（唯一）")


class PatientOut(BaseModel):
    """患者档案响应。current_state 为内部状态代码，仅供前端路由使用，**不得直接展示给医生**。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gender: str
    birth_date: date
    medical_record_no: str
    current_state: str
    stage: str | None = None
    stage_goal: str | None = None
    interventions: str | None = None
    next_review_date: date | None = None
    last_med_stop_date: date | None = None
    lifestyle_start_date: date | None = None
    surgery_date: date | None = None
    earliest_judge_date: date | None = None
    remission_confirmed_date: date | None = None
    has_glucose_lowering_drug: bool | None = None
    drug_purpose: str | None = None
    created_at: datetime


# ===================== 临床事件流水 =====================


class EventOut(BaseModel):
    """事件流水响应（只读，事件只增不改）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: str
    source: str
    source_state: str
    target_state: str
    template_id: str | None = None
    output_text: str
    operator_id: int
    created_at: datetime


class EventPage(BaseModel):
    """事件分页响应（避免历史很长时一次性返回全部记录）。"""

    total: int
    items: list[EventOut]
