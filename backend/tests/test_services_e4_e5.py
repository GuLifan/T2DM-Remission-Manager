"""
模块名称：test_services_e4_e5.py
所属层级：测试（tests）
功能说明：事件4（缓解判定）与事件5（缓解后复评）的分支测试。

覆盖内容：
    1. 五种系统状态输出（未到期 / 仍用药 / 客观满足 / 未达到 / 暂不能解释）；
    2. **红线回归**：系统绝不自动确认缓解——客观满足只是"请医生确认"；
    3. 替代指标必须完成独立复核才可用；
    4. 缓解后：维持 / 风险上升 / 因获益用药不可评价（≠复发）/ 缓解终止（≠缓解失败）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import BusinessRuleError
from app.domain import enums
from app.domain.states import ST20, ST31, ST32, ST40, ST50, ST60
from app.models.clinical import PostRemissionInput, RemissionJudgeInput
from app.services.post_remission import evaluate_post_remission
from app.services.remission_judge import check_remission, confirm_remission

TODAY = date(2026, 12, 1)
EARLIEST = date(2026, 11, 30)
REMISSION_DATE = date(2026, 12, 1)


def _judge(**overrides) -> RemissionJudgeInput:
    """构造基线判定输入（诊断可信、停药满 3 月、HbA1c 可靠且达标）。"""
    base = {
        "f041_diagnosis_credible": enums.YES,
        "f042_drug_free_3m": enums.YES,
        "f043_hba1c_reliable": enums.YES,
        "f014_hba1c": 6.2,
    }
    base.update(overrides)
    return RemissionJudgeInput(**base)


# ===================== 事件4 =====================


def test_not_due_blocks_and_returns_to_observation() -> None:
    """未到期：阻断确认，回到观察期。"""
    result = check_remission(
        ST50,
        _judge(),
        today=date(2026, 11, 1),
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert result.blocked is True
    assert result.rule_id == "E4-B01"
    assert result.target_state == ST40
    assert "2026-11-30" in result.output_text


def test_on_drug_blocks_drug_free_remission() -> None:
    """仍在使用降糖作用药物：阻断"无药缓解"确认，返回阶段由医生选择。"""
    result = check_remission(
        ST50, _judge(), today=TODAY, earliest_judge_date=EARLIEST, has_glucose_lowering_drug=True
    )
    assert result.blocked is True
    assert result.rule_id == "E4-B02"
    assert result.needs_target_stage is True
    assert "暂不能确认无药物缓解" in result.output_text


def test_objective_met_requires_doctor_confirmation_and_never_auto_confirms() -> None:
    """红线回归：客观满足只是"请医生确认"，系统绝不自动形成缓解结论。"""
    result = check_remission(
        ST50, _judge(), today=TODAY, earliest_judge_date=EARLIEST, has_glucose_lowering_drug=False
    )
    assert result.objective_met is True
    assert result.doctor_confirmation_required is True
    assert result.rule_id == "E4-B03"
    # 关键：目标状态仍是判定环节（ST50），不是缓解后复评（ST60）
    assert result.target_state == ST50
    assert result.target_state != ST60
    assert "请由医生确认" in result.output_text


def test_hba1c_at_or_above_threshold_is_not_met() -> None:
    """HbA1c 未达标准：回到事件3继续管理，不标记永久失败、不返回完整评估。"""
    result = check_remission(
        ST50,
        _judge(f014_hba1c=7.1),
        today=TODAY,
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert result.rule_id == "E4-B06"
    assert result.needs_target_stage is True
    assert "失败" not in result.output_text


def test_alternative_indicator_requires_independent_review() -> None:
    """替代指标未完成独立复核 → 不得形成"客观条件满足"。"""
    without_review = check_remission(
        ST50,
        _judge(f043_hba1c_reliable=enums.NO, f014_hba1c=None, f044_fpg=6.1, f046_independent_review=enums.NO),
        today=TODAY,
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert without_review.objective_met is False
    assert without_review.rule_id == "E4-B07"

    with_review = check_remission(
        ST50,
        _judge(f043_hba1c_reliable=enums.NO, f014_hba1c=None, f044_fpg=6.1, f046_independent_review=enums.YES),
        today=TODAY,
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert with_review.objective_met is True


def test_diagnosis_not_credible_returns_to_full_assessment() -> None:
    """F041=否（既往诊断明确不可信）→ 返回完整评估复核（Q-08 裁决）。"""
    result = check_remission(
        ST50,
        _judge(f041_diagnosis_credible=enums.NO),
        today=TODAY,
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert result.target_state == ST20
    assert result.rule_id == "E4-B07"


def test_diagnosis_pending_review_keeps_judgement_stage() -> None:
    """诊断或指标待复核 → 保留判定环节并生成定向复核任务。"""
    result = check_remission(
        ST50,
        _judge(f041_diagnosis_credible=enums.PENDING_REVIEW),
        today=TODAY,
        earliest_judge_date=EARLIEST,
        has_glucose_lowering_drug=False,
    )
    assert result.rule_id == "E4-B07"
    assert result.target_state == ST50
    assert "{pre_tasks}" not in result.output_text


def test_confirm_remission_moves_to_post_remission_with_followup() -> None:
    """医生确认 → 进入缓解后复评并生成随访任务。"""
    result = confirm_remission(ST50, "确认")
    assert result.rule_id == "E4-B04"
    assert result.target_state == ST60
    assert result.needs_followup_tasks is True


def test_confirm_requires_review_tasks_when_deferred() -> None:
    """暂不确认必须填写定向复核项目；保留在判定环节，不得写成未缓解。"""
    with pytest.raises(BusinessRuleError) as error:
        confirm_remission(ST50, "暂不确认")
    assert "定向复核" in error.value.message

    kept = confirm_remission(ST50, "暂不确认", pre_tasks="复核停药时间记录")
    assert kept.rule_id == "E4-B05"
    assert kept.target_state == ST50
    assert "未缓解" not in kept.output_text


# ===================== 事件5 =====================


def _post(**overrides) -> PostRemissionInput:
    """构造基线缓解后复评（维持）。"""
    base = {"f050_med_status": enums.MED_UNUSED, "f055_glucose_state": enums.GLUCOSE_BELOW_THRESHOLD}
    base.update(overrides)
    return PostRemissionInput(**base)


def test_maintain_keeps_remission_and_schedules_followup() -> None:
    """缓解维持：留在缓解状态，按随访节奏给出下次随访日期（6 个月后）。"""
    result = evaluate_post_remission(ST60, _post(), TODAY, remission_confirmed_date=REMISSION_DATE)
    assert result.rule_id == "E5-B01"
    assert result.target_state == ST60
    assert result.next_review_date == date(2027, 6, 1)


def test_risk_triggers_raise_risk_without_new_state() -> None:
    """风险上升：加强维持干预，不得创建"前复发期"等新状态。"""
    result = evaluate_post_remission(
        ST60, _post(f051_risk_triggers=["体重反弹"]), TODAY, remission_confirmed_date=REMISSION_DATE
    )
    assert result.rule_id == "E5-B02"
    assert result.target_state == ST60
    assert "复发风险上升" in result.output_text


def test_benefit_drug_makes_state_unevaluable_not_relapse() -> None:
    """红线回归：因获益用药 → 当前缓解状态不可评价，**不等同于复发**。"""
    result = evaluate_post_remission(
        ST60,
        _post(f050_med_status=enums.MED_FOR_ORGAN, target_stage=enums.STAGE_INDUCTION),
        TODAY,
        remission_confirmed_date=REMISSION_DATE,
    )
    assert result.rule_id == "E5-B03"
    assert result.target_state == ST32
    assert "不等同于复发" in result.output_text


def test_remission_termination_returns_to_review_not_entry() -> None:
    """缓解终止：直接返回事件3（阶段由医生选择），不得从预评估重新开始。"""
    result = evaluate_post_remission(
        ST60,
        _post(f055_glucose_state=enums.GLUCOSE_DIABETIC_RANGE, target_stage=enums.STAGE_STABLE),
        TODAY,
        remission_confirmed_date=REMISSION_DATE,
    )
    assert result.rule_id == "E5-B04"
    assert result.target_state == ST31


def test_remission_termination_with_new_evidence_returns_to_full_assessment() -> None:
    """缓解终止且出现新分型证据/重大变化 → 返回完整评估。"""
    result = evaluate_post_remission(
        ST60,
        _post(f055_glucose_state=enums.GLUCOSE_DIABETIC_RANGE, has_new_type_evidence=True),
        TODAY,
        remission_confirmed_date=REMISSION_DATE,
    )
    assert result.target_state == ST20


def test_termination_requires_doctor_chosen_stage() -> None:
    """返回主动管理时必须由医生选择阶段。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_post_remission(ST60, _post(f055_glucose_state=enums.GLUCOSE_DIABETIC_RANGE), TODAY)
    assert "必须由医生选择管理阶段" in error.value.message


def test_unexplained_glucose_keeps_remission_with_review_task() -> None:
    """血糖暂不能解释 → 保留缓解记录并提示定向复核（不新增临床状态）。"""
    result = evaluate_post_remission(
        ST60, _post(f055_glucose_state=enums.GLUCOSE_UNEXPLAINED), TODAY, remission_confirmed_date=REMISSION_DATE
    )
    assert result.rule_id == "SYS-E5-REVIEW"
    assert result.target_state == ST60
