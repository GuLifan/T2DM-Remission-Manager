"""
模块名称：full_assessment.py
所属层级：临床服务层（services）
功能说明：实现"单元2｜完整评估并形成主动管理计划"的决策逻辑。

**同一次决策事件**内完成：完整评估资料 + 是否启动 + 当前阶段 + 一个主要目标 +
干预组合 + 首次正式复评时间（锁定稿§6：不得拆成连续重复页面）。

临床依据：《临床流程锁定稿 v1.0》第六节；规则 E2-B01…E2-B04；
          `_SPEC/06` 裁决（血糖稳定阶段默认复评 12 周，医生可调整）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.core.exceptions import BusinessRuleError
from app.domain import enums, templates
from app.domain.states import ST00, ST20, ST31, ST32
from app.domain.transitions import validate_transition
from app.models.clinical import FullAssessmentInput, FullAssessmentResult
from app.services import defaults

# 阶段取值 → 目标状态
_STAGE_TO_STATE = {enums.STAGE_STABLE: ST31, enums.STAGE_INDUCTION: ST32}
# 阶段取值 → 输出模板
_STAGE_TO_TEMPLATE = {enums.STAGE_STABLE: "OUT-E2-STABLE", enums.STAGE_INDUCTION: "OUT-E2-INDUCTION"}


def evaluate_full_assessment(
    current_state: str, data: FullAssessmentInput, today: date
) -> FullAssessmentResult:
    """执行完整评估并形成主动管理计划。

    参数:
        current_state (str): 患者当前状态（本单元应为 ST20）。
        data (FullAssessmentInput): 六维度评估资料与一次性计划决策。
        today (date): 决策当天（用于计算默认复评日期，由 Clock 注入）。

    返回:
        FullAssessmentResult: 计划结论与目标状态。

    异常:
        BusinessRuleError: 暂缓未填资料、启动但缺少阶段/目标/干预组合、或启动取值非法。

    临床依据: 《临床流程锁定稿 v1.0》第六节。
    """
    # ---- 暂缓补充关键资料：留在 ST20，只保留真正改变决策的缺失资料 ----
    if data.f026_start == enums.HOLD_SUPPLEMENT:
        if not (data.f012_pre_tasks or "").strip():
            raise BusinessRuleError("暂缓补充关键资料时必须填写需要补充的内容。", code="PRE_TASKS_REQUIRED")
        target_state = ST20
        validate_transition(current_state, target_state)
        return FullAssessmentResult(
            rule_id="E2-B03",
            template_id="OUT-E2-HOLD",
            output_text=templates.render("OUT-E2-HOLD", pre_tasks=data.f012_pre_tasks or ""),
            target_state=target_state,
        )

    # ---- 当前不启动：返回常规糖尿病综合管理 ----
    if data.f026_start == enums.NOT_START:
        target_state = ST00
        validate_transition(current_state, target_state)
        return FullAssessmentResult(
            rule_id="E2-B04",
            template_id="OUT-E2-NOSTART",
            output_text=templates.render("OUT-E2-NOSTART"),
            target_state=target_state,
        )

    # ---- 启动主动管理：一次性完成阶段、目标、干预与首次复评 ----
    if data.f026_start == enums.START:
        if data.f027_stage not in _STAGE_TO_STATE:
            raise BusinessRuleError("启动主动管理时必须选择当前管理阶段。", code="STAGE_REQUIRED")
        if not (data.f028_stage_goal or "").strip():
            raise BusinessRuleError("启动主动管理时必须填写一个主要阶段目标。", code="GOAL_REQUIRED")
        if not data.f029_interventions:
            raise BusinessRuleError("启动主动管理时至少选择一种干预组合。", code="INTERVENTIONS_REQUIRED")

        target_state = _STAGE_TO_STATE[data.f027_stage]
        validate_transition(current_state, target_state)
        # 医生未指定复评日期时按默认 12 周计算（默认值集中在 services/defaults.py）
        next_review = data.next_review_date or defaults.default_next_review_date(today)
        interventions = "、".join(data.f029_interventions)
        rule_id = "E2-B01" if target_state == ST31 else "E2-B02"
        template_id = _STAGE_TO_TEMPLATE[data.f027_stage]
        return FullAssessmentResult(
            rule_id=rule_id,
            template_id=template_id,
            output_text=templates.render(
                template_id,
                stage_goal=data.f028_stage_goal or "",
                interventions=interventions,
                next_review_date=next_review.isoformat(),
            ),
            target_state=target_state,
            stage=data.f027_stage,
            stage_goal=data.f028_stage_goal,
            interventions=interventions,
            next_review_date=next_review,
        )

    # 取值非法属于工程缺陷（前端应只提供三个合法选项）
    raise BusinessRuleError("无法识别的启动选项，请重新选择。", code="INVALID_START_OPTION")
