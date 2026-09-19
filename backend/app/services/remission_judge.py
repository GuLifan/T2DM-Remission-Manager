"""
模块名称：remission_judge.py
所属层级：临床服务层（services）
功能说明：实现"单元5｜缓解判定"的决策逻辑。

核心纪律（锁定稿§9）：
    **系统只核对客观条件，绝不自动确认缓解。** 客观条件满足时，只把"可以请医生确认"
    交给医生；是否形成"2型糖尿病缓解"临床结论，必须由医生点击确认。

客观条件（E4-B03）：
    既往诊断可信（F041=是） 且 已停用全部降糖作用药物≥3个月（F042=是） 且 当前日期≥F040
    且〔HbA1c 可靠且 F014＜6.5%〕或〔HbA1c 不可靠且（FPG＜7.0 或 eA1c＜6.5%）且已完成独立复核 F046=是〕

临床依据：《临床流程锁定稿 v1.0》第九节；规则 E4-B01…E4-B07；
          `_SPEC/06` Q005（指标优先级与替代复核）、Q006（未达标返回事件3）、
          Q008（F041=否 返回 ST20 复核）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.core.exceptions import BusinessRuleError
from app.domain import enums, templates
from app.domain.states import ST20, ST31, ST32, ST40, ST50, ST60
from app.domain.transitions import validate_transition
from app.models.clinical import RemissionJudgeInput, RemissionJudgeResult

# 缓解判定阈值（锁定稿§9；不设自动准入阈值，只用于客观条件核对）
HBA1C_THRESHOLD = 6.5
FPG_THRESHOLD = 7.0


def check_remission(
    current_state: str,
    data: RemissionJudgeInput,
    *,
    today: date,
    earliest_judge_date: date | None,
    has_glucose_lowering_drug: bool | None,
) -> RemissionJudgeResult:
    """核对缓解判定的客观条件（不形成结论）。

    参数:
        current_state (str): 当前状态（本单元应为 ST50）。
        data (RemissionJudgeInput): 医生填写的核对输入。
        today (date): 当前日期（由 Clock 注入）。
        earliest_judge_date (date | None): 最早可判定日期（F040）。
        has_glucose_lowering_drug (bool | None): 最近一次医生确认的用药状态（F053）。

    返回:
        RemissionJudgeResult: blocked / objective_met / 结论文案 / 目标状态。
        当目标状态需要医生选择（返回哪个管理阶段）时，`needs_target_stage=True` 且
        `target_state` 为空字符串——由接口层要求医生补选后再落库。

    临床依据: 《临床流程锁定稿 v1.0》第九节。
    """
    # ---- 1) 既往诊断明确不可信：返回到完整评估复核（含分型再评估）----
    if data.f041_diagnosis_credible == enums.NO:
        validate_transition(current_state, ST20)
        return RemissionJudgeResult(
            blocked=True,
            objective_met=False,
            rule_id="E4-B07",
            template_id="OUT-E4-UNCERTAIN",
            output_text=templates.render(
                "OUT-E4-UNCERTAIN", pre_tasks="复核既往诊断依据与糖尿病分型"
            ),
            target_state=ST20,
        )

    # ---- 2) 未到期：阻断确认，回到观察期 ----
    if earliest_judge_date is None or today < earliest_judge_date:
        validate_transition(current_state, ST40)
        return RemissionJudgeResult(
            blocked=True,
            objective_met=False,
            rule_id="E4-B01",
            template_id="OUT-E4-NOT-DUE",
            output_text=templates.render(
                "OUT-E4-NOT-DUE",
                earliest_assessment_date=(
                    earliest_judge_date.isoformat() if earliest_judge_date else "待确定（缺少停药日期）"
                ),
            ),
            target_state=ST40,
        )

    # ---- 3) 仍在使用降糖作用药物：阻断"无药缓解"确认 ----
    if has_glucose_lowering_drug:
        # 系统不自动建议停药；返回哪个阶段由医生选择
        return RemissionJudgeResult(
            blocked=True,
            objective_met=False,
            rule_id="E4-B02",
            template_id="OUT-E4-ON-DRUG",
            output_text=templates.render("OUT-E4-ON-DRUG"),
            target_state="",
            needs_target_stage=True,
        )

    # ---- 4) 客观条件核对 ----
    objective_met, not_met = _objective_conditions(data)

    if objective_met:
        validate_transition(current_state, ST50)
        return RemissionJudgeResult(
            blocked=False,
            objective_met=True,
            rule_id="E4-B03",
            template_id="OUT-E4-OBJECTIVE-MET",
            output_text=templates.render("OUT-E4-OBJECTIVE-MET"),
            target_state=ST50,
            doctor_confirmation_required=True,
        )

    if not_met:
        # 指标未达缓解标准：核对指标可靠性后直接返回事件3，不返回完整评估
        return RemissionJudgeResult(
            blocked=False,
            objective_met=False,
            rule_id="E4-B06",
            template_id="OUT-E4-NOT-MET",
            output_text=templates.render("OUT-E4-NOT-MET"),
            target_state="",
            needs_target_stage=True,
        )

    # ---- 5) 资料不足以可靠确认或排除：保留判定环节，生成定向复核任务 ----
    validate_transition(current_state, ST50)
    return RemissionJudgeResult(
        blocked=False,
        objective_met=False,
        rule_id="E4-B07",
        template_id="OUT-E4-UNCERTAIN",
        output_text=templates.render(
            "OUT-E4-UNCERTAIN", pre_tasks="核对停药时间锚点、指标可靠性与替代指标独立复核结果"
        ),
        target_state=ST50,
    )


def _objective_conditions(data: RemissionJudgeInput) -> tuple[bool, bool]:
    """核对客观条件。

    返回:
        tuple[bool, bool]: (是否满足, 是否明确未达标)。
        两者都为 False 表示"资料不足以判断"。
    """
    if data.f042_drug_free_3m != enums.YES or data.f041_diagnosis_credible != enums.YES:
        # 停药时间或诊断可信度待核对 → 无法判断（不是"未达标"）
        return False, False

    if data.f043_hba1c_reliable == enums.YES:
        # HbA1c 可靠时只走 HbA1c 分支（不得随意改用替代指标）
        if data.f014_hba1c is None:
            return False, False
        if data.f014_hba1c < HBA1C_THRESHOLD:
            return True, False
        return False, True

    if data.f043_hba1c_reliable == enums.NO:
        # 仅当 HbA1c 不可靠时才允许替代指标，且必须完成独立复核
        if data.f046_independent_review != enums.YES:
            return False, False
        alternative_met = (data.f044_fpg is not None and data.f044_fpg < FPG_THRESHOLD) or (
            data.f045_ea1c is not None and data.f045_ea1c < HBA1C_THRESHOLD
        )
        if alternative_met:
            return True, False
        # 替代指标都已给出但均未达标 → 明确未达标
        if data.f044_fpg is not None or data.f045_ea1c is not None:
            return False, True
        return False, False

    # HbA1c 可靠性"待复核"：无法判断
    return False, False


def confirm_remission(current_state: str, action: str, pre_tasks: str | None = None) -> RemissionJudgeResult:
    """医生确认环节（E4-B04 / E4-B05）。

    参数:
        current_state (str): 当前状态（本单元应为 ST50）。
        action (str): 确认 / 暂不确认。
        pre_tasks (str | None): 暂不确认时的定向复核项目（必填）。

    返回:
        RemissionJudgeResult: 确认则进入缓解后复评（ST60）；暂不确认则保留 ST50 并生成复核任务。

    临床依据: 《临床流程锁定稿 v1.0》第九节 E4-B04/B05。
    """
    if action == "确认":
        validate_transition(current_state, ST60)
        return RemissionJudgeResult(
            blocked=False,
            objective_met=True,
            rule_id="E4-B04",
            template_id="OUT-E4-CONFIRMED",
            output_text=templates.render("OUT-E4-CONFIRMED"),
            target_state=ST60,
            needs_followup_tasks=True,
        )
    if action == "暂不确认":
        if not (pre_tasks or "").strip():
            raise BusinessRuleError("暂不确认缓解时必须填写定向复核项目。", code="REVIEW_TASKS_REQUIRED")
        validate_transition(current_state, ST50)
        return RemissionJudgeResult(
            blocked=False,
            objective_met=True,
            rule_id="E4-B05",
            template_id="OUT-E4-UNCERTAIN",
            output_text=templates.render("OUT-E4-UNCERTAIN", pre_tasks=pre_tasks or ""),
            target_state=ST50,
        )
    raise BusinessRuleError("无法识别的确认动作，请重新选择。", code="INVALID_CONFIRM_ACTION")


def choose_target_stage(rule_id: str) -> tuple[str, ...]:
    """返回"需要医生选择返回阶段"时的可选状态（供接口层构造提示与校验）。"""
    if rule_id in {"E4-B02", "E4-B06"}:
        return (ST31, ST32)
    return ()
