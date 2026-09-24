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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ===================== 账号与登录 =====================


class AuthStatusOut(BaseModel):
    """登录前置状态：是否还没有任何账号（首次运行需要引导创建）。"""

    needs_bootstrap: bool


class BootstrapIn(BaseModel):
    """创建首个正式管理员账号的请求。"""

    username: str = Field(min_length=3, max_length=64, description="登录名")
    display_name: str = Field(min_length=1, max_length=64, description="界面显示姓名")
    password: str = Field(min_length=8, max_length=128, description="登录密码（至少 8 位）")


class RegisterIn(BaseModel):
    """开放注册请求；注册成功后不自动登录。"""

    username: str = Field(min_length=3, max_length=64, description="登录名")
    display_name: str = Field(min_length=1, max_length=64, description="医师姓名")
    department: str | None = Field(default=None, max_length=128, description="所属科室（选填）")
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> RegisterIn:
        """两次密码必须一致，避免只在前端校验而被接口绕过。"""
        if self.password != self.password_confirm:
            raise ValueError("两次输入的密码不一致。")
        return self


class RegisterOut(BaseModel):
    """开放注册结果。"""

    message: str


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
    department: str | None = None
    role: str
    is_test_account: bool = False
    simulated_date: date | None = None


class AssignableDoctorOut(BaseModel):
    """管理员转移患者归属时可选择的启用医生。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    department: str | None = None


class LoginOut(BaseModel):
    """登录成功响应。"""

    token: str
    expires_at: int = Field(description="令牌过期时间（Unix 秒）")
    user: UserOut


# ===================== 患者档案 =====================


class PatientCreateIn(BaseModel):
    """手工建档请求；出生日期的日固定为 1，界面只录入年月。"""

    name: str = Field(min_length=1, max_length=64)
    gender: str = Field(pattern="^[男女]$", description="男 / 女")
    birth_date: date
    medical_record_no: str = Field(min_length=1, max_length=64, description="住院号（唯一）")
    department: str = Field(default="内分泌科", min_length=1, max_length=128, description="当前科室")
    contact_phone: str | None = Field(default=None, max_length=64, description="联系方式（选填）")

    @field_validator("birth_date")
    @classmethod
    def birth_month_only(cls, value: date) -> date:
        """出生信息只精确到月，接口统一把日固定为 1。"""
        return value.replace(day=1)


class PatientProfileUpdateIn(PatientCreateIn):
    """完善患者资料；住院号仍需保持全局唯一。"""


class OwnershipTransferIn(BaseModel):
    """管理员转移患者当前责任归属的请求。"""

    owner_id: int = Field(gt=0, description="新的责任医生账号 ID")


class PatientOut(BaseModel):
    """患者档案响应。current_state 为内部状态代码，仅供前端路由使用，**不得直接展示给医生**。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gender: str
    birth_date: date
    medical_record_no: str
    department: str
    contact_phone: str | None = None
    created_by: int | None = None
    owner_id: int | None = None
    owner_display_name: str | None = None
    can_edit: bool = False
    profile_complete: bool = True
    is_test_patient: bool = False
    height_cm: float | None = None
    weight_kg: float | None = None
    bmi: float | None = None
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
    updated_at: datetime


class ImportRowResult(BaseModel):
    """批量导入单行结果。"""

    row: int
    medical_record_no: str | None = None
    status: str = Field(description="success / skipped / failed")
    message: str


class PatientImportOut(BaseModel):
    """批量导入汇总与逐行结果。"""

    success_count: int
    skipped_count: int
    failed_count: int
    rows: list[ImportRowResult]


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
    simulated_date: date | None = None
    created_at: datetime


class EventPage(BaseModel):
    """事件分页响应（避免历史很长时一次性返回全部记录）。"""

    total: int
    items: list[EventOut]


# ===================== 测试模式（仅开发验收使用） =====================


class TestContextOut(BaseModel):
    """当前账号的测试能力与日期上下文。"""

    test_mode_enabled: bool
    can_use_test_tools: bool
    real_date: date
    effective_date: date
    simulated_date: date | None = None


class SimulatedDateIn(BaseModel):
    """设置或清除账号级模拟日期；空值表示恢复真实日期。"""

    simulated_date: date | None = None


class DebugJumpIn(BaseModel):
    """测试患者状态跳转请求。"""

    target_state: str = Field(min_length=4, max_length=4)
    request_id: str | None = Field(default=None, max_length=64)


# ===================== 医学依据检索 =====================


class EvidenceMaterialStatusOut(BaseModel):
    """一份预期材料的本地索引状态。"""

    source_key: str
    title: str
    source_type: str
    ready: bool
    page_count: int | None = None
    text_page_count: int | None = None
    chunk_count: int = 0
    imported_at: datetime | None = None


class EvidenceStatusOut(BaseModel):
    """依据库总体状态，用于区分未导入和查询无命中。"""

    expected_count: int
    indexed_count: int
    searchable: bool
    last_imported_at: datetime | None = None
    materials: list[EvidenceMaterialStatusOut]


class EvidenceSearchItemOut(BaseModel):
    """一条纯文本依据命中；不得包含 HTML 或本机绝对路径。"""

    evidence_id: int
    source_key: str
    title: str
    source_type: str
    page_no: int | None = None
    section: str | None = None
    snippet: str


class EvidenceSearchOut(BaseModel):
    """医学依据检索响应。"""

    query: str
    search_mode: str
    materials_indexed: int
    total: int
    returned: int
    items: list[EvidenceSearchItemOut]
