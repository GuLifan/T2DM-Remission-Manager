"""
模块名称：phase_review.py
所属层级：临床服务层（services）
功能说明：实现"单元3｜阶段复评与治疗调整"的决策逻辑（主动管理期间唯一反复出现的医生决策事件）。

分支裁决方式（V1.0 关键改进）：
    不再用"多个独立勾选框 + 隐含优先级"，而是走 `domain.branches.PHASE_REVIEW_BRANCHES`
    的显式优先级表；被高优先级分支覆盖的分支会以自然语言说明返回给前台，
    **绝不静默丢弃医生已填内容**（V0.1 实测缺陷：停药日期被静默忽略）。

临床依据：《临床流程锁定稿 v1.0》第七节；规则 E3-B01…E3-B08；
          `_SPEC/06` Q004（获益用药不提示停药）、Q007（明显失控由医生确认，不设自动阈值）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.core.exceptions import BusinessRuleError
from app.domain import enums, templates
from app.domain.branches import resolve_branch
from app.domain.states import ST00, ST31, ST32, ST40, state_name
from app.domain.transitions import validate_transition
from app.models.clinical import PhaseReviewInput, PhaseReviewResult
from app.services import defaults
from app.utils.date_utils import compute_earliest_judge_date


def evaluate_phase_review(
    current_state: str,
    data: PhaseReviewInput,
    today: date,
    *,
    lifestyle_start_date: date | None = None,
    surgery_date: date | None = None,
) -> PhaseReviewResult:
    """执行阶段复评。

    参数:
        current_state (str): 当前主动管理阶段（ST31 或 ST32）。
        data (PhaseReviewInput): 复评输入。
        today (date): 决策当天（用于默认复评日期）。
        lifestyle_start_date / surgery_date: 观察期的时间锚点（如适用，用于计算最早可判定日期）。

    返回:
        PhaseReviewResult: 复评结论、目标状态与（如有）被忽略分支的说明。

    异常:
        BusinessRuleError: 互斥分支同时为真、缺少必需输入、动作取值非法。

    临床依据: 《临床流程锁定稿 v1.0》第七节。
    """
    # 阶段简称（血糖稳定 / 缓解诱导）：用于比较与写入患者档案
    stage_value = enums.STAGE_STABLE if current_state == ST31 else enums.STAGE_INDUCTION
    # 状态全名：仅用于自然语言文案中的"当前阶段"
    stage_label = state_name(current_state)

    # ---- 1) 汇总本次为真的分支（只收集特殊分支；常规动作作为兜底）----
    hits: set[str] = set()
    if data.f056_uncontrolled:
        hits.add("uncontrolled")
    if (
        data.f053_has_drug
        and data.f054_purpose in enums.BENEFIT_PURPOSES
        and data.glucose_non_diabetic
    ):
        hits.add("on_treatment_non_diabetic")
    if data.f035_stop_last_med:
        hits.add("stop_last_med")
    if not hits:
        # 没有任何特殊分支为真时，按医生所选动作走常规复评
        hits = {"routine_action"}

    # ---- 2) 按优先级裁决（含互斥校验）----
    try:
        chosen, ignored = resolve_branch(hits)
    except ValueError as error:
        # 互斥冲突：转成医生可读提示，而不是交给前端静默处理
        raise BusinessRuleError(str(error), code="BRANCH_CONFLICT") from error
    ignored_notes = [f"{item.branch.label}：{item.reason}" for item in ignored]

    # ---- 3) 按生效分支执行 ----
    if chosen.key == "uncontrolled":
        # E3-B08：明显血糖失控由医生确认，不设自动医学阈值；返回血糖稳定阶段
        adjustment = data.adjustment_summary or "明显血糖失控，返回血糖稳定阶段"
        next_review = data.next_review_date or defaults.default_next_review_date(today)
        target_state = ST31
        validate_transition(current_state, target_state)
        return PhaseReviewResult(
            rule_id="E3-B08",
            template_id="OUT-E3-ADJUST",
            output_text=templates.render(
                "OUT-E3-ADJUST",
                current_stage=state_name(ST31),
                adjustment_summary=adjustment,
                next_review_date=next_review.isoformat(),
            ),
            target_state=target_state,
            stage=enums.STAGE_STABLE,
            next_review_date=next_review,
            ignored_branches=ignored_notes,
        )

    if chosen.key == "on_treatment_non_diabetic":
        # E3-B06：治疗下血糖达标且仍用获益药——只记录，不提示停药、不进入观察期
        target_state = current_state  # 留在当前阶段（自环）
        validate_transition(current_state, target_state)
        return PhaseReviewResult(
            rule_id="E3-B06",
            template_id="OUT-E3-ON-TREATMENT",
            output_text=templates.render("OUT-E3-ON-TREATMENT"),
            target_state=target_state,
            stage=stage_value,
            next_review_date=data.next_review_date,
            ignored_branches=ignored_notes,
        )

    if chosen.key == "stop_last_med":
        # E3-B07：停用最后一种降糖药 → 系统自动进入观察期（无"停药确认页面"）
        if data.f036_stop_date is None:
            raise BusinessRuleError("停用最后一种降糖作用药物时必须记录停药日期。", code="STOP_DATE_REQUIRED")
        target_state = ST40
        validate_transition(current_state, target_state)
        earliest = compute_earliest_judge_date(
            last_med_stop_date=data.f036_stop_date,
            lifestyle_start_date=lifestyle_start_date,
            surgery_date=surgery_date,
        )
        return PhaseReviewResult(
            rule_id="E3-B07",
            template_id="OUT-E3-OBS-ENTER",
            output_text=templates.render(
                "OUT-E3-OBS-ENTER", last_med_stop_date=data.f036_stop_date.isoformat()
            ),
            target_state=target_state,
            stage=None,
            next_review_date=None,
            entered_observation=True,
            earliest_judge_date=earliest,
            ignored_branches=ignored_notes,
        )

    # ---- 4) 常规复评动作（E3-B01…B05）----
    return _routine_action(current_state, stage_value, stage_label, data, today, ignored_notes)


def _routine_action(
    current_state: str,
    stage_value: str,
    stage_label: str,
    data: PhaseReviewInput,
    today: date,
    ignored_notes: list[str],
) -> PhaseReviewResult:
    """处理常规复评动作：继续 / 调整 / 转换阶段 / 结束主动管理。"""
    next_review = data.next_review_date or defaults.default_next_review_date(today)

    if data.f034_action == enums.ACT_CONTINUE:
        validate_transition(current_state, current_state)
        return PhaseReviewResult(
            rule_id="E3-B01",
            template_id="OUT-E3-CONTINUE",
            output_text=templates.render("OUT-E3-CONTINUE", next_review_date=next_review.isoformat()),
            target_state=current_state,
            stage=stage_value,
            next_review_date=next_review,
            ignored_branches=ignored_notes,
        )

    if data.f034_action == enums.ACT_ADJUST:
        if not (data.adjustment_summary or "").strip():
            raise BusinessRuleError("调整方案或目标时必须填写调整内容。", code="ADJUST_REQUIRED")
        # 调整仍留在当前阶段：不重新做完整评估（锁定稿§11 返回路径）
        validate_transition(current_state, current_state)
        return PhaseReviewResult(
            rule_id="E3-B02",
            template_id="OUT-E3-ADJUST",
            output_text=templates.render(
                "OUT-E3-ADJUST",
                current_stage=stage_label,
                adjustment_summary=data.adjustment_summary or "",
                next_review_date=next_review.isoformat(),
            ),
            target_state=current_state,
            stage=stage_value,
            next_review_date=next_review,
            ignored_branches=ignored_notes,
        )

    if data.f034_action == enums.ACT_SWITCH:
        # 阶段互转必须由医生确认，且新阶段必须与当前阶段不同
        if data.new_stage not in enums.STAGES:
            raise BusinessRuleError("转换阶段时必须选择新的管理阶段。", code="NEW_STAGE_REQUIRED")
        # 注意：必须与阶段简称比较（状态全名带"主动管理—"前缀，两者不可直接比较）
        if data.new_stage == stage_value:
            raise BusinessRuleError("新阶段与当前阶段相同，无需转换。", code="SAME_STAGE")
        if not (data.stage_goal or "").strip():
            raise BusinessRuleError("转换阶段时必须填写新的主要阶段目标。", code="GOAL_REQUIRED")
        target_state = ST31 if data.new_stage == enums.STAGE_STABLE else ST32
        validate_transition(current_state, target_state)
        rule_id = "E3-B03" if target_state == ST32 else "E3-B04"
        return PhaseReviewResult(
            rule_id=rule_id,
            template_id="OUT-E3-SWITCH",
            output_text=templates.render(
                "OUT-E3-SWITCH",
                old_stage=stage_label,
                new_stage=data.new_stage,
                stage_goal=data.stage_goal or "",
                next_review_date=next_review.isoformat(),
            ),
            target_state=target_state,
            stage=data.new_stage,
            stage_goal=data.stage_goal,
            next_review_date=next_review,
            ignored_branches=ignored_notes,
        )

    if data.f034_action == enums.ACT_END:
        if not (data.end_reason or "").strip():
            raise BusinessRuleError("结束主动管理时必须记录结束原因。", code="END_REASON_REQUIRED")
        target_state = ST00
        validate_transition(current_state, target_state)
        return PhaseReviewResult(
            rule_id="E3-B05",
            template_id="OUT-E3-END",
            output_text=templates.render("OUT-E3-END"),
            target_state=target_state,
            stage=None,
            next_review_date=None,
            ignored_branches=ignored_notes,
        )

    raise BusinessRuleError("无法识别的复评动作，请重新选择。", code="INVALID_REVIEW_ACTION")
