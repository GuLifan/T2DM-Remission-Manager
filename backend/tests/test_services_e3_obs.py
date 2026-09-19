"""
模块名称：test_services_e3_obs.py
所属层级：测试（tests）
功能说明：事件3（阶段复评）与观察期的分支测试。

覆盖内容：
    1. 常规动作四条路径；
    2. **分支优先级**：失控 > 治疗下达标 > 停药 > 常规，且被覆盖分支必须给出原因；
    3. **红线回归**：获益用药不得提示停药、不得进入观察期；
    4. 停药自动进入观察期（无"停药确认页面"）；
    5. 观察期到期判定与重新用药退出。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import BusinessRuleError
from app.domain import enums
from app.domain.states import ST00, ST31, ST32, ST40, ST50
from app.models.clinical import MedicationRestartInput, PhaseReviewInput
from app.services.observation import evaluate_medication_restart, get_observation_status
from app.services.phase_review import evaluate_phase_review

TODAY = date(2026, 9, 20)


def _review(**overrides) -> PhaseReviewInput:
    """构造基线复评输入（继续当前阶段）。"""
    base = {"f034_action": enums.ACT_CONTINUE}
    base.update(overrides)
    return PhaseReviewInput(**base)


def test_continue_keeps_stage_with_default_review_date() -> None:
    """继续当前阶段：留在原阶段，默认 12 周后复评。"""
    result = evaluate_phase_review(ST31, _review(), TODAY)
    assert result.rule_id == "E3-B01"
    assert result.target_state == ST31
    assert result.next_review_date == date(2026, 12, 13)


def test_adjust_stays_in_stage_and_requires_summary() -> None:
    """调整方案留在当前阶段（不重新完整评估），且必须写调整内容。"""
    result = evaluate_phase_review(
        ST32, _review(f034_action=enums.ACT_ADJUST, adjustment_summary="加用体重管理药物"), TODAY
    )
    assert result.rule_id == "E3-B02"
    assert result.target_state == ST32
    assert "加用体重管理药物" in result.output_text

    with pytest.raises(BusinessRuleError) as error:
        evaluate_phase_review(ST32, _review(f034_action=enums.ACT_ADJUST), TODAY)
    assert "调整内容" in error.value.message


def test_switch_stage_between_two_stages() -> None:
    """阶段互转必须由医生确认，且方向决定规则 ID。"""
    to_induction = evaluate_phase_review(
        ST31,
        _review(f034_action=enums.ACT_SWITCH, new_stage=enums.STAGE_INDUCTION, stage_goal="减重 10%"),
        TODAY,
    )
    assert to_induction.rule_id == "E3-B03"
    assert to_induction.target_state == ST32

    to_stable = evaluate_phase_review(
        ST32,
        _review(f034_action=enums.ACT_SWITCH, new_stage=enums.STAGE_STABLE, stage_goal="安全降糖"),
        TODAY,
    )
    assert to_stable.rule_id == "E3-B04"
    assert to_stable.target_state == ST31


def test_switch_to_same_stage_is_rejected() -> None:
    """新阶段与当前相同不得当作"转换"。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_phase_review(
            ST31,
            _review(f034_action=enums.ACT_SWITCH, new_stage=enums.STAGE_STABLE, stage_goal="x"),
            TODAY,
        )
    assert "无需转换" in error.value.message


def test_end_active_management_returns_regular_care() -> None:
    """结束主动管理 → 返回常规管理并保留再发起入口。"""
    result = evaluate_phase_review(ST31, _review(f034_action=enums.ACT_END, end_reason="患者要求"), TODAY)
    assert result.rule_id == "E3-B05"
    assert result.target_state == ST00


def test_red_line_benefit_drug_does_not_suggest_stopping() -> None:
    """红线回归（病例3）：治疗下达标且用获益药 → 不建议停药、不进入观察期。"""
    result = evaluate_phase_review(
        ST32,
        _review(
            f053_has_drug=True,
            f054_purpose=enums.PURPOSE_ORGAN,
            glucose_non_diabetic=True,
        ),
        TODAY,
    )
    assert result.rule_id == "E3-B06"
    assert result.target_state == ST32          # 留在当前阶段
    assert result.entered_observation is False  # 不进入观察期
    assert "不建议为获得缓解标签而停药" in result.output_text


def test_stop_last_med_enters_observation_automatically() -> None:
    """停用最后一种降糖药 → 系统自动进入观察期并算出最早可判定日期。"""
    result = evaluate_phase_review(
        ST32,
        _review(f035_stop_last_med=True, f036_stop_date=date(2026, 8, 31)),
        TODAY,
    )
    assert result.rule_id == "E3-B07"
    assert result.target_state == ST40
    assert result.entered_observation is True
    # 月末钳位：8月31日 + 3 个日历月 = 11月30日
    assert result.earliest_judge_date == date(2026, 11, 30)


