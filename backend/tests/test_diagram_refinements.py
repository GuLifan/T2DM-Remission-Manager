"""2026-10-13 导图修订的关键反例，不从未知事实推断医学结论。"""

from datetime import date

from app.models.clinical_v03 import PostRemissionV03
from app.services.clinical_v03 import Context, evaluate_post


def test_unknown_medication_with_reliable_low_glucose_still_requires_review():
    payload = PostRemissionV03(
        request_id="unknown-med",
        expected_revision=1,
        f018_weight=70,
        f049_glucose="虚构可靠指标",
        f049_test_date=date(2026, 10, 1),
        f050_med_status="待核对",
        f055_glucose_state="低于糖尿病诊断阈值",
        risk_increase_confirmed=False,
        f012_pre_tasks="复核当前药物",
    )
    result = evaluate_post(Context("ST60"), payload, date(2026, 10, 13))
    assert result.transition_ids == ["T45"]
    assert result.updates["current_remission_evaluation"] == "待复核"
