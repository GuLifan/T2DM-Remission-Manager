"""批准的v0.3输入契约（F057—F063及日期、药物、确认版本）。

与旧clinical.py隔离，直到服务/前端整体接入后才由新接口使用。
严格拒绝未知字段；缺失/待确认不转换成“否”；旧版请求每次录入体重；v0.4允许来源引用，身高仍由共享守卫锁定。
医学判定仍由服务与医生确认，模型仅验证结构和明显矛盾，不自动诊断或停药。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.models.clinical import _reject_exclusive_multiselect_conflict

YesNo = Literal["是", "否"]
Stage = Literal["血糖稳定", "缓解诱导"]
Purpose = Literal["高血糖治疗", "器官获益", "体重获益", "其他"]
Intervention = Literal["结构化生活方式", "代谢手术", "其他"]


class V03Request(BaseModel):
    """客户端必须带幂等键和患者版本；正式接口接入前不接受此模型写库。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    clinical_contract_version: Literal["v0.3"] = "v0.3"
    request_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=0)
    input_schema_version: Literal["v0.3", "v0.4"] = "v0.3"
    regimen_source_id: int | None = Field(default=None, gt=0)
    medication_reconciliation_confirmed: StrictBool = False
    medication_review_complete: StrictBool = False
    current_medication_confirmation: Literal["是", "否", "待核实"] | None = None
    # 当前方案移除是本次事实核对，不是删除历史或推断实际停药。
    removed_medication_ids: list[str] = Field(default_factory=list, max_length=200)
    no_current_medications_confirmed: StrictBool = False

    @field_validator("removed_medication_ids")
    @classmethod
    def validate_removed_medication_ids(cls, value):
        if len(value) != len(set(value)) or any(not item or len(item) > 128 for item in value):
            raise ValueError("移除药物标识必须有效且不得重复")
        return value


