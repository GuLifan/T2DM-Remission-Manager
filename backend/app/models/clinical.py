"""
模块名称：clinical.py
所属层级：数据模型层（models）
功能说明：临床服务层的输入与输出模型（6 个流程单元）。

与 `schemas.py` 的区别：`schemas.py` 是接口层的对外契约；本文件是**服务层契约**，
字段沿用最小字段映射的 F 编号，便于与甲方实现表逐条对照（追踪键：F001–F056）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ===================== 事件1：60秒缓解预评估 =====================


class PreAssessmentInput(BaseModel):
    """预评估输入：核心五问（F001–F005）+ 机会信息（F006–F010）+ 前置事项（F012）。"""

    # 客户端请求标识：用于幂等（同一 request_id 不产生重复事件）
    request_id: str | None = None
    f001_t2dm_established: str = Field(description="成人T2DM判断是否基本成立（是/否/待确认）")
    f002_acute_unsafe: str = Field(description="当前是否存在急性不安全状态")
    f003_type_doubt: str = Field(description="是否存在足以影响下一步的明显分型疑点")
    f004_treatment_context_sufficient: str = Field(description="当前治疗背景是否足以判断")
    f005_refused: str = Field(description="患者是否明确拒绝进一步了解或参与")
    # 机会信息：缺项不阻断（B-03 红线）
    f006_duration: str | None = None
    f006_duration_years: int | None = Field(default=None, ge=0, le=60)
    f006_duration_months: int = Field(default=0, ge=0, le=11)
    f007_bmi_hint: str | None = None
    # 第二批把身高/体重前移到预评估；仍只作记录，不参与准入判断
    f018_weight: float | None = Field(default=None, gt=0, le=500)
    f019_height: float | None = Field(default=None, ge=50, le=250)
    f008_glucose_status: str | None = None
    f009_insulin: str | None = None
    f010_demands: list[str] = Field(default_factory=list)
    f012_pre_tasks: str | None = None


class PreAssessmentResult(BaseModel):
    """预评估结果：三类主结论之一。"""

    conclusion: str
    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    hold_reasons: list[str] = Field(default_factory=list)
    return_hint: str | None = None


class AcuteStabilizedInput(BaseModel):
    """急性安全暂缓后医生确认已稳定化 → 快速建档（补录事件2必需字段，不重复预评估）。

    依据：锁定稿§11 返回路径；`_SPEC/06` Q-06 裁决。
    """

    request_id: str | None = None
    stage_goal: str = Field(min_length=1, description="一个主要阶段目标")
    interventions: list[str] = Field(description="干预组合（多选，至少一项）")
    next_review_date: date | None = None


# ===================== 事件2：完整评估并形成主动管理计划 =====================


class FullAssessmentInput(BaseModel):
    """完整评估输入：六维度评估资料（F013–F025）+ 一次性计划决策（F026–F029）。"""

    request_id: str | None = None
    f013_diagnosis_basis: str | None = None
    f014_hba1c: float | None = Field(default=None, ge=0, le=30)
    f016_drugs: str | None = None
    f017_major_adjustment: str | None = None
    f018_weight: float | None = Field(default=None, gt=0, le=500)
    f019_height: float | None = Field(default=None, ge=50, le=250)
    f020_waist: str | None = None
    f021_weight_change: str | None = None
    f022_cpeptide: str | None = None
    f023_constraints: list[str] = Field(default_factory=list)
    f024_willing: str | None = None
    f025_review_accept: str | None = None
    # 一次性计划决策
    f026_start: str = Field(description="启动 / 暂缓补充关键资料 / 当前不启动")
    f027_stage: str | None = None
    f028_stage_goal: str | None = None
    f029_interventions: list[str] = Field(default_factory=list)
    next_review_date: date | None = None
    f012_pre_tasks: str | None = None
    not_start_reason: str | None = None


class FullAssessmentResult(BaseModel):
    """完整评估结果。"""

    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    stage: str | None = None
    stage_goal: str | None = None
    interventions: str | None = None
    next_review_date: date | None = None


# ===================== 事件3：阶段复评与治疗调整 =====================


class PhaseReviewInput(BaseModel):
    """阶段复评输入：复评最少输入（F030–F033）+ 动作（F034–F036）+ 分支事实。"""

    request_id: str | None = None
    # 第三批允许在正式复评时更新最新身高/体重；空值表示沿用患者现有快照
    f018_weight: float | None = Field(default=None, gt=0, le=500)
    f019_height: float | None = Field(default=None, ge=50, le=250)
    f030_safety_issues: list[str] = Field(default_factory=list)
    f031_stage_indicator: str | None = None
    f032_treatment_changes: list[str] = Field(default_factory=list)
    f033_executable: str | None = None
    f034_action: str = Field(description="继续 / 调整 / 转换阶段 / 结束主动管理")
    new_stage: str | None = None
    stage_goal: str | None = None
    adjustment_summary: str | None = None
    next_review_date: date | None = None
    end_reason: str | None = None
    # 治疗变化分支事实
    f035_stop_last_med: bool = False
    f036_stop_date: date | None = None
    f053_has_drug: bool = False
    f054_purpose: str | None = None
    glucose_non_diabetic: bool = False
    f056_uncontrolled: bool = False
    emergency_note: str | None = None


class PhaseReviewResult(BaseModel):
    """阶段复评结果。"""

    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    stage: str | None = None
    stage_goal: str | None = None
    next_review_date: date | None = None
    entered_observation: bool = False
    earliest_judge_date: date | None = None
    # 被更高优先级分支覆盖的分支说明（必须返回给前台，禁止静默丢弃）
    ignored_branches: list[str] = Field(default_factory=list)


# ===================== 单元4：缓解观察期（系统自动状态）=====================


class ObservationStatus(BaseModel):
    """观察期状态（只读展示；到期判定由系统计算，医生不需要点击"进入观察期"）。"""

    stage: str
    last_med_stop_date: date | None = None
    lifestyle_start_date: date | None = None
    surgery_date: date | None = None
    earliest_judge_date: date | None = None
    due: bool = False
    rule_id: str
    template_id: str
    output_text: str


class MedicationRestartInput(BaseModel):
    """观察期重新用药（退出观察期）输入。"""

    request_id: str | None = None
    f037_reason: str = Field(description="因高血糖 / 因器官获益 / 因体重获益 / 其他")
    target_stage: str = Field(description="返回事件3后的管理阶段（医生选择）")


class MedicationRestartResult(BaseModel):
    """观察期重新用药结果。"""

    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    stage: str
    stage_goal: str | None = None


# ===================== 事件4：缓解判定 =====================


class RemissionJudgeInput(BaseModel):
    """缓解判定输入：诊断可信、停药时间、指标与独立复核。"""

    request_id: str | None = None
    f041_diagnosis_credible: str = Field(description="既往T2DM诊断是否可信（是/否/待复核）")
    f042_drug_free_3m: str = Field(description="已停用全部降糖作用药物至少3个月（是/否/待核对）")
    f043_hba1c_reliable: str = Field(description="HbA1c结果是否可可靠解释（是/否/待复核）")
    f014_hba1c: float | None = Field(default=None, ge=0, le=30)
    f044_fpg: float | None = Field(default=None, ge=0, le=50)
    f045_ea1c: float | None = Field(default=None, ge=0, le=30)
    f046_independent_review: str | None = None
    # 返回主动管理时由医生选择的阶段（仅 E4-B02 / E4-B06 需要；缺失时接口只返回提示、不落库）
    target_stage: str | None = None


class RemissionConfirmInput(BaseModel):
    """缓解确认输入（E4-B04 / E4-B05）。"""

    request_id: str | None = None
    f048_confirm: str = Field(description="确认 / 暂不确认")
    f012_pre_tasks: str | None = Field(default=None, description="暂不确认时的定向复核项目")


class RemissionJudgeResult(BaseModel):
    """缓解判定结果。

    blocked：是否被客观条件阻断（未到期 / 仍用药）。
    objective_met：客观条件是否满足（满足也不等于缓解——必须由医生确认）。

    target_state 约定：为空字符串表示"返回哪个管理阶段由医生选择"，
    此时 `needs_target_stage=True`，接口层必须先要求医生补选阶段再落库。
    """

    blocked: bool
    objective_met: bool
    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    doctor_confirmation_required: bool = False
    needs_target_stage: bool = False
    needs_followup_tasks: bool = False


# ===================== 事件5：缓解后复评 =====================


class PostRemissionInput(BaseModel):
    """缓解后复评输入。"""

    request_id: str | None = None
    f049_glucose: str | None = None
    f050_med_status: str = Field(description="未使用 / 因高血糖 / 因器官获益 / 因体重获益")
    f051_risk_triggers: list[str] = Field(default_factory=list)
    f055_glucose_state: str = Field(description="低于糖尿病诊断阈值 / 达到糖尿病范围 / 暂不能可靠解释")
    target_stage: str | None = None
    next_review_date: date | None = None
    # 是否出现"新分型证据或重大临床变化"：缓解终止时据此决定返回完整评估（ST20）还是阶段复评
    has_new_type_evidence: bool = False


class PostRemissionResult(BaseModel):
    """缓解后复评结果。"""

    rule_id: str
    template_id: str
    output_text: str
    target_state: str
    stage: str | None = None
    next_review_date: date | None = None
