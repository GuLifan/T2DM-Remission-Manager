"""
模块名称：test_services_e1_e2.py
所属层级：测试（tests）
功能说明：事件1（60秒预评估）与事件2（完整评估）的分支测试。

覆盖内容：
    1. 预评估三类主结论与四种暂缓情形；
    2. **红线回归**：高 HbA1c、使用胰岛素、BMI 正常、C 肽缺失都不得导致排除；
    3. 暂缓原因可多项并存，且必须给出前置事项与返回位置；
    4. 完整评估一次性完成阶段、目标、干预与复评日期。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import BusinessRuleError
from app.domain import enums
from app.domain.states import ST00, ST10, ST20, ST31, ST32
from app.models.clinical import FullAssessmentInput, PreAssessmentInput
from app.services.full_assessment import evaluate_full_assessment
from app.services.pre_assessment import evaluate_pre_assessment

TODAY = date(2026, 9, 20)


def _pre(**overrides) -> PreAssessmentInput:
    """构造"三项暂缓皆无"的基线预评估输入（病例1 的特征）。"""
    base = {
        "f001_t2dm_established": enums.YES,
        "f002_acute_unsafe": enums.NO,
        "f003_type_doubt": enums.NO,
        "f004_treatment_context_sufficient": enums.YES,
        "f005_refused": enums.NO,
    }
    base.update(overrides)
    return PreAssessmentInput(**base)


# ===================== 事件1 =====================


def test_pre_assessment_enters_full_assessment() -> None:
    """核心五问全部通过 → 进入完整评估。"""
    result = evaluate_pre_assessment(ST10, _pre())
    assert result.conclusion == "进入完整评估"
    assert result.rule_id == "E1-B01"
    assert result.target_state == ST20
    assert result.template_id == "OUT-E1-ENTER"


def test_pre_assessment_acute_hold_is_primary_and_lists_all_reasons() -> None:
    """急性安全置顶，但分型存疑与资料不足同样要展示（不互相屏蔽）。"""
    result = evaluate_pre_assessment(
        ST10,
        _pre(
            f002_acute_unsafe=enums.YES,
            f003_type_doubt=enums.YES,
            f004_treatment_context_sufficient=enums.NO,
            f012_pre_tasks="先处理急性问题；同时复核分型、补充用药背景",
        ),
    )
    assert result.conclusion == "暂缓进入"
    assert result.rule_id == "E1-B02"  # 急性安全优先
    assert result.target_state == ST10  # 暂缓为自环
    assert result.hold_reasons == [enums.HOLD_ACUTE, enums.HOLD_TYPE, enums.HOLD_DATA]
    assert result.return_hint  # 暂缓必须给出返回位置


def test_pre_assessment_type_doubt_hold() -> None:
    """分型存疑 → 暂缓并说明复核后的两条去向。"""
    result = evaluate_pre_assessment(ST10, _pre(f003_type_doubt=enums.YES, f012_pre_tasks="查C肽与抗体"))
    assert result.rule_id == "E1-B03"
    assert "关闭本路径" in result.return_hint


def test_pre_assessment_t2dm_pending_counts_as_type_doubt() -> None:
    """F001=待确认 归入分型存疑暂缓（IMP-1）。"""
    result = evaluate_pre_assessment(
        ST10,
        _pre(f001_t2dm_established=enums.PENDING, f012_pre_tasks="复核诊断依据"),
    )
    assert result.rule_id == "E1-B03"
    assert result.hold_reasons == [enums.HOLD_TYPE]


def test_pre_assessment_data_insufficient_hold() -> None:
    """关键治疗背景不足 → 暂缓，补齐后回到预评估结论处（不新增临床节点）。"""
    result = evaluate_pre_assessment(
        ST10, _pre(f004_treatment_context_sufficient=enums.NO, f012_pre_tasks="补充当前用药与胰岛素背景")
    )
    assert result.rule_id == "E1-B04"
    assert "返回本次预评估结论处" in result.return_hint


def test_pre_assessment_hold_requires_pre_tasks() -> None:
    """选择暂缓却没有前置事项 → 结论不完整，必须报错。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_pre_assessment(ST10, _pre(f003_type_doubt=enums.YES, f012_pre_tasks="  "))
    assert "前置事项" in error.value.message