class ClinicalExamination(BaseModel):
    """资料检查支持多种指标；只有旧ExaminationRecord的三类可进入E4判定。"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["HbA1c", "FPG", "指尖血糖", "CGM摘要", "CGM估算HbA1c", "其他可靠近期资料"]
    value: float | None = Field(default=None, gt=0, le=100)
    text: str | None = Field(default=None, max_length=4000)
    unit: str = Field(default="", max_length=32)
    source: str = Field(default="本院检查", min_length=1, max_length=255)
    test_date: date | None = None
    report_start_date: date | None = None
    report_end_date: date | None = None
    reliability: Literal["可靠", "不可靠", "待复核"] = "可靠"
    independently_reviewed: StrictBool = False
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check(self):
        if self.kind in ("HbA1c", "FPG", "CGM估算HbA1c"):
            ExaminationRecord.model_validate(self.model_dump(exclude={"text", "note"}))
        elif self.value is None and not self.text:
            raise ValueError("请填写检查数值或报告摘要")
        if self.report_start_date and self.report_end_date and self.report_start_date > self.report_end_date:
            raise ValueError("报告结束日不能早于开始日")
        return self

    @property
    def effective_date(self):
        return self.report_end_date or self.test_date


class AssessmentRequest(V03Request):
    """评估测量与资料扩展；新版可引用，旧版仍执行新体重约束。"""

    f018_weight: float | None = Field(default=None, gt=0, le=500)
    measurement_id: int | None = Field(default=None, gt=0)
    measured_on: date | None = None
    intervention_other: str | None = Field(default=None, max_length=2000)
    duration_years: int | None = Field(default=None, ge=0, le=150, strict=True)
    duration_months: int | None = Field(default=None, ge=0, le=1800, strict=True)
    examinations: list[ClinicalExamination] = Field(default_factory=list)
    examination_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def duration_and_measurement(self):
        if self.input_schema_version == "v0.3" and self.f018_weight is None:
            raise ValueError("旧版评估必须填写本次体重；新版可引用已有测量")
        if self.duration_years is not None and self.duration_months is not None and self.duration_months >= 12:
            raise ValueError("填写病程年后，月只能填写0—11；只填月时可超过11个月")
        if self.measurement_id and self.f018_weight is not None:
            raise ValueError("请在沿用测量与新增体重之间选择一种")
        return self
    f019_height: float | None = Field(default=None, ge=50, le=250)


class MedicationRecord(BaseModel):
    """逐药事实由医生核对，不通过药物名称自动认定降糖作用或停药。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=128)
    dose: str = Field(min_length=1, max_length=128)
    status: Literal["使用中", "已停用", "待核对"]
    has_glucose_lowering_effect: StrictBool | None = None
    purpose: Purpose | None = None
    purposes: list[Literal["降糖治疗", "肾脏保护", "心血管保护", "体重管理", "其他", "器官获益"]] = Field(default_factory=list)
    catalog_id: str | None = None
    category_id: str | None = None
    medication_id: str | None = None
    start_precision: Literal["day", "month", "year", "unknown"] = "unknown"
    start_value: str | None = None
    started_on: date | None = None
    stopped_on: date | None = None

    @model_validator(mode="after")
    def validate_drug_dates(self):
        # 新结构保留精度；旧完整日期和单一用途仍可解释，不回写旧payload。
        import re
        if self.started_on and self.start_precision == "unknown" and not self.start_value:
            self.start_precision, self.start_value = "day", self.started_on.isoformat()
        if self.start_precision == "unknown":
            if self.start_value:
                raise ValueError("开始时间不详时不能同时填写具体时间")
        else:
            patterns = {"day": r"\d{4}-\d{2}-\d{2}", "month": r"\d{4}-\d{2}", "year": r"\d{4}"}
            if not self.start_value or not re.fullmatch(patterns[self.start_precision], self.start_value):
                raise ValueError("请按所选精度填写药物开始时间")
            try:
                earliest = date.fromisoformat(self.start_value + {"year": "-01-01", "month": "-01", "day": ""}[self.start_precision])
            except ValueError as exc:
                raise ValueError("药物开始时间无效") from exc
            if self.stopped_on and self.stopped_on < earliest:
                raise ValueError("实际停用日期不能早于开始时间范围")
            if self.start_precision == "day":
                if self.started_on and self.started_on != earliest:
                    raise ValueError("药物开始日期与精度值不一致")
                self.started_on = earliest
            elif self.started_on:
                raise ValueError("仅年或年月不能保存虚构的完整开始日期")
        if len(set(self.purposes)) != len(self.purposes):
            raise ValueError("用药目的不得重复")
        if self.purpose and self.purposes:
            mapping = {"高血糖治疗": {"降糖治疗"}, "器官获益": {"肾脏保护", "心血管保护", "器官获益"}, "体重获益": {"体重管理"}, "其他": {"其他"}}
            if not mapping[self.purpose].intersection(self.purposes):
                raise ValueError("主要用途与多选用药目的不一致")
        if self.status == "使用中" and self.stopped_on is not None:
            raise ValueError("使用中的药物不能同时记录实际停用日期")
        if self.status == "已停用" and self.stopped_on is None:
            raise ValueError("已停用药物请记录实际停用日期")
        if self.started_on and self.stopped_on and self.stopped_on < self.started_on:
            raise ValueError("实际停用日期不能早于开始日期")
        return self

    def matches_purpose(self, purpose: str) -> bool:
        groups = {"高血糖治疗": {"降糖治疗"}, "器官获益": {"肾脏保护", "心血管保护", "器官获益"}, "体重获益": {"体重管理"}, "其他": {"其他"}}
        return self.purpose == purpose or bool(groups.get(purpose, set()).intersection(self.purposes))