def test_stop_last_med_requires_stop_date() -> None:
    """停药必须记录日期（否则观察期无法计时）。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_phase_review(ST31, _review(f035_stop_last_med=True, f036_stop_date=None), TODAY)
    assert "停药日期" in error.value.message


def test_uncontrolled_has_highest_priority_and_reports_ignored_branch() -> None:
    """优先级：明显失控 > 停药；被覆盖的停药分支必须说明原因，不得静默丢弃。"""
    result = evaluate_phase_review(
        ST32,
        _review(f056_uncontrolled=True, f035_stop_last_med=True, f036_stop_date=date(2026, 9, 1)),
        TODAY,
    )
    assert result.rule_id == "E3-B08"
    assert result.target_state == ST31          # 失控返回血糖稳定阶段
    assert result.entered_observation is False  # 本次不进入观察期
    assert len(result.ignored_branches) == 1
    assert "停用最后一种具有降糖作用的药物" in result.ignored_branches[0]
    assert "覆盖" in result.ignored_branches[0]


def test_exclusive_branch_conflict_is_rejected_with_friendly_message() -> None:
    """互斥分支同时为真 → 明确报错，而不是悄悄选一个。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_phase_review(
            ST31,
            _review(
                f035_stop_last_med=True,
                f036_stop_date=date(2026, 9, 1),
                f053_has_drug=True,
                f054_purpose=enums.PURPOSE_ORGAN,
                glucose_non_diabetic=True,
            ),
            TODAY,
        )
    assert error.value.code == "BRANCH_CONFLICT"
    assert "不能同时" in error.value.message


# ===================== 观察期 =====================


def test_observation_not_due_shows_earliest_date() -> None:
    """未到期：显示最早可判定日期并保留观察。"""
    status = get_observation_status(
        last_med_stop_date=date(2026, 8, 31),
        lifestyle_start_date=None,
        surgery_date=None,
        today=date(2026, 10, 1),
    )
    assert status.due is False
    assert status.rule_id == "A1-B02"
    assert status.earliest_judge_date == date(2026, 11, 30)
    assert "2026-11-30" in status.output_text


def test_observation_due_opens_judgement() -> None:
    """到期：提示可进入正式缓解判定。"""
    status = get_observation_status(
        last_med_stop_date=date(2026, 8, 31),
        lifestyle_start_date=None,
        surgery_date=None,
        today=date(2026, 12, 1),
    )
    assert status.due is True
    assert status.rule_id == "A1-B03"


def test_observation_respects_later_anchor() -> None:
    """生活方式干预满 6 个月更晚时，以其为准（取 MAX）。"""
    status = get_observation_status(
        last_med_stop_date=date(2026, 8, 1),       # +3 月 = 11月1日
        lifestyle_start_date=date(2026, 7, 1),     # +6 月 = 2027年1月1日（更晚）
        surgery_date=None,
        today=date(2026, 11, 15),
    )
    assert status.earliest_judge_date == date(2027, 1, 1)
    assert status.due is False


def test_observation_restart_by_hyperglycemia_returns_to_review() -> None:
    """因高血糖重新用药 → 退出观察期，返回阶段复评（阶段由医生选择）。"""
    result = evaluate_medication_restart(
        ST40,
        MedicationRestartInput(f037_reason=enums.RESTART_HYPERGLYCEMIA, target_stage=enums.STAGE_STABLE),
    )
    assert result.rule_id == "A1-B04"
    assert result.target_state == ST31


def test_observation_restart_by_benefit_drug_is_not_relapse() -> None:
    """因获益用药退出可判定观察：不等同于缓解失败或复发。"""
    result = evaluate_medication_restart(
        ST40,
        MedicationRestartInput(f037_reason=enums.RESTART_ORGAN, target_stage=enums.STAGE_INDUCTION),
    )
    assert result.rule_id == "A1-B05"
    assert result.target_state == ST32
    assert "不等同于缓解失败或复发" in result.output_text


def test_observation_restart_requires_doctor_chosen_stage() -> None:
    """返回阶段必须由医生选择，系统不得替他决定。"""
    with pytest.raises(ValueError):
        evaluate_medication_restart(
            ST40, MedicationRestartInput(f037_reason=enums.RESTART_HYPERGLYCEMIA, target_stage="随便")
        )


def test_stop_med_path_never_passes_through_judgement() -> None:
    """停药只进入观察期（ST40），不得直接跳到判定（ST50）——无"停药确认页面"的代码证据。"""
    result = evaluate_phase_review(
        ST31, _review(f035_stop_last_med=True, f036_stop_date=date(2026, 9, 1)), TODAY
    )
    assert result.target_state == ST40
    assert result.target_state != ST50