def test_pre_assessment_refusal_and_false_diagnosis_not_start() -> None:
    """明确拒绝 / T2DM 不成立 → 当前不启动，返回常规管理并保留再发起入口。"""
    refused = evaluate_pre_assessment(ST10, _pre(f005_refused=enums.YES))
    assert refused.conclusion == "当前不启动"
    assert refused.target_state == ST00

    not_t2dm = evaluate_pre_assessment(ST10, _pre(f001_t2dm_established=enums.NO))
    assert not_t2dm.conclusion == "当前不启动"
    assert not_t2dm.target_state == ST00


def test_red_line_high_hba1c_insulin_obesity_are_not_excluded() -> None:
    """红线回归：高 HbA1c、短期胰岛素强化、BMI 31 都不得导致排除（病例1）。"""
    result = evaluate_pre_assessment(
        ST10,
        _pre(f006_duration="4个月", f007_bmi_hint="BMI 31", f008_glucose_status="HbA1c 10.6%", f009_insulin="短期强化"),
    )
    assert result.conclusion == "进入完整评估"
    assert result.hold_reasons == []


def test_red_line_normal_bmi_and_missing_cpeptide_are_not_excluded() -> None:
    """红线回归：BMI 21、C 肽缺失、早期胰岛素都不得被判为"不适合缓解"（病例2 的特征）。"""
    result = evaluate_pre_assessment(
        ST10,
        _pre(f007_bmi_hint="BMI 21", f009_insulin="长期使用"),
    )
    # 没有分型疑点时不得因为 BMI 正常或使用胰岛素而暂缓/排除
    assert result.conclusion == "进入完整评估"


# ===================== 事件2 =====================


def _full(**overrides) -> FullAssessmentInput:
    """构造"启动-血糖稳定"的基线完整评估输入。"""
    base = {
        "f026_start": enums.START,
        "f027_stage": enums.STAGE_STABLE,
        "f028_stage_goal": "安全改善明显高血糖",
        "f029_interventions": ["结构化生活方式", "降糖治疗调整"],
    }
    base.update(overrides)
    return FullAssessmentInput(**base)


def test_full_assessment_starts_stable_stage_with_default_review() -> None:
    """启动血糖稳定阶段：一次性确定阶段、目标、干预与默认复评日期（12 周）。"""
    result = evaluate_full_assessment(ST20, _full(), TODAY)
    assert result.rule_id == "E2-B01"
    assert result.target_state == ST31
    assert result.stage == enums.STAGE_STABLE
    assert result.interventions == "结构化生活方式、降糖治疗调整"
    # 2026-09-20 + 12 周 = 2026-12-13
    assert result.next_review_date == date(2026, 12, 13)
    assert "{stage_goal}" not in result.output_text


def test_full_assessment_starts_induction_stage() -> None:
    """启动缓解诱导阶段 → ST32。"""
    result = evaluate_full_assessment(
        ST20, _full(f027_stage=enums.STAGE_INDUCTION, f028_stage_goal="实现有临床意义的体重下降"), TODAY
    )
    assert result.rule_id == "E2-B02"
    assert result.target_state == ST32
    assert "缓解诱导阶段" in result.output_text


def test_full_assessment_respects_doctor_specified_review_date() -> None:
    """医生指定复评日期时以医生为准（默认值只是缺省）。"""
    result = evaluate_full_assessment(ST20, _full(next_review_date=date(2026, 10, 1)), TODAY)
    assert result.next_review_date == date(2026, 10, 1)


def test_full_assessment_hold_and_not_start() -> None:
    """暂缓补充资料留在 ST20；当前不启动返回 ST00。"""
    held = evaluate_full_assessment(
        ST20, FullAssessmentInput(f026_start=enums.HOLD_SUPPLEMENT, f012_pre_tasks="补充C肽"), TODAY
    )
    assert held.rule_id == "E2-B03"
    assert held.target_state == ST20

    not_start = evaluate_full_assessment(ST20, FullAssessmentInput(f026_start=enums.NOT_START), TODAY)
    assert not_start.rule_id == "E2-B04"
    assert not_start.target_state == ST00


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"f027_stage": None}, "必须选择当前管理阶段"),
        ({"f028_stage_goal": "  "}, "主要阶段目标"),
        ({"f029_interventions": []}, "至少选择一种干预组合"),
    ],
)
def test_full_assessment_requires_complete_plan(overrides: dict, expected_message: str) -> None:
    """启动主动管理时必须一次性给出阶段、目标与干预（不得留下半成品计划）。"""
    with pytest.raises(BusinessRuleError) as error:
        evaluate_full_assessment(ST20, _full(**overrides), TODAY)
    assert expected_message in error.value.message