class ExaminationRecord(BaseModel):
    """F058本次选用记录；CGM使用报告结束日，避免误用出报告日。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["HbA1c", "FPG", "CGM估算HbA1c"]
    value: float = Field(gt=0, le=50)
    unit: Literal["%", "mmol/L"]
    source: str = Field(min_length=1, max_length=255)
    test_date: date | None = None
    report_start_date: date | None = None
    report_end_date: date | None = None
    reliability: Literal["可靠", "不可靠", "待复核"]
    independently_reviewed: StrictBool = False

    @model_validator(mode="after")
    def validate_examination(self):
        if self.unit != ("mmol/L" if self.kind == "FPG" else "%"):
            raise ValueError("检查单位与所选检查类型不一致")
        if self.kind != "FPG" and self.value > 30:
            raise ValueError("请核对HbA1c或估算HbA1c的输入值")
        if self.report_start_date and self.report_end_date and self.report_end_date < self.report_start_date:
            raise ValueError("CGM报告结束日不能早于开始日")
        return self

    @property
    def effective_date(self) -> date | None:
        return self.report_end_date if self.kind == "CGM估算HbA1c" else self.test_date


class ObservationAnchors(BaseModel):
    """F063明确适用性；允许适用但日期未知，由服务留待核对，不能跳过。"""

    model_config = ConfigDict(extra="forbid")
    f063_applicable_interventions: list[Intervention] = Field(min_length=1)
    f038_lifestyle_start_date: date | None = None
    f039_surgery_date: date | None = None

    @field_validator("f063_applicable_interventions")
    @classmethod
    def unique_interventions(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("适用干预不得重复")
        return value


class PreAssessmentV03(AssessmentRequest):
    f001_t2dm_established: Literal["是", "否", "待确认"]
    f002_acute_unsafe: YesNo
    f003_type_doubt: YesNo
    f004_treatment_context_sufficient: YesNo
    f005_refused: YesNo
    f061_conclusion: Literal["进入完整评估", "暂缓进入", "当前不启动"]
    f011_hold_reasons: list[Literal["急性安全", "分型存疑", "关键资料不足"]] = Field(default_factory=list)
    f012_pre_tasks: str | None = None
    # 机会信息不影响准入；以字典快照保存，不新增刚性临床条件。
    opportunity_info: dict[str, str | list[str] | None] = Field(default_factory=dict)
    f016_medications: list[MedicationRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def hold_reasons_match_facts(self):
        if self.f061_conclusion == "暂缓进入":
            expected = {
                "急性安全": self.f002_acute_unsafe == "是",
                "分型存疑": self.f003_type_doubt == "是" or self.f001_t2dm_established == "待确认",
                "关键资料不足": self.f004_treatment_context_sufficient == "否",
            }
            if not self.f011_hold_reasons or any(not expected[item] for item in self.f011_hold_reasons):
                raise ValueError("暂缓原因与本次核心问题核对不一致")
        elif self.f011_hold_reasons:
            raise ValueError("非暂缓结论不能同时保留暂缓原因")
        return self


class PreRecoveryV03(AssessmentRequest):
    """前置处理完成后的医生复核；不借分型/急性处理出口自动诊断。"""

    f016_medications: list[MedicationRecord] = Field(default_factory=list)

    result: Literal["分型仍为T2DM", "分型明确其他类型", "急性已处理返回结论", "急性已处理进入血糖稳定"]
    doctor_confirmed: StrictBool
    evidence_summary: str = Field(min_length=1, max_length=2000)
    stage_goal: str | None = None
    interventions: list[str] = Field(default_factory=list)
    next_review_date: date | None = None
    f023_constraints: list[str] = Field(default_factory=list)
    _validate_constraints = field_validator("f023_constraints")(_reject_exclusive_multiselect_conflict)
    _validate_multi = field_validator("interventions")(_reject_exclusive_multiselect_conflict)


class ObservationUpdateV03(V03Request):
    """观察期补核适用时间，不是一次新的身体测量或实际停药。"""

    anchors: ObservationAnchors


class FullAssessmentV03(AssessmentRequest):
    f026_start: Literal["启动", "暂缓补充关键资料", "当前不启动"]
    f013_diagnosis_basis: str | None = None
    recent_examination: ExaminationRecord | None = None
    f015_recent_glucose: str | None = None
    f015_test_date: date | None = None
    recent_glucose_reliable: Literal["是", "否", "待复核"] | None = None
    f016_medications: list[MedicationRecord] = Field(default_factory=list)
    f016_no_medication_confirmed: StrictBool = False
    f023_constraints: list[str] = Field(default_factory=list)
    f024_willing: YesNo | None = None
    f025_review_accept: YesNo | None = None
    f027_stage: Stage | None = None
    f028_stage_goal: str | None = None
    f029_interventions: list[str] = Field(default_factory=list)
    f012_pre_tasks: str | None = None
    next_review_date: date | None = None
    _validate_multi = field_validator("f023_constraints", "f029_interventions")(_reject_exclusive_multiselect_conflict)

    @model_validator(mode="after")
    def medication_confirmation_consistency(self):
        if self.f016_no_medication_confirmed and any(m.status != "已停用" for m in self.f016_medications):
            raise ValueError("已确认当前无药时不能同时提交在用或待核对药物")
        return self


class PhaseReviewV03(AssessmentRequest):
    f030_safety_issues: list[str] = Field(min_length=1)
    f031_stage_indicator: str = Field(min_length=1)
    f032_treatment_changes: list[str] = Field(min_length=1)
    f033_executable: Literal["可继续", "需调整", "无法继续"]
    f034_action: Literal["继续当前阶段", "调整方案或目标", "转换阶段", "结束主动管理"]
    f035_stop_last_med: StrictBool
    f057_actual_stop: Literal["已实际停用", "仅计划停用", "待核对"] | None = None
    planned_stop_date: date | None = None
    f036_stop_date: date | None = None
    f053_has_drug: StrictBool | None  # 必须显式提交；null代表待确认而不是否
    f054_purpose: Purpose | None = None
    f060_non_diabetic_on_treatment: Literal["是", "否", "待确认"] | None = None
    f056_uncontrolled: StrictBool = False
    f016_medications: list[MedicationRecord] = Field(default_factory=list)
    anchors: ObservationAnchors | None = None
    f062_target_stage: Stage | None = None
    stage_goal: str | None = None
    adjustment_summary: str | None = None
    end_reason: str | None = None
    next_review_date: date | None = None
    _validate_multi = field_validator("f030_safety_issues", "f032_treatment_changes")(_reject_exclusive_multiselect_conflict)

    @model_validator(mode="after")
    def actual_stop_consistency(self):
        if not self.f035_stop_last_med and any((self.f057_actual_stop, self.planned_stop_date, self.f036_stop_date)):
            raise ValueError("未作停药决定时不能记录停药执行状态或日期")
        if self.f035_stop_last_med and self.f057_actual_stop is None:
            raise ValueError("医生作停药决定后须核对实际执行状态")
        if self.f057_actual_stop == "已实际停用":
            if not self.f035_stop_last_med or self.f036_stop_date is None or self.f053_has_drug is not False:
                raise ValueError("实际全部停药须有医生决定、实际日期且明确无降糖作用药")
            if any(m.status == "使用中" and m.has_glucose_lowering_effect is not False for m in self.f016_medications):
                raise ValueError("当前药物记录仍有降糖作用或待核对药物，不能记为全部实际停药")
        elif self.f036_stop_date is not None:
            raise ValueError("计划停药或待核对时不能把计划日期记为实际停药日")
        if self.f053_has_drug is True:
            current = [m for m in self.f016_medications if m.status == "使用中" and m.has_glucose_lowering_effect is True]
            if not current:
                raise ValueError("确认仍有降糖作用药物时，请逐药记录当前使用中的药物")
            if self.f054_purpose and not any(m.matches_purpose(self.f054_purpose) for m in current):
                raise ValueError("药物主要用途与逐药记录不一致")
        return self


class MedicationRestartV03(V03Request):
    f037_reason: Literal["因高血糖", "因器官获益", "因体重获益"]
    f062_target_stage: Stage | None = None
    f016_medications: list[MedicationRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def verify_restart_record(self):
        current = [m for m in self.f016_medications if m.status == "使用中" and m.has_glucose_lowering_effect is True]
        if not current:
            raise ValueError("重新用药需医生核对当前使用中药物确有降糖作用")
        expected = {"因高血糖": "高血糖治疗", "因器官获益": "器官获益", "因体重获益": "体重获益"}[self.f037_reason]
        if not any(m.matches_purpose(expected) for m in current):
            raise ValueError("重新用药原因与逐药用途不一致")
        return self


class RemissionJudgeV03(AssessmentRequest):
    f041_diagnosis_credible: Literal["是", "否", "待复核"]
    f042_drug_free_3m: Literal["是", "否", "待核对"]
    f043_hba1c_reliable: Literal["是", "否", "待复核"]
    f053_has_drug: StrictBool | None
    f059_completeness: Literal["完整", "缺失", "时间未满足", "结果待复核"]
    f058_examination: ExaminationRecord | None = None
    f058_examination_id: int | None = Field(default=None, gt=0)
    f016_medications: list[MedicationRecord] = Field(default_factory=list)
    f062_target_stage: Stage | None = None
    f012_pre_tasks: str | None = None
    anchors: ObservationAnchors | None = None


class RemissionConfirmV03(V03Request):
    """同次核对与确认共用测量；凭具体事件+版本，不查历史任意达标。"""

    f048_confirm: Literal["确认", "暂不确认"]
    assessment_event_id: int = Field(gt=0)
    f012_pre_tasks: str | None = None


class PostRemissionV03(AssessmentRequest):
    f049_glucose: str | None = None
    f049_test_date: date | None = None
    f050_med_status: Literal["未使用", "因高血糖", "因器官获益", "因体重获益", "待核对"]
    f055_glucose_state: Literal["低于糖尿病诊断阈值", "达到糖尿病范围", "暂不能可靠解释"]
    f051_risk_triggers: list[str] = Field(default_factory=list)
    risk_increase_confirmed: StrictBool
    f016_medications: list[MedicationRecord] = Field(default_factory=list)
    f062_target_stage: Stage | None = None
    f012_pre_tasks: str | None = None
    next_review_date: date | None = None
    _validate_multi = field_validator("f051_risk_triggers")(_reject_exclusive_multiselect_conflict)

    @model_validator(mode="after")
    def verify_post_remission_medications(self):
        current = [m for m in self.f016_medications if m.status == "使用中" and m.has_glucose_lowering_effect is True]
        expected = {"因高血糖": "高血糖治疗", "因器官获益": "器官获益", "因体重获益": "体重获益"}
        if self.f050_med_status in expected and not any(m.matches_purpose(expected[self.f050_med_status]) for m in current):
            raise ValueError("本次用药状态须有相符的当前逐药记录")
        if self.f050_med_status == "未使用" and current:
            raise ValueError("未使用降糖作用药物与逐药记录不一致")
        return self


class SupplementalDecisionV03(V03Request):
    """补充出口需独立的医生明确决定；不能由旧字段的否值自动触发。"""

    transition_id: Literal["P01", "P02", "P03A", "P03B", "P04", "P05A", "P05B"]
    doctor_confirmed: Literal[True]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_summary: str = Field(min_length=1, max_length=2000)
    remission_termination_confirmed: StrictBool = False
    f050_med_status: Literal["未使用", "因高血糖", "因器官获益", "因体重获益"] | None = None

    f016_medications: list[MedicationRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_benefit_regimen(self):
        if self.transition_id not in {"P05A", "P05B"}:
            return self
        if not self.medication_review_complete:
            raise ValueError("获益用药返回前请完整核对当前药物方案")
        purpose = {"因器官获益": "器官获益", "因体重获益": "体重获益"}.get(self.f050_med_status)
        current = [m for m in self.f016_medications if m.status == "使用中" and m.has_glucose_lowering_effect is True]
        if not purpose or not any(m.matches_purpose(purpose) for m in current):
            raise ValueError("获益用药返回须有目的相符的当前在用降糖作用药物")
        if any(m.status == "待核对" or (m.status == "使用中" and m.has_glucose_lowering_effect is None) for m in self.f016_medications):
            raise ValueError("当前药物方案仍有待核对资料，请先完整核实")
        return self

    @field_validator("doctor_confirmed", mode="before")
    @classmethod
    def strict_doctor_confirmation(cls, value):
        if value is not True:
            raise ValueError("必须由医生明确确认本次返回操作")
        return value
