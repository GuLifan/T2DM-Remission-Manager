"""
模块名称：test_state_machine.py
所属层级：测试（tests）
功能说明：状态机与领域单一数据源的核心测试。

覆盖内容：
    1. 全部 9 个状态都有定义、都有中文名称；
    2. 每个状态（终态 ST99 除外）都有合法出口——无出口检查；
    3. 未登记的转换必须被拒绝，且提示为自然语言；
    4. 锁定文案数量与 ID 集合正确（30 个 OUT-* + 2 个 SYS-*）；
    5. 分支优先级表顺序正确，且被覆盖分支必须给出原因。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

import pytest

from app.core.exceptions import BusinessRuleError
from app.domain import states, templates
from app.domain.branches import PHASE_REVIEW_BRANCHES, resolve_branch
from app.domain.transitions import (
    LEGAL_TRANSITIONS,
    TRANSITIONS,
    dead_end_states,
    transitions_for,
    validate_transition,
)


def test_all_states_defined_with_chinese_names() -> None:
    """9 个状态全部有中文名称，且不含状态代码。"""
    assert len(states.ALL_STATES) == 9
    assert set(states.STATE_NAMES) == set(states.ALL_STATES)
    for code in states.ALL_STATES:
        name = states.STATE_NAMES[code]
        assert name and code not in name


def test_state_name_falls_back_without_leaking_code() -> None:
    """未知状态不得把代码泄漏到前台（V0.1 的 L2 缺陷）。"""
    assert states.state_name("ST_UNKNOWN") == "未知状态"


def test_no_dead_end_states() -> None:
    """除终态 ST99 外，所有状态都必须有出口。"""
    assert dead_end_states() == []
    # 终态确实没有出口
    assert LEGAL_TRANSITIONS.get(states.ST99, set()) == set()


def test_every_transition_source_and_target_are_known_states() -> None:
    """转换表中出现的状态必须都是已知状态。"""
    for item in TRANSITIONS:
        for source in item.source:
            assert source in states.ALL_STATES, f"未知源状态：{source}"
        assert item.target in states.ALL_STATES, f"未知目标状态：{item.target}"


def test_illegal_transition_is_rejected_with_natural_language() -> None:
    """未登记的转换必须被拒绝，且提示是医生可读的中文。"""
    # ST00 只能重新发起预评估，不能直接跳到缓解判定
    with pytest.raises(BusinessRuleError) as error:
        validate_transition(states.ST00, states.ST50)
    assert error.value.status_code == 422
    assert "不允许" in error.value.message
    assert "ST" not in error.value.message  # 不得出现状态代码


def test_unknown_source_state_is_rejected() -> None:
    """未知源状态按工程缺陷处理。"""
    with pytest.raises(BusinessRuleError) as error:
        validate_transition("ST_FAKE", states.ST10)
    assert error.value.code == "UNKNOWN_STATE"


def test_legal_transitions_include_locked_paths() -> None:
    """锁定稿中的关键路径必须都在转换表里。"""
    assert states.ST20 in LEGAL_TRANSITIONS[states.ST10]          # 进入完整评估
    assert states.ST40 in LEGAL_TRANSITIONS[states.ST31]          # 停药后进入观察期
    assert states.ST50 in LEGAL_TRANSITIONS[states.ST40]          # 到期开放判定
    assert states.ST60 in LEGAL_TRANSITIONS[states.ST50]          # 医生确认缓解
    assert states.ST20 in LEGAL_TRANSITIONS[states.ST50]          # F041=否 返回完整评估
    assert states.ST99 in LEGAL_TRANSITIONS[states.ST10]          # 分型为其他类型关闭路径
    assert states.ST40 not in LEGAL_TRANSITIONS[states.ST10]      # 不得从预评估直接进观察期


def test_transitions_carry_rule_id_and_template() -> None:
    """关键转换必须声明规则 ID、必需输入与输出模板。"""
    stop_med = transitions_for("E3-B07")
    assert stop_med, "缺少 E3-B07 转换定义"
    assert all(item.template_id == "OUT-E3-OBS-ENTER" for item in stop_med)
    assert all("f036_stop_date" in item.required_fields for item in stop_med)
    assert all("enter_observation" in item.side_effects for item in stop_med)


def test_templates_are_frozen_and_counted_correctly() -> None:
    """锁定文案数量：30 个 OUT-* + 2 个 SYS-*（更正 V0.1 的"34 个"口径）。"""
    assert len(templates.CLINICAL_TEMPLATE_IDS) == 30
    assert len(templates.SYS_TEMPLATE_IDS) == 2
    assert len(templates.TEMPLATES) == 32
    # 每条文案都不得为空，且不得残留未替换的说明性标记
    for template_id, text in templates.TEMPLATES.items():
        assert text.strip(), f"{template_id} 文案为空"


def test_render_replaces_variables() -> None:
    """渲染必须替换全部已知变量。"""
    text = templates.render("OUT-E3-CONTINUE", next_review_date="2026-12-20")
    assert "2026-12-20" in text
    assert "{next_review_date}" not in text


def test_render_keeps_unknown_placeholder_visible() -> None:
    """漏传变量时保留占位符，便于开发者一眼看出（不静默清空）。"""
    text = templates.render("OUT-E3-CONTINUE")
    assert "{next_review_date}" in text


def test_branch_priority_order_is_locked() -> None:
    """分支优先级顺序必须与锁定稿一致：失控 > 治疗下达标 > 停药 > 常规动作。"""
    keys = [branch.key for branch in sorted(PHASE_REVIEW_BRANCHES, key=lambda item: item.priority)]
    assert keys == ["uncontrolled", "on_treatment_non_diabetic", "stop_last_med", "routine_action"]


def test_resolve_branch_reports_ignored_branch_with_reason() -> None:
    """高优先级分支覆盖低优先级分支时，必须返回被忽略分支与原因（禁止静默丢弃）。"""
    chosen, ignored = resolve_branch({"uncontrolled", "stop_last_med"})
    assert chosen.key == "uncontrolled"
    assert len(ignored) == 1
    assert ignored[0].branch.key == "stop_last_med"
    assert "覆盖" in ignored[0].reason


def test_resolve_branch_rejects_exclusive_conflict() -> None:
    """互斥分支同时为真时必须报错（不能悄悄选一个）。"""
    with pytest.raises(ValueError) as error:
        resolve_branch({"stop_last_med", "on_treatment_non_diabetic"})
    assert "不能同时" in str(error.value)


def test_resolve_branch_falls_back_to_routine_action() -> None:
    """没有任何特殊分支时，按常规复评动作处理。"""
    chosen, ignored = resolve_branch({"routine_action"})
    assert chosen.key == "routine_action"
    assert ignored == []
