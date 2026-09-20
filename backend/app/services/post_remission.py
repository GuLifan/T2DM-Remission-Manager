"""
模块名称：post_remission.py
所属层级：临床服务层（services）
功能说明：实现"单元6｜缓解后复评"的决策逻辑。

分支：缓解维持 / 风险上升 / 因获益用药不可评价 / 缓解终止。
**关键纪律**：因器官或体重获益用药导致不可评价时，**不得等同于复发**
（锁定稿§10；`_SPEC/06` Q004）。

临床依据：《临床流程锁定稿 v1.0》第十节；规则 E5-B01…E5-B05；
          `_SPEC/06` Q004/Q012（返回阶段由医生选择）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.core.exceptions import BusinessRuleError
from app.domain import enums, templates
from app.domain.states import ST20, ST31, ST32, ST60
from app.domain.transitions import validate_transition
from app.models.clinical import PostRemissionInput, PostRemissionResult
from app.services import defaults

# 阶段取值 → 状态代码
_STAGE_TO_STATE = {enums.STAGE_STABLE: ST31, enums.STAGE_INDUCTION: ST32}


def evaluate_post_remission(
    current_state: str,
    data: PostRemissionInput,
    today: date,
    *,
    remission_confirmed_date: date | None = None,
) -> PostRemissionResult:
    """执行缓解后复评。

    参数:
        current_state (str): 当前状态（本单元应为 ST60）。
        data (PostRemissionInput): 复评输入。
        today (date): 当前日期（由 Clock 注入）。
        remission_confirmed_date (date | None): 缓解确认日期（用于计算默认随访日期）。

    返回:
        PostRemissionResult: 结论、目标状态与下次随访日期。

    异常:
        BusinessRuleError: 需要返回阶段复评但医生未选择阶段时抛出。
    """
    # ---- 1) 缓解状态终止：直接返回事件3；仅新分型证据或重大变化返回完整评估 ----
    # 终止有两个触发条件（锁定稿§10）：血糖达到糖尿病范围，或因高血糖重新使用降糖药。
    # 两者任一成立即视为本次缓解状态结束——但"因器官/体重获益用药"不在此列（见下一分支）。
    terminated = data.f055_glucose_state == enums.GLUCOSE_DIABETIC_RANGE or (
        data.f050_med_status == enums.MED_FOR_HYPERGLYCEMIA
    )
    if terminated:
        if data.has_new_type_evidence:
            validate_transition(current_state, ST20)
            return PostRemissionResult(
                rule_id="E5-B04",
                template_id="OUT-E5-END",
                output_text=templates.render("OUT-E5-END"),
                target_state=ST20,
            )
        target_state = _require_target_stage(data, current_state)
        return PostRemissionResult(
            rule_id="E5-B04",
            template_id="OUT-E5-END",
            output_text=templates.render("OUT-E5-END"),
            target_state=target_state,
            stage=data.target_stage,
        )

    # ---- 2) 因器官/体重获益用药：当前缓解状态不可评价（不等同于复发）----
    if data.f050_med_status in (enums.MED_FOR_ORGAN, enums.MED_FOR_WEIGHT):
        target_state = _require_target_stage(data, current_state)
        return PostRemissionResult(
            rule_id="E5-B03",
            template_id="OUT-E5-UNEVALUABLE",
            output_text=templates.render("OUT-E5-UNEVALUABLE"),
            target_state=target_state,
            stage=data.target_stage,
        )

    # ---- 3) 血糖状态暂不能可靠解释：保留缓解状态并提示定向复核 ----
    if data.f055_glucose_state == enums.GLUCOSE_UNEXPLAINED:
        validate_transition(current_state, ST60)
        return PostRemissionResult(
            rule_id="SYS-E5-REVIEW",
            template_id="SYS-E5-REVIEW",
            output_text=templates.render("SYS-E5-REVIEW"),
            target_state=ST60,
            stage=None,
            next_review_date=_next_review(data, today, remission_confirmed_date),
        )

    # ---- 4) 缓解维持（含风险上升）----
    validate_transition(current_state, ST60)
    next_review = _next_review(data, today, remission_confirmed_date)
    if data.f051_risk_triggers:
        rule_id, template_id = "E5-B02", "OUT-E5-RISK"
    else:
        rule_id, template_id = "E5-B01", "OUT-E5-MAINTAIN"
    return PostRemissionResult(
        rule_id=rule_id,
        template_id=template_id,
        output_text=templates.render(template_id),
        target_state=ST60,
        stage=None,
        next_review_date=next_review,
    )


def _require_target_stage(data: PostRemissionInput, current_state: str) -> str:
    """校验并返回医生选择的返回阶段（系统不得替他决定）。"""
    if data.target_stage not in _STAGE_TO_STATE:
        raise BusinessRuleError(
            "返回主动管理时必须由医生选择管理阶段（血糖稳定或缓解诱导）。",
            code="TARGET_STAGE_REQUIRED",
        )
    target_state = _STAGE_TO_STATE[data.target_stage]
    validate_transition(current_state, target_state)
    return target_state


def _next_review(
    data: PostRemissionInput, today: date, remission_confirmed_date: date | None
) -> date | None:
    """计算下次随访日期。

    优先级：医生指定 > 按随访节奏计算（第 6/12/18/24 个月，满 2 年后按年顺延）。
    缺少缓解确认日期时返回 None，由前台提示医生手工设置，系统不猜测。

    参数:
        data (PostRemissionInput): 复评输入（可能含医生指定的 next_review_date）。
        today (date): 当前日期（由 Clock 注入）。
        remission_confirmed_date (date | None): 缓解确认日期。

    返回:
        date | None: 下次随访日期或 None。
    """
    if data.next_review_date is not None:
        return data.next_review_date
    if remission_confirmed_date is None:
        # 缺少缓解确认日期时无法计算节奏，交给前台提示医生手工设置
        return None
    return defaults.next_followup_date(remission_confirmed_date, today)
