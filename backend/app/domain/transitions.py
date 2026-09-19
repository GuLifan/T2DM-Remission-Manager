"""
模块名称：transitions.py
所属层级：领域层（domain）
功能说明：合法状态转换表——本项目**状态转换的唯一真源**。

每条转换声明四件事：由哪条规则触发、从哪些状态出发、到哪个状态、需要哪些必需输入、
以及会产生什么副作用。服务层在返回结果前调用 `validate_transition()`，
任何未登记的转换一律拒绝，杜绝"非法跳转"与"无出口状态"。

临床依据：《临床流程锁定稿 v1.0》第四～十一节；`_SPEC/03` 第二节状态出口矩阵；
          `_SPEC/06` 裁决（F041=否 返回 ST20、A1-B04/E5-B03 返回阶段由医生选择）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现（自 V0.1 矩阵继承，未增删改转换）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import BusinessRuleError
from app.domain.states import ST00, ST10, ST20, ST31, ST32, ST40, ST50, ST60, ST99, state_name


@dataclass(frozen=True)
class Transition:
    """一条合法状态转换。"""

    rule_id: str
    source: tuple[str, ...]
    target: str
    template_id: str | None = None
    # 必需输入字段（缺失时服务层应抛业务异常，而不是产生半成品事件）
    required_fields: tuple[str, ...] = ()
    # 副作用标识：供接口层决定要额外更新哪些患者字段
    side_effects: tuple[str, ...] = field(default_factory=tuple)
    label: str = ""


# ===== 全部合法转换（按状态分组，便于人工核对）=====
TRANSITIONS: tuple[Transition, ...] = (
    # --- 常规管理：条件改变后重新发起预评估 ---
    Transition("REOPEN", (ST00,), ST10, label="重新发起60秒预评估"),
    # --- 事件1：60秒预评估 ---
    Transition("E1-B01", (ST10,), ST20, "OUT-E1-ENTER", label="进入完整评估"),
    Transition("E1-B02", (ST10,), ST10, "OUT-E1-HOLD-ACUTE", ("f012_pre_tasks",), label="急性安全暂缓"),
    Transition("E1-B03", (ST10,), ST10, "OUT-E1-HOLD-TYPE", ("f012_pre_tasks",), label="分型存疑暂缓"),
    Transition("E1-B04", (ST10,), ST10, "OUT-E1-HOLD-DATA", ("f012_pre_tasks",), label="关键治疗背景不足暂缓"),
    Transition("E1-B05", (ST10,), ST00, "OUT-E1-NOSTART", label="当前不启动"),
    Transition("SYS-E1-CLOSE", (ST10,), ST99, "SYS-E1-CLOSE", label="分型复核为其他类型，关闭本路径"),
    # --- 事件2：完整评估并形成主动管理计划 ---
    Transition("E2-B01", (ST20,), ST31, "OUT-E2-STABLE", ("f026_start", "f027_stage", "f028_stage_goal", "f029_interventions"), ("set_stage", "set_goal", "set_interventions", "set_next_review"), label="启动-血糖稳定"),
    Transition("E2-B02", (ST20,), ST32, "OUT-E2-INDUCTION", ("f026_start", "f027_stage", "f028_stage_goal", "f029_interventions"), ("set_stage", "set_goal", "set_interventions", "set_next_review"), label="启动-缓解诱导"),
    Transition("E2-B03", (ST20,), ST20, "OUT-E2-HOLD", ("f012_pre_tasks",), label="暂缓补充关键资料"),
    Transition("E2-B04", (ST20,), ST00, "OUT-E2-NOSTART", label="当前不启动主动管理"),
    # --- 事件3：阶段复评与治疗调整（血糖稳定阶段出发）---
    # 自环必须为两个阶段各登记一条：血糖稳定阶段留在 ST31，缓解诱导阶段留在 ST32
    Transition("E3-B01", (ST31,), ST31, "OUT-E3-CONTINUE", ("next_review_date",), ("set_next_review",), label="继续当前阶段（血糖稳定，自环）"),
    Transition("E3-B01", (ST32,), ST32, "OUT-E3-CONTINUE", ("next_review_date",), ("set_next_review",), label="继续当前阶段（缓解诱导，自环）"),
    Transition("E3-B02", (ST31,), ST31, "OUT-E3-ADJUST", ("adjustment_summary",), ("set_next_review",), label="调整方案或目标（血糖稳定，留在当前阶段）"),
    Transition("E3-B02", (ST32,), ST32, "OUT-E3-ADJUST", ("adjustment_summary",), ("set_next_review",), label="调整方案或目标（缓解诱导，留在当前阶段）"),
    Transition("E3-B03", (ST31,), ST32, "OUT-E3-SWITCH", ("new_stage", "stage_goal"), ("set_stage", "set_goal", "set_next_review"), label="阶段互转：血糖稳定→缓解诱导"),
    Transition("E3-B04", (ST32,), ST31, "OUT-E3-SWITCH", ("new_stage", "stage_goal"), ("set_stage", "set_goal", "set_next_review"), label="阶段互转：缓解诱导→血糖稳定"),
    Transition("E3-B05", (ST31, ST32), ST00, "OUT-E3-END", ("end_reason",), ("clear_stage",), label="结束主动管理"),
    Transition("E3-B06", (ST31,), ST31, "OUT-E3-ON-TREATMENT", ("f053_has_drug", "f054_purpose"), ("update_drug_status",), label="治疗下血糖达标且仍用获益药（血糖稳定，留在当前阶段）"),
    Transition("E3-B06", (ST32,), ST32, "OUT-E3-ON-TREATMENT", ("f053_has_drug", "f054_purpose"), ("update_drug_status",), label="治疗下血糖达标且仍用获益药（缓解诱导，留在当前阶段）"),
    Transition("E3-B07", (ST31, ST32), ST40, "OUT-E3-OBS-ENTER", ("f035_stop_last_med", "f036_stop_date"), ("record_med_stop_date", "enter_observation", "compute_earliest_judge_date"), label="停用最后一种药→自动进入观察期"),
    Transition("E3-B08", (ST31, ST32), ST31, "OUT-E3-ADJUST", ("f056_uncontrolled",), ("set_stage", "set_next_review"), label="明显血糖失控→返回血糖稳定"),
    # --- 观察期（系统自动状态）---
    Transition("A1-B01", (ST40,), ST40, label="观察期状态展示（自环）"),
    Transition("A1-B02", (ST40,), ST40, "OUT-A1-WAIT", label="观察期未到期提示"),
    Transition("A1-B03", (ST40,), ST50, "OUT-A1-DUE", label="到期开放缓解判定"),
    Transition("A1-B04", (ST40,), ST31, "OUT-A1-RESTART-HIGH", ("f037_reason",), ("clear_observation",), label="因高血糖重新用药→返回阶段复评（血糖稳定）"),
    Transition("A1-B04", (ST40,), ST32, "OUT-A1-RESTART-HIGH", ("f037_reason",), ("clear_observation",), label="因高血糖重新用药→返回阶段复评（缓解诱导）"),
    Transition("A1-B05", (ST40,), ST31, "OUT-A1-RESTART-BENEFIT", ("f037_reason",), ("clear_observation",), label="因器官/体重获益用药→返回阶段复评（血糖稳定）"),
    Transition("A1-B05", (ST40,), ST32, "OUT-A1-RESTART-BENEFIT", ("f037_reason",), ("clear_observation",), label="因器官/体重获益用药→返回阶段复评（缓解诱导）"),
    # --- 事件4：缓解判定 ---
    Transition("E4-B01", (ST50,), ST40, "OUT-E4-NOT-DUE", label="未到期→回到观察期"),
    Transition("E4-B02", (ST50,), ST31, "OUT-E4-ON-DRUG", ("f054_purpose",), ("set_stage",), label="仍用药→返回阶段复评（血糖稳定）"),
    Transition("E4-B02", (ST50,), ST32, "OUT-E4-ON-DRUG", ("f054_purpose",), ("set_stage",), label="仍用药→返回阶段复评（缓解诱导）"),
    Transition("E4-B03", (ST50,), ST50, "OUT-E4-OBJECTIVE-MET", label="客观条件核对（无状态变化）"),
    Transition("E4-B04", (ST50,), ST60, "OUT-E4-CONFIRMED", ("f048_confirm",), ("record_remission_date", "enter_post_remission"), label="医生确认缓解→进入缓解后复评"),
    Transition("E4-B05", (ST50,), ST50, "OUT-E4-UNCERTAIN", ("f012_pre_tasks",), label="客观满足但医生暂不确认→定向复核"),
    Transition("E4-B06", (ST50,), ST31, "OUT-E4-NOT-MET", (), ("set_stage",), label="未达到标准→返回阶段复评（血糖稳定）"),
    Transition("E4-B06", (ST50,), ST32, "OUT-E4-NOT-MET", (), ("set_stage",), label="未达到标准→返回阶段复评（缓解诱导）"),
    Transition("E4-B07", (ST50,), ST50, "OUT-E4-UNCERTAIN", ("f012_pre_tasks",), label="暂不能解释→保留判定环节"),
    Transition("E4-B07", (ST50,), ST20, "OUT-E4-UNCERTAIN", (), label="F041=否（既往诊断不可信）→返回完整评估复核"),
    # --- 事件5：缓解后复评 ---
    Transition("E5-B01", (ST60,), ST60, "OUT-E5-MAINTAIN", ("next_review_date",), ("set_next_review",), label="缓解维持"),
    Transition("E5-B02", (ST60,), ST60, "OUT-E5-RISK", ("next_review_date",), ("set_next_review",), label="维持但风险上升"),
    Transition("E5-B03", (ST60,), ST31, "OUT-E5-UNEVALUABLE", ("target_stage",), ("set_stage",), label="不可评价（获益用药）→返回阶段复评（血糖稳定）"),
    Transition("E5-B03", (ST60,), ST32, "OUT-E5-UNEVALUABLE", ("target_stage",), ("set_stage",), label="不可评价（获益用药）→返回阶段复评（缓解诱导）"),
    Transition("E5-B04", (ST60,), ST31, "OUT-E5-END", ("target_stage",), ("clear_remission", "set_stage"), label="缓解终止→返回阶段复评（血糖稳定）"),
    Transition("E5-B04", (ST60,), ST32, "OUT-E5-END", ("target_stage",), ("clear_remission", "set_stage"), label="缓解终止→返回阶段复评（缓解诱导）"),
    Transition("E5-B04", (ST60,), ST20, "OUT-E5-END", ("target_stage",), ("clear_remission",), label="缓解终止（新分型证据/重大临床变化）→返回完整评估"),
    Transition("SYS-E5-REVIEW", (ST60,), ST60, "SYS-E5-REVIEW", label="血糖暂不能解释→保留缓解状态并定向复核"),
)

# 由转换表推导的"源状态 → 允许目标状态集合"，供快速校验与测试使用
LEGAL_TRANSITIONS: dict[str, set[str]] = {}
for _item in TRANSITIONS:
    for _source in _item.source:
        LEGAL_TRANSITIONS.setdefault(_source, set()).add(_item.target)


def validate_transition(source_state: str, target_state: str) -> None:
    """校验一次状态转换是否合法。

    为什么集中校验：临床流程要求"任何状态都有合法出口、没有非法跳转"，
    所有服务层跳转统一经过本函数，保证状态机是唯一真源。

    参数:
        source_state (str): 转换前状态代码。
        target_state (str): 转换后状态代码。

    异常:
        BusinessRuleError: 源状态未知或转换未登记（消息为医生可读的自然语言）。
    """
    allowed = LEGAL_TRANSITIONS.get(source_state)
    if allowed is None:
        raise BusinessRuleError("当前患者状态无法识别，请联系系统维护人员。", code="UNKNOWN_STATE")
    if target_state not in allowed:
        raise BusinessRuleError(
            f"当前流程不允许从“{state_name(source_state)}”直接进入“{state_name(target_state)}”。",
            code="ILLEGAL_TRANSITION",
        )


def transitions_for(rule_id: str) -> tuple[Transition, ...]:
    """按规则 ID 查询转换定义（供测试与接口层查询必需字段/副作用）。"""
    return tuple(item for item in TRANSITIONS if item.rule_id == rule_id)


def dead_end_states() -> list[str]:
    """返回没有任何出口的状态列表（终态 ST99 除外）。

    这是"无出口检查"的实现：首轮验收要求每个状态都能走到下一步、常规管理或关闭路径。
    """
    return [
        state
        for state, targets in LEGAL_TRANSITIONS.items()
        if state != ST99 and not targets
    ]
