"""
模块名称：observation.py
所属层级：临床服务层（services）
功能说明：实现"单元4｜缓解观察期"（系统自动状态）。

关键设计：
    - 观察期由"停用最后一种降糖药"自动触发，**不存在"进入观察期"按钮，也没有停药确认页**；
    - 系统只计算最早可判定日期并提示，到期后开放判定入口；
    - 因高血糖重新用药（A1-B04）或因器官/体重获益用药（A1-B05）时退出观察期。

临床依据：《临床流程锁定稿 v1.0》第八节；规则 A1-B01…A1-B05；
          `_SPEC/06` Q001（日历月加法钳位）、Q004（获益用药不等同失败或复发）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.domain import enums, templates
from app.domain.states import ST31, ST32, state_name
from app.domain.transitions import validate_transition
from app.models.clinical import MedicationRestartInput, MedicationRestartResult, ObservationStatus
from app.utils.date_utils import compute_earliest_judge_date


def get_observation_status(
    *,
    last_med_stop_date: date | None,
    lifestyle_start_date: date | None,
    surgery_date: date | None,
    today: date,
) -> ObservationStatus:
    """计算并返回观察期状态（未到期 / 已到期）。

    参数:
        last_med_stop_date: 最后一种降糖作用药物的停用日期（观察期起点）。
        lifestyle_start_date / surgery_date: 其他时间锚点（如适用）。
        today (date): 当前日期（由 Clock 注入）。

    返回:
        ObservationStatus: 含最早可判定日期、是否到期与对应的自然语言提示。
    """
    earliest = compute_earliest_judge_date(
        last_med_stop_date=last_med_stop_date,
        lifestyle_start_date=lifestyle_start_date,
        surgery_date=surgery_date,
    )
    # 到期判定：当前日期不早于最早可判定日期
    due = earliest is not None and today >= earliest
    if due:
        template_id = "OUT-A1-DUE"
        rule_id = "A1-B03"
        output_text = templates.render("OUT-A1-DUE")
    else:
        template_id = "OUT-A1-WAIT"
        rule_id = "A1-B02"
        # 最早可判定日期尚未计算出来时，提示语中给出占位说明而不是空白
        output_text = templates.render(
            "OUT-A1-WAIT",
            earliest_assessment_date=earliest.isoformat() if earliest else "待确定（缺少停药日期）",
        )
    return ObservationStatus(
        stage=state_name("ST40"),
        last_med_stop_date=last_med_stop_date,
        lifestyle_start_date=lifestyle_start_date,
        surgery_date=surgery_date,
        earliest_judge_date=earliest,
        due=due,
        rule_id=rule_id,
        template_id=template_id,
        output_text=output_text,
    )


def evaluate_medication_restart(
    current_state: str, data: MedicationRestartInput
) -> MedicationRestartResult:
    """观察期重新用药：退出观察期并返回阶段复评。

    分支：
        - 因高血糖 → A1-B04（结束观察期，返回事件3，阶段由医生选择）；
        - 因器官获益 / 体重获益 → A1-B05（结束"可判定的无药观察"，保留历史，
          **不等同于缓解失败或复发**）。

    参数:
        current_state (str): 当前状态（本单元应为 ST40）。
        data (MedicationRestartInput): 重新用药原因与返回阶段。

    返回:
        MedicationRestartResult: 结论与目标状态。
    """
    if data.target_stage not in enums.STAGES:
        # 返回阶段由医生选择（`_SPEC/06` 裁决），系统不得替他决定
        raise ValueError("返回阶段必须是血糖稳定或缓解诱导。")
    target_state = ST31 if data.target_stage == enums.STAGE_STABLE else ST32
    validate_transition(current_state, target_state)

    if data.f037_reason == enums.RESTART_HYPERGLYCEMIA:
        rule_id, template_id = "A1-B04", "OUT-A1-RESTART-HIGH"
    elif data.f037_reason in (enums.RESTART_ORGAN, enums.RESTART_WEIGHT):
        rule_id, template_id = "A1-B05", "OUT-A1-RESTART-BENEFIT"
    else:
        # "其他"原因：按退出可判定观察处理，同样保留历史记录
        rule_id, template_id = "A1-B05", "OUT-A1-RESTART-BENEFIT"

    return MedicationRestartResult(
        rule_id=rule_id,
        template_id=template_id,
        output_text=templates.render(template_id),
        target_state=target_state,
        stage=data.target_stage,
    )
