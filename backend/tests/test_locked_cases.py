"""
模块名称：test_locked_cases.py
所属层级：测试（tests）
功能说明：3 个锁定病例的端到端走查（验收基线，`_SPEC/05` 第二节）。

每个病例都按"预评估 → 完整评估 → 复评 → 观察/判定 → 缓解后"的真实顺序推进，
并在关键节点断言"必须避免的错误"（锁定稿§12）：
    病例1：不得因 HbA1c 10.6% 或胰岛素强化而排除；停药后自动进入观察期。
    病例2：不得因 BMI 正常、早期胰岛素、C 肽缺失而判"不适合缓解"；暂缓必须给返回位置。
    病例3：不得提示停用器官保护药；输出"治疗下血糖已达非糖尿病范围，暂不能判定缓解"。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.domain import enums
from app.domain.states import ST10, ST20, ST31, ST32, ST40, ST50, ST60, ST99
from app.domain.transitions import LEGAL_TRANSITIONS
from app.models.clinical import (
    FullAssessmentInput,
    PhaseReviewInput,
    PostRemissionInput,
    PreAssessmentInput,
    RemissionJudgeInput,
)
from app.services.full_assessment import evaluate_full_assessment
from app.services.observation import get_observation_status
from app.services.phase_review import evaluate_phase_review
from app.services.post_remission import evaluate_post_remission
from app.services.pre_assessment import evaluate_pre_assessment
from app.services.remission_judge import check_remission, confirm_remission

# 病例3 的锁定输出文案（逐字）：不得提示停药，也不得标记已缓解
CASE3_EXPECTED_TEXT = (
    "治疗下血糖已达非糖尿病范围，暂不能判定缓解。"
    "当前药物具有心肾或体重获益，不建议为获得缓解标签而停药。"
)


def test_case1_early_obesity_severe_hyperglycemia_walks_through() -> None:
    """病例1：43岁女性，T2DM 4个月，BMI 31，HbA1c 10.6%，短期胰岛素强化，愿意减重。"""
    # 步骤1｜预评估：机会信息（高 HbA1c、胰岛素、肥胖）不得触发排除
    pre = evaluate_pre_assessment(
        ST10,
        PreAssessmentInput(
            f001_t2dm_established=enums.YES,
            f002_acute_unsafe=enums.NO,
            f003_type_doubt=enums.NO,
            f004_treatment_context_sufficient=enums.YES,
            f005_refused=enums.NO,
            f006_duration="4个月",
            f007_bmi_hint="BMI 31",
            f008_glucose_status="HbA1c 10.6%",
            f009_insulin="短期强化",
            f010_demands=["减重"],
        ),
    )
    assert pre.conclusion == "进入完整评估"
    assert pre.target_state == ST20

    # 步骤2｜完整评估：一次性启动血糖稳定阶段
    full = evaluate_full_assessment(
        pre.target_state,
        FullAssessmentInput(
            f014_hba1c=10.6,
            f018_weight=85.0,
            f019_height=1.66,
            f026_start=enums.START,
            f027_stage=enums.STAGE_STABLE,
            f028_stage_goal="安全改善明显高血糖",
            f029_interventions=["结构化生活方式", "降糖治疗调整"],
        ),
        date(2026, 9, 20),
    )
    assert full.target_state == ST31
    assert full.stage == enums.STAGE_STABLE

    # 步骤3｜复评：继续当前阶段
    review = evaluate_phase_review(
        full.target_state, PhaseReviewInput(f034_action=enums.ACT_CONTINUE), date(2026, 10, 1)
    )
    assert review.target_state == ST31

    # 步骤4｜转阶段：医生确认进入缓解诱导
    switched = evaluate_phase_review(
        review.target_state,
        PhaseReviewInput(
            f034_action=enums.ACT_SWITCH,
            new_stage=enums.STAGE_INDUCTION,
            stage_goal="实现有临床意义的体重下降",
        ),
        date(2026, 11, 1),
    )
    assert switched.target_state == ST32

    # 步骤5｜停药：系统自动进入观察期（不得出现"停药确认页面"）
    stopped = evaluate_phase_review(
        switched.target_state,
        PhaseReviewInput(
            f034_action=enums.ACT_CONTINUE, f035_stop_last_med=True, f036_stop_date=date(2026, 8, 31)
        ),
        date(2027, 1, 10),
    )
    assert stopped.target_state == ST40
    assert stopped.entered_observation is True
    # 月末钳位：8月31日 + 3 个日历月 = 11月30日
    assert stopped.earliest_judge_date == date(2026, 11, 30)

    # 步骤6｜观察期到期 → 缓解判定
    status = get_observation_status(
        last_med_stop_date=date(2026, 8, 31),
        lifestyle_start_date=None,
        surgery_date=None,
        today=date(2027, 1, 10),
    )
    assert status.due is True

    judged = check_remission(
        ST50,
        RemissionJudgeInput(
            f041_diagnosis_credible=enums.YES,
            f042_drug_free_3m=enums.YES,
            f043_hba1c_reliable=enums.YES,
            f014_hba1c=6.2,
        ),
        today=date(2027, 1, 10),
        earliest_judge_date=status.earliest_judge_date,
        has_glucose_lowering_drug=False,
    )
    # 系统只给出"请医生确认"，不自动形成结论
    assert judged.objective_met is True
    assert judged.target_state == ST50

    confirmed = confirm_remission(ST50, "确认")
    assert confirmed.target_state == ST60

    # 步骤7｜缓解后复评：维持（缓解确认日 2027-01-10，下次随访为 6 个月后）
    post = evaluate_post_remission(
        ST60,
        PostRemissionInput(
            f050_med_status=enums.MED_UNUSED, f055_glucose_state=enums.GLUCOSE_BELOW_THRESHOLD
        ),
        date(2027, 6, 1),
        remission_confirmed_date=date(2027, 1, 10),
    )
    assert post.rule_id == "E5-B01"
    assert post.next_review_date == date(2027, 7, 10)


def test_case2_lean_early_insulin_type_doubt_walks_through() -> None:
    """病例2：38岁男性，BMI 21，起病体重下降，早期胰岛素，C 肽/抗体未查。"""
    # 步骤1｜预评估：分型存疑 → 暂缓，且必须给出前置事项与返回位置
    held = evaluate_pre_assessment(
        ST10,
        PreAssessmentInput(
            f001_t2dm_established=enums.YES,
            f002_acute_unsafe=enums.NO,
            f003_type_doubt=enums.YES,
            f004_treatment_context_sufficient=enums.YES,
            f005_refused=enums.NO,
            f007_bmi_hint="BMI 21",
            f009_insulin="长期使用",
            f012_pre_tasks="复查C肽与糖尿病自身抗体",
        ),
    )
    assert held.conclusion == "暂缓进入"
    assert held.rule_id == "E1-B03"
    assert held.target_state == ST10  # 暂缓为自环，可回到结论处
    assert held.return_hint is not None and "关闭本路径" in held.return_hint
    # 不得把 BMI 正常 / 早期胰岛素 / C 肽缺失本身当作排除理由
    assert held.hold_reasons == [enums.HOLD_TYPE]

    # 分支B｜复核后仍为 T2DM → 直接进入完整评估（不重复入口、不重复预评估）
    confirmed = evaluate_pre_assessment(
        ST10,
        PreAssessmentInput(
            f001_t2dm_established=enums.YES,
            f002_acute_unsafe=enums.NO,
            f003_type_doubt=enums.NO,
            f004_treatment_context_sufficient=enums.YES,
            f005_refused=enums.NO,
        ),
    )
    assert confirmed.target_state == ST20

    # 分支A｜明确为其他类型糖尿病 → 关闭本路径（终态 ST99，无出口）
    # 终态没有出口：字典中不存在该键，用 get 语义判断（不要假定键一定存在）
    assert LEGAL_TRANSITIONS.get(ST99, set()) == set()
    assert ST99 in LEGAL_TRANSITIONS[ST10]


def test_case3_benefit_drug_never_suggests_stopping() -> None:
    """病例3：52岁女性，T2DM 2年，CKD/蛋白尿，SGLT2 抑制剂，减重 10%，HbA1c 5.9%。"""
    # 步骤1｜预评估：CKD 或使用 SGLT2 抑制剂不得导致排除
    pre = evaluate_pre_assessment(
        ST10,
        PreAssessmentInput(
            f001_t2dm_established=enums.YES,
            f002_acute_unsafe=enums.NO,
            f003_type_doubt=enums.NO,
            f004_treatment_context_sufficient=enums.YES,
            f005_refused=enums.NO,
            f008_glucose_status="HbA1c 5.9%",
        ),
    )
    assert pre.target_state == ST20

    # 步骤2｜完整评估：启动缓解诱导阶段
    full = evaluate_full_assessment(
        ST20,
        FullAssessmentInput(
            f023_constraints=["CKD"],
            f026_start=enums.START,
            f027_stage=enums.STAGE_INDUCTION,
            f028_stage_goal="维持体重与代谢改善",
            f029_interventions=["结构化生活方式", "体重管理药物"],
        ),
        date(2026, 9, 20),
    )
    assert full.target_state == ST32

    # 步骤3｜复评：治疗下血糖达非糖尿病范围，但仍在用器官获益药物
    review = evaluate_phase_review(
        ST32,
        PhaseReviewInput(
            f034_action=enums.ACT_CONTINUE,
            f053_has_drug=True,
            f054_purpose=enums.PURPOSE_ORGAN,
            glucose_non_diabetic=True,
        ),
        date(2026, 12, 1),
    )
    assert review.rule_id == "E3-B06"
    assert review.target_state == ST32
    assert review.entered_observation is False
    # 锁定文案逐字一致（不改写、不缩写）
    assert review.output_text == CASE3_EXPECTED_TEXT
    # 不得标记为"已缓解"或"缓解失败"
    assert "已缓解" not in review.output_text
    assert "缓解失败" not in review.output_text

    # 步骤4｜后续复评：保持主动管理，继续事件3复评（不得为获得缓解标签提示停药）
    followup = evaluate_phase_review(
        review.target_state,
        PhaseReviewInput(
            f034_action=enums.ACT_CONTINUE,
            f053_has_drug=True,
            f054_purpose=enums.PURPOSE_ORGAN,
            glucose_non_diabetic=True,
        ),
        date(2027, 3, 1),
    )
    assert followup.target_state == ST32
