"""v0.3三病例正式API走查；只使用测试账号、测试患者、模拟日期和隔离数据库。"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.config import get_settings
from app.models.user import User


@pytest.fixture()
def v03_test_account(doctor, db_session):
    settings = get_settings()
    old_mode = settings.test_mode
    user = db_session.get(User, doctor["user"]["id"])
    old_flag, old_date = user.is_test_account, user.simulated_date
    settings.test_mode = True
    user.is_test_account = True
    user.simulated_date = None
    db_session.commit()
    yield doctor
    user = db_session.get(User, doctor["user"]["id"])
    user.is_test_account, user.simulated_date = old_flag, old_date
    db_session.commit()
    settings.test_mode = old_mode


def set_date(client, account, value: str):
    response = client.post("/api/test-context/simulated-date", headers=account["headers"],
                           json={"simulated_date": value})
    assert response.status_code == 200, response.text


def create_patient(client, account, suffix: str) -> dict:
    response = client.post("/api/patients", headers=account["headers"], json={
        "name": f"v0.3虚构病例{suffix}", "gender": "女", "birth_date": "1980-01-01",
        "medical_record_no": f"V03-{suffix}-{uuid4().hex[:8]}", "department": "内分泌科",
        "contact_phone": None,
    })
    assert response.status_code == 201, response.text
    return response.json()


def submit(client, account, patient_id: int, action: str, revision: int, **values) -> dict:
    response = client.post(f"/api/patients/{patient_id}/clinical-v03/{action}", headers=account["headers"],
                           json={"clinical_contract_version": "v0.3", "request_id": uuid4().hex,
                                 "expected_revision": revision, **values})
    assert response.status_code == 200, response.text
    return response.json()


def reopen(client, account, patient: dict) -> dict:
    return submit(client, account, patient["id"], "supplemental-decision", patient["clinical_revision"],
                  transition_id="P01", doctor_confirmed=True, reason="医生确认重新评估",
                  evidence_summary="虚构测试条件变化", remission_termination_confirmed=False,
                  f050_med_status=None)


def enter_full(client, account, patient_id: int, revision: int, *, weight=81.4, height=162) -> dict:
    return submit(client, account, patient_id, "pre-assessment", revision,
                  f018_weight=weight, f019_height=height, f001_t2dm_established="是",
                  f002_acute_unsafe="否", f003_type_doubt="否", f004_treatment_context_sufficient="是",
                  f005_refused="否", f061_conclusion="进入完整评估", f011_hold_reasons=[],
                  f012_pre_tasks=None, opportunity_info={}, f016_medications=[])


def test_case1_complete_path_plan_vs_actual_stop_and_same_snapshot_confirmation(client, v03_test_account):
    account = v03_test_account
    set_date(client, account, "2026-01-15")
    patient = create_patient(client, account, "CASE1")
    step = reopen(client, account, patient)
    assert step["transition_ids"] == ["P01"]
    step = enter_full(client, account, patient["id"], step["patient_revision"])
    assert step["transition_ids"] == ["T01"]
    insulin = {"name": "虚构短期胰岛素", "dose": "演示剂量", "status": "使用中",
               "has_glucose_lowering_effect": True, "purpose": "高血糖治疗", "started_on": "2026-01-15"}
    step = submit(client, account, patient["id"], "full-assessment", step["patient_revision"],
                  f018_weight=81.4, f019_height=None, f026_start="启动", f013_diagnosis_basis="既往T2DM记录由医生核对",
                  recent_examination={"kind": "HbA1c", "value": 10.6, "unit": "%", "source": "虚构实验室",
                                      "test_date": "2026-01-10", "reliability": "可靠"},
                  f015_recent_glucose=None, f015_test_date=None, recent_glucose_reliable="是",
                  f016_medications=[insulin], f016_no_medication_confirmed=False, f023_constraints=["无"],
                  f024_willing="是", f025_review_accept="是", f027_stage="血糖稳定",
                  f028_stage_goal="安全改善明显高血糖", f029_interventions=["结构化生活方式"],
                  f012_pre_tasks=None, next_review_date="2026-04-09")
    assert step["transition_ids"] == ["T10"]

    set_date(client, account, "2026-04-09")
    step = submit(client, account, patient["id"], "phase-review", step["patient_revision"],
                  f018_weight=78, f019_height=None, f030_safety_issues=["无"], f031_stage_indicator="医生核对近期趋势",
                  f032_treatment_changes=["无"], f033_executable="可继续", f034_action="转换阶段",
                  f035_stop_last_med=False, f057_actual_stop=None, planned_stop_date=None, f036_stop_date=None,
                  f053_has_drug=True, f054_purpose="高血糖治疗", f060_non_diabetic_on_treatment="否",
                  f056_uncontrolled=False, f016_medications=[insulin], anchors=None, f062_target_stage="缓解诱导",
                  stage_goal="体重和代谢改善", adjustment_summary=None, end_reason=None, next_review_date="2026-04-20")
    assert step["transition_ids"] == ["T20"]

    set_date(client, account, "2026-04-20")
    step = submit(client, account, patient["id"], "phase-review", step["patient_revision"],
                  f018_weight=73.4, f019_height=None, f030_safety_issues=["无"], f031_stage_indicator="医生复核",
                  f032_treatment_changes=["无"], f033_executable="可继续", f034_action="继续当前阶段",
                  f035_stop_last_med=True, f057_actual_stop="仅计划停用", planned_stop_date="2026-05-01",
                  f036_stop_date=None, f053_has_drug=True, f054_purpose="高血糖治疗",
                  f060_non_diabetic_on_treatment="否", f056_uncontrolled=False, f016_medications=[insulin],
                  anchors=None, f062_target_stage=None, stage_goal=None, adjustment_summary=None,
                  end_reason=None, next_review_date="2026-05-01")
    assert step["transition_ids"] == ["T14B"] and step["target_state"] == "ST32"

    set_date(client, account, "2026-05-01")
    stopped = {**insulin, "status": "已停用", "stopped_on": "2026-05-01"}
    step = submit(client, account, patient["id"], "phase-review", step["patient_revision"],
                  f018_weight=73, f019_height=None, f030_safety_issues=["无"], f031_stage_indicator="医生复核",
                  f032_treatment_changes=["药物调整"], f033_executable="可继续", f034_action="继续当前阶段",
                  f035_stop_last_med=True, f057_actual_stop="已实际停用", planned_stop_date=None,
                  f036_stop_date="2026-05-01", f053_has_drug=False, f054_purpose=None,
                  f060_non_diabetic_on_treatment="否", f056_uncontrolled=False, f016_medications=[stopped],
                  anchors={"f063_applicable_interventions": ["结构化生活方式"],
                           "f038_lifestyle_start_date": "2026-01-15", "f039_surgery_date": None},
                  f062_target_stage=None, stage_goal=None, adjustment_summary=None, end_reason=None,
                  next_review_date=None)
    assert step["transition_ids"] == ["T18B", "T22"] and step["target_state"] == "ST40"

    set_date(client, account, "2026-08-01")
    step = submit(client, account, patient["id"], "refresh", step["patient_revision"])
    assert step["transition_ids"] == ["T24"] and step["target_state"] == "ST50"
    step = submit(client, account, patient["id"], "remission-judge", step["patient_revision"],
                  f018_weight=70, f019_height=None, f041_diagnosis_credible="是", f042_drug_free_3m="是",
                  f043_hba1c_reliable="是", f053_has_drug=False, f059_completeness="完整",
                  f058_examination={"kind": "HbA1c", "value": 5.9, "unit": "%", "source": "虚构实验室",
                                      "test_date": "2026-08-01", "reliability": "可靠"},
                  f016_medications=[stopped], f062_target_stage=None, f012_pre_tasks=None,
                  anchors={"f063_applicable_interventions": ["结构化生活方式"],
                           "f038_lifestyle_start_date": "2026-01-15", "f039_surgery_date": None})
    assert step["transition_ids"] == ["T34"] and step["objective_met"] is True
    step = submit(client, account, patient["id"], "remission-confirm", step["patient_revision"],
                  f048_confirm="确认", assessment_event_id=step["assessment_event_id"], f012_pre_tasks=None)
    assert step["transition_ids"] == ["T35", "T44"] and step["target_state"] == "ST60"

    set_date(client, account, "2027-02-01")
    step = submit(client, account, patient["id"], "post-remission", step["patient_revision"],
                  f018_weight=69, f019_height=None, f049_glucose="HbA1c 5.8%", f049_test_date="2027-02-01",
                  f050_med_status="未使用", f055_glucose_state="低于糖尿病诊断阈值",
                  f051_risk_triggers=["无"], risk_increase_confirmed=False, f016_medications=[],
                  f062_target_stage=None, f012_pre_tasks=None, next_review_date="2027-08-01")
    assert step["transition_ids"] == ["T39"] and step["target_state"] == "ST60"


@pytest.mark.parametrize(("outcome", "expected"), [("分型仍为T2DM", "T05"), ("分型明确其他类型", "T06")])
def test_case2_type_review_has_both_independent_exits(client, v03_test_account, outcome, expected):
    account = v03_test_account
    set_date(client, account, "2026-01-15")
    patient = create_patient(client, account, f"CASE2-{expected}")
    step = reopen(client, account, patient)
    step = submit(client, account, patient["id"], "pre-assessment", step["patient_revision"],
                  f018_weight=61, f019_height=170, f001_t2dm_established="待确认", f002_acute_unsafe="否",
                  f003_type_doubt="是", f004_treatment_context_sufficient="是", f005_refused="否",
                  f061_conclusion="暂缓进入", f011_hold_reasons=["分型存疑"],
                  f012_pre_tasks="定向复核C肽、自身抗体与临床分型", opportunity_info={}, f016_medications=[])
    assert step["transition_ids"] == ["T03"]
    set_date(client, account, "2026-01-22")
    step = submit(client, account, patient["id"], "pre-recovery", step["patient_revision"],
                  f018_weight=61, f019_height=None, result=outcome, doctor_confirmed=True,
                  evidence_summary="虚构分型复核资料", stage_goal=None, interventions=[], next_review_date=None)
    assert step["transition_ids"] == [expected]
    assert step["target_state"] == ("ST20" if expected == "T05" else "ST99")


def test_case3_benefit_drug_is_parallel_information_not_observation(client, v03_test_account):
    account = v03_test_account
    set_date(client, account, "2026-01-15")
    patient = create_patient(client, account, "CASE3")
    step = enter_full(client, account, patient["id"], reopen(client, account, patient)["patient_revision"],
                      weight=73.5, height=162)
    benefit = {"name": "虚构SGLT2抑制剂", "dose": "演示剂量", "status": "使用中",
               "has_glucose_lowering_effect": True, "purpose": "器官获益", "started_on": "2026-01-01"}
    step = submit(client, account, patient["id"], "full-assessment", step["patient_revision"],
                  f018_weight=73.5, f019_height=None, f026_start="启动", f013_diagnosis_basis="既往T2DM记录由医生核对",
                  recent_examination={"kind": "HbA1c", "value": 5.9, "unit": "%", "source": "虚构实验室",
                                      "test_date": "2026-01-10", "reliability": "可靠"},
                  f015_recent_glucose=None, f015_test_date=None, recent_glucose_reliable="是",
                  f016_medications=[benefit], f016_no_medication_confirmed=False, f023_constraints=["CKD/蛋白尿"],
                  f024_willing="是", f025_review_accept="是", f027_stage="缓解诱导",
                  f028_stage_goal="体重与代谢改善", f029_interventions=["结构化生活方式"],
                  f012_pre_tasks=None, next_review_date="2026-04-09")
    assert step["transition_ids"] == ["T11"]
    set_date(client, account, "2026-04-09")
    step = submit(client, account, patient["id"], "phase-review", step["patient_revision"],
                  f018_weight=73.5, f019_height=None, f030_safety_issues=["无"],
                  f031_stage_indicator="减重10%，HbA1c 5.9%", f032_treatment_changes=["无"],
                  f033_executable="可继续", f034_action="继续当前阶段", f035_stop_last_med=False,
                  f057_actual_stop=None, planned_stop_date=None, f036_stop_date=None, f053_has_drug=True,
                  f054_purpose="器官获益", f060_non_diabetic_on_treatment="是", f056_uncontrolled=False,
                  f016_medications=[benefit], anchors=None, f062_target_stage=None, stage_goal=None,
                  adjustment_summary=None, end_reason=None, next_review_date="2026-07-02")
    assert step["transition_ids"] == ["T17B", "T14B"] and step["target_state"] == "ST32"
    read = client.get(f"/api/patients/{patient['id']}", headers=account["headers"]).json()
    assert read["last_med_stop_date"] is None and read["observation_status"] == "none"
