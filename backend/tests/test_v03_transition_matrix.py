"""原子转移逐项服务验证；确认三条通过真实接口单独验证。全部虚构资料。"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.clock import system_clock
from app.domain.clinical_v03 import TRANSITIONS_BY_ID
from app.models.clinical_v03 import (
    FullAssessmentV03,
    MedicationRestartV03,
    ObservationAnchors,
    PhaseReviewV03,
    PostRemissionV03,
    PreAssessmentV03,
    PreRecoveryV03,
    RemissionJudgeV03,
    SupplementalDecisionV03,
)
from app.models.patient import Patient
from app.services import clinical_v03 as s
from app.utils.date_utils import add_months_clamped

TODAY = date(2026, 10, 13)
BASE = {"request_id": "matrix", "expected_revision": 1, "f018_weight": 70}
ANCHOR = {"f063_applicable_interventions": ["其他"]}
PRE = {
    **BASE,
    "f001_t2dm_established": "是",
    "f002_acute_unsafe": "否",
    "f003_type_doubt": "否",
    "f004_treatment_context_sufficient": "是",
    "f005_refused": "否",
    "f061_conclusion": "进入完整评估",
}
FULL = {
    **BASE,
    "f026_start": "启动",
    "f013_diagnosis_basis": "虚构诊断记录",
    "f015_recent_glucose": "虚构可靠血糖",
    "f015_test_date": "2026-10-01",
    "recent_glucose_reliable": "是",
    "f016_no_medication_confirmed": True,
    "f024_willing": "是",
    "f025_review_accept": "是",
    "f027_stage": "血糖稳定",
    "f028_stage_goal": "虚构目标",
    "f029_interventions": ["其他"],
}
PHASE = {
    **BASE,
    "f030_safety_issues": ["无"],
    "f031_stage_indicator": "虚构复评",
    "f032_treatment_changes": ["无"],
    "f033_executable": "可继续",
    "f034_action": "继续当前阶段",
    "f035_stop_last_med": False,
    "f053_has_drug": False,
}
EXAM = {
    "kind": "HbA1c",
    "value": 6.1,
    "unit": "%",
    "source": "虚构实验室",
    "test_date": "2026-10-01",
    "reliability": "可靠",
}
JUDGE = {
    **BASE,
    "f041_diagnosis_credible": "是",
    "f042_drug_free_3m": "是",
    "f043_hba1c_reliable": "是",
    "f053_has_drug": False,
    "f059_completeness": "完整",
    "anchors": ANCHOR,
    "f058_examination": EXAM,
}
POST = {
    **BASE,
    "f049_glucose": "虚构可靠血糖",
    "f049_test_date": "2026-10-01",
    "f050_med_status": "未使用",
    "f055_glucose_state": "低于糖尿病诊断阈值",
    "risk_increase_confirmed": False,
}


def medication(purpose):
    return {
        "name": "虚构药",
        "dose": "测试用法",
        "status": "使用中",
        "has_glucose_lowering_effect": True,
        "purpose": purpose,
        "started_on": "2026-01-01",
    }


def observation(state="ST40", stop=date(2026, 6, 1)):
    return s.Context(
        state,
        stop_date=stop,
        anchors=ObservationAnchors(**ANCHOR),
        observation_status="active",
        actual_stop_confirmed=True,
        has_drug=False,
    )


IDS = [key for key in TRANSITIONS_BY_ID if key not in {"T35", "T36", "T44"}]


@pytest.mark.parametrize("key", IDS)
def test_each_atomic_transition_has_executable_clinical_decision(key):
    source = TRANSITIONS_BY_ID[key].source
    if key.startswith("P"):
        payload = SupplementalDecisionV03(
            request_id="matrix",
            expected_revision=1,
            transition_id=key,
            doctor_confirmed=True,
            reason="虚构重大变化或重发条件",
            evidence_summary="虚构证据",
            remission_termination_confirmed=key == "P04",
            f050_med_status="因器官获益" if key.startswith("P05") else None,
            medication_review_complete=key.startswith("P05"),
            f016_medications=[{"name":"获益用药", "dose":"待核对", "status":"使用中", "has_glucose_lowering_effect":True, "purposes":["肾脏保护"]}] if key.startswith("P05") else [],
        )
        result = s.evaluate_supplement(s.Context(source), payload)
    elif key in {"T01", "T02", "T03", "T04", "T09"}:
        values = dict(PRE)
        if key in {"T02", "T03", "T04"}:
            reason, field, fact = {
                "T02": ("急性安全", "f002_acute_unsafe", "是"),
                "T03": ("分型存疑", "f003_type_doubt", "是"),
                "T04": ("关键资料不足", "f004_treatment_context_sufficient", "否"),
            }[key]
            values.update(
                {
                    field: fact,
                    "f061_conclusion": "暂缓进入",
                    "f011_hold_reasons": [reason],
                    "f012_pre_tasks": "虚构定向任务",
                }
            )
        elif key == "T09":
            values["f061_conclusion"] = "当前不启动"
        result = s.evaluate_pre(s.Context(source), PreAssessmentV03(**values))
    elif key in {"T05", "T06", "T07", "T08"}:
        choice = {
            "T05": "分型仍为T2DM",
            "T06": "分型明确其他类型",
            "T07": "急性已处理返回结论",
            "T08": "急性已处理进入血糖稳定",
        }[key]
        payload = PreRecoveryV03(
            **BASE,
            result=choice,
            doctor_confirmed=True,
            evidence_summary="虚构复核",
            stage_goal="虚构初始目标",
            interventions=["其他"],
        )
        result = s.evaluate_recovery(
            s.Context(source), payload, TODAY, ["分型存疑" if key in {"T05", "T06"} else "急性安全"]
        )
    elif key in {"T10", "T11", "T12", "T13"}:
        values = dict(FULL)
        if key == "T11":
            values["f027_stage"] = "缓解诱导"
        elif key == "T12":
            values.update(f026_start="暂缓补充关键资料", f012_pre_tasks="补充虚构资料")
        elif key == "T13":
            values["f026_start"] = "当前不启动"
        result = s.evaluate_full(s.Context(source), FullAssessmentV03(**values), TODAY)
    elif key.startswith(("T14", "T15", "T16", "T17", "T18", "T19")) or key in {"T20", "T21"}:
        values = dict(PHASE)
        if key.startswith("T15"):
            values.update(f034_action="调整方案或目标", adjustment_summary="虚构调整")
        elif key.startswith("T16"):
            values.update(f034_action="结束主动管理", end_reason="虚构原因")
        elif key.startswith("T17"):
            values.update(
                f053_has_drug=True,
                f054_purpose="器官获益",
                f060_non_diabetic_on_treatment="是",
                f016_medications=[medication("器官获益")],
            )
        elif key.startswith("T18"):
            values.update(
                f035_stop_last_med=True, f057_actual_stop="已实际停用", f036_stop_date="2026-10-01", anchors=ANCHOR
            )
        elif key.startswith("T19"):
            values["f056_uncontrolled"] = True
        elif key in {"T20", "T21"}:
            values.update(
                f034_action="转换阶段",
                f062_target_stage="缓解诱导" if key == "T20" else "血糖稳定",
                stage_goal="虚构新目标",
            )
        result = s.evaluate_phase(
            s.Context(source, stage="血糖稳定" if source == "ST31" else "缓解诱导"), PhaseReviewV03(**values), TODAY
        )
    elif key in {"T22", "T23", "T24"}:
        result = s.evaluate_observation(
            observation(stop=date(2026, 10, 1) if key != "T24" else date(2026, 6, 1)), TODAY
        )
    elif key in {"T25", "T26", "T27", "T28", "T29"}:
        high = key in {"T25", "T26"}
        stage = "血糖稳定" if key in {"T25", "T28"} else "缓解诱导" if key in {"T26", "T29"} else None
        result = s.evaluate_restart(
            observation(),
            MedicationRestartV03(
                request_id="matrix",
                expected_revision=1,
                f037_reason="因高血糖" if high else "因器官获益",
                f062_target_stage=stage,
                f016_medications=[medication("高血糖治疗" if high else "器官获益")],
            ),
        )
    elif key in {"T30", "T31", "T32", "T33", "T34", "T37", "T38"}:
        values = dict(JUDGE)
        ctx = observation("ST50")
        if key == "T30":
            ctx = observation("ST50", date(2026, 10, 1))
        elif key == "T31":
            values["f041_diagnosis_credible"] = "待复核"
        elif key in {"T32", "T33"}:
            values.update(
                f053_has_drug=True,
                f062_target_stage="血糖稳定" if key == "T32" else "缓解诱导",
                f016_medications=[medication("高血糖治疗")],
            )
        elif key in {"T37", "T38"}:
            values.update(
                f058_examination={**EXAM, "value": 6.5}, f062_target_stage="血糖稳定" if key == "T37" else "缓解诱导"
            )
        result = s.evaluate_judge(ctx, RemissionJudgeV03(**values), TODAY)
    else:
        values = dict(POST)
        if key == "T40":
            values.update(risk_increase_confirmed=True, f051_risk_triggers=["体重回升"])
        elif key == "T41":
            values.update(f050_med_status="因器官获益", f016_medications=[medication("器官获益")])
        elif key in {"T42", "T43"}:
            values.update(
                f050_med_status="因高血糖",
                f049_glucose=None,
                f049_test_date=None,
                f055_glucose_state="暂不能可靠解释",
                f062_target_stage="血糖稳定" if key == "T42" else "缓解诱导",
                f016_medications=[medication("高血糖治疗")],
            )
        elif key == "T45":
            values.update(f049_glucose=None, f049_test_date=None, f012_pre_tasks="虚构复核任务")
        result = s.evaluate_post(s.Context("ST60", confirmed_date=date(2026, 1, 1)), PostRemissionV03(**values), TODAY)
    assert key in result.transition_ids
    # 并行注释后仍只有一个最终目标，核对整条组合而非假设每 ID 都是最终状态。
    assert result.target_state == TRANSITIONS_BY_ID[result.transition_ids[-1]].target


@pytest.mark.parametrize("key", ["T35", "T36", "T44"])
def test_confirmation_transition_over_api_binds_current_objective_event(client, doctor, db_session, key):
    today = system_clock.today()
    patient = Patient(
        name="虚构判定矩阵",
        gender="女",
        birth_date=date(1980, 1, 1),
        medical_record_no="MATRIX-" + uuid4().hex[:16],
        department="内分泌科",
        owner_id=doctor["user"]["id"],
        height_cm=165,
        profile_complete=True,
        is_test_patient=True,
        current_state="ST50",
        clinical_contract_version="v0.3",
        observation_status="active",
        actual_stop_confirmed=True,
        has_glucose_lowering_drug=False,
        last_med_stop_date=add_months_clamped(today, -4),
        applicable_interventions=["其他"],
    )
    db_session.add(patient)
    db_session.commit()
    base = f"/api/patients/{patient.id}/clinical-v03/"
    payload = {
        **JUDGE,
        "request_id": uuid4().hex,
        "expected_revision": patient.clinical_revision,
        "f058_examination": {**EXAM, "test_date": today.isoformat()},
    }
    checked = client.post(base + "remission-judge", headers=doctor["headers"], json=payload)
    assert checked.status_code == 200, checked.text
    data = checked.json()
    assert data["transition_ids"] == ["T34"]
    confirmation = client.post(
        base + "remission-confirm",
        headers=doctor["headers"],
        json={
            "request_id": uuid4().hex,
            "expected_revision": data["patient_revision"],
            "assessment_event_id": data["assessment_event_id"],
            "f048_confirm": "暂不确认" if key == "T36" else "确认",
            "f012_pre_tasks": "虚构定向复核" if key == "T36" else None,
        },
    )
    assert confirmation.status_code == 200, confirmation.text
    assert key in confirmation.json()["transition_ids"]
    duplicate = client.post(
        base + "remission-confirm",
        headers=doctor["headers"],
        json={
            "request_id": uuid4().hex,
            "expected_revision": data["patient_revision"],
            "assessment_event_id": data["assessment_event_id"],
            "f048_confirm": "确认",
        },
    )
    assert duplicate.status_code in {409, 422}
