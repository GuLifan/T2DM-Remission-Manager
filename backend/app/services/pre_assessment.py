"""
模块名称：pre_assessment.py
所属层级：临床服务层（services）
功能说明：实现"单元1｜60秒缓解预评估"的决策逻辑。

只判断患者**目前是否值得进入完整评估**，不判断最终能否缓解。

分支优先级（自上而下，先命中先返回）：
    1. 患者明确拒绝 → 当前不启动（E1-B05）
    2. T2DM 判断不成立 → 当前不启动（E1-B05）
    3. 暂缓原因（可多项并存）：急性安全（置顶）> 分型存疑 > 关键治疗背景不足
    4. 三者皆无 → 进入完整评估（E1-B01）

临床依据：《临床流程锁定稿 v1.0》第五节；规则 E1-B01…E1-B05；
          `_SPEC/06` Q002（暂缓原因可并存、急性安全仅置顶不屏蔽其他原因）、
          IMP-1（F001=否 → 不启动；F001=待确认 → 分型存疑暂缓）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from app.core.exceptions import BusinessRuleError
from app.domain import enums, templates
from app.domain.states import ST00, ST10, ST20
from app.domain.transitions import validate_transition
from app.models.clinical import PreAssessmentInput, PreAssessmentResult

# 暂缓原因的处理优先级（数字小者优先，与锁定稿"急性安全置顶"一致）
_HOLD_PRIORITY: tuple[tuple[str, str, str], ...] = (
    (enums.HOLD_ACUTE, "E1-B02", "OUT-E1-HOLD-ACUTE"),
    (enums.HOLD_TYPE, "E1-B03", "OUT-E1-HOLD-TYPE"),
    (enums.HOLD_DATA, "E1-B04", "OUT-E1-HOLD-DATA"),
)

# 暂缓的返回位置说明（任务书§7 要求"暂缓必须同时给出原因、前置任务与返回位置"）
_RETURN_HINT = {
    enums.HOLD_ACUTE: "处理完成后返回本次预评估结论处；若已完成稳定化治疗，可由医生直接进入血糖稳定阶段。",
    enums.HOLD_TYPE: "复核分型后返回本次预评估结论处；明确仍为T2DM则直接进入完整评估，明确为其他类型则关闭本路径。",
    enums.HOLD_DATA: "资料补齐后返回本次预评估结论处，不新增资料补充临床节点。",
}


def evaluate_pre_assessment(current_state: str, data: PreAssessmentInput) -> PreAssessmentResult:
    """执行 60 秒预评估。

    参数:
        current_state (str): 患者当前状态（本单元应为 ST10）。
        data (PreAssessmentInput): 医生填写的核心五问与机会信息。

    返回:
        PreAssessmentResult: 三类主结论之一（进入完整评估 / 暂缓进入 / 当前不启动）。

    异常:
        BusinessRuleError: 选择暂缓但未填写前置事项时抛出（暂缓必须给出前置任务）。

    临床依据: 《临床流程锁定稿 v1.0》第五节。
    """
    # ---- 1) 患者明确拒绝：直接不启动（尊重患者意愿优先于其他分支）----
    if data.f005_refused == enums.YES:
        return _not_start(current_state, "患者明确拒绝进一步了解或参与本次缓解管理。")

    # ---- 2) 成人 T2DM 判断不成立：当前不启动 ----
    if data.f001_t2dm_established == enums.NO:
        return _not_start(current_state, "当前判断成人 2 型糖尿病不成立。")

    # ---- 3) 汇总全部暂缓原因（可多项并存，不互相屏蔽）----
    hold_reasons: list[str] = []
    if data.f002_acute_unsafe == enums.YES:
        hold_reasons.append(enums.HOLD_ACUTE)
    if data.f003_type_doubt == enums.YES:
        hold_reasons.append(enums.HOLD_TYPE)
    # F001=待确认 同样属于"分型尚需复核"，但不得重复计数
    if data.f001_t2dm_established == enums.PENDING and enums.HOLD_TYPE not in hold_reasons:
        hold_reasons.append(enums.HOLD_TYPE)
    if data.f004_treatment_context_sufficient == enums.NO:
        hold_reasons.append(enums.HOLD_DATA)

    if hold_reasons:
        # 暂缓必须给出前置任务：缺前置任务等于没有返回路径，属不完整结论
        if not (data.f012_pre_tasks or "").strip():
            raise BusinessRuleError(
                "选择暂缓进入时必须填写需要完成的前置事项。", code="PRE_TASKS_REQUIRED"
            )
        # 主规则按优先级取第一条命中的原因；其余原因保留在 hold_reasons 中一并展示
        primary = next(item for item in _HOLD_PRIORITY if item[0] in hold_reasons)
        reason, rule_id, template_id = primary
        target_state = ST10  # 暂缓为自环：患者仍停留在预评估环节
        validate_transition(current_state, target_state)
        return PreAssessmentResult(
            conclusion="暂缓进入",
            rule_id=rule_id,
            template_id=template_id,
            output_text=templates.render(template_id, pre_tasks=data.f012_pre_tasks or ""),
            target_state=target_state,
            hold_reasons=hold_reasons,
            return_hint=_RETURN_HINT[reason],
        )

    # ---- 4) 三项暂缓原因皆无：进入完整评估 ----
    target_state = ST20
    validate_transition(current_state, target_state)
    return PreAssessmentResult(
        conclusion="进入完整评估",
        rule_id="E1-B01",
        template_id="OUT-E1-ENTER",
        output_text=templates.render("OUT-E1-ENTER"),
        target_state=target_state,
        hold_reasons=[],
    )


def _not_start(current_state: str, reason: str) -> PreAssessmentResult:
    """构造"当前不启动"结论（转入常规糖尿病综合管理）。"""
    target_state = ST00
    validate_transition(current_state, target_state)
    return PreAssessmentResult(
        conclusion="当前不启动",
        rule_id="E1-B05",
        template_id="OUT-E1-NOSTART",
        output_text=templates.render("OUT-E1-NOSTART"),
        target_state=target_state,
        hold_reasons=[],
        return_hint=f"{reason}后续患者意愿或临床条件改变时，可重新发起60秒预评估。",
    )
