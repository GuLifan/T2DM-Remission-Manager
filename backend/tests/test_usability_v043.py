"""0.4.3独立API反例：移除留史、显式无药、停药不可绕过和日期边界。"""

import json
from datetime import date

import pytest
from sqlalchemy import func, select
from test_clinical_v03_cases import v03_test_account as v03_test_account
from test_clinical_v04 import ctx, full_values, phase_values, request, setup_patient

from app.models.clinical_record import ClinicalRecord
from app.models.clinical_v03 import ExaminationRecord
from app.models.event import Event
from app.models.patient import Patient
from app.utils.clinical_v03_dates import examination_date_qualified


def with_drugs(client, account, count=2):
    pid = setup_patient(client, account)
    meds = [
        {
            "name": f"独立模拟药{i}",
            "dose": "待核对",
            "status": "使用中",
            "has_glucose_lowering_effect": True,
            "purposes": ["降糖治疗"],
        }
        for i in range(count)
    ]
    result = request(
        client, account, pid, "full-assessment", **full_values(ctx(client, account, pid), medications=meds)
    )
    assert result.status_code == 200, result.text
    return pid, ctx(client, account, pid)


def counts(db, pid):
    return tuple(
        db.scalar(select(func.count()).select_from(m).where(m.patient_id == pid)) for m in (Event, ClinicalRecord)
    )


def test_partial_removal_appends_current_plan_preserves_original_and_conflicts(client, v03_test_account, db_session):
    a = v03_test_account
    pid, c = with_drugs(client, a)
    original = json.dumps(c["regimen"]["data"], sort_keys=True)
    values = phase_values(c)
    drugs = values["f016_medications"]
    removed = drugs[0]["medication_id"]
    values.update(
        f016_medications=drugs[1:], f053_has_drug=True, f054_purpose="高血糖治疗", removed_medication_ids=[removed]
    )
    result = request(client, a, pid, "phase-review", **values)
    assert result.status_code == 200, result.text
    after = ctx(client, a, pid)
    assert after["regimen"]["id"] != c["regimen"]["id"]
    assert len(after["regimen"]["data"]["medications"]) == 1
    old = db_session.get(ClinicalRecord, c["regimen"]["id"])
    assert json.dumps(old.data, sort_keys=True) == original
    patient = db_session.get(Patient, pid)
    db_session.refresh(patient)
    assert patient.has_glucose_lowering_drug is True
    assert patient.current_state == "ST31" and not patient.actual_stop_confirmed
    event = db_session.get(Event, result.json()["assessment_event_id"])
    assert json.loads(event.payload)["removed_medication_ids"] == [removed]
    assert request(client, a, pid, "phase-review", **values).status_code == 409


@pytest.mark.parametrize(
    "variant", ["missing", "forged", "duplicate", "not_reviewed", "no_empty_confirmation", "invented_card"]
)
def test_removal_cannot_bypass_review_or_identity_and_rolls_back(client, v03_test_account, db_session, variant):
    a = v03_test_account
    pid, c = with_drugs(client, a, 1)
    mid = c["regimen"]["data"]["medications"][0]["medication_id"]
    values = phase_values(c)
    values.update(f016_medications=[], removed_medication_ids=[mid], no_current_medications_confirmed=True)
    if variant == "missing":
        values["removed_medication_ids"] = []
    elif variant == "forged":
        values["removed_medication_ids"] = ["other-patient-id"]
    elif variant == "duplicate":
        values["removed_medication_ids"] = [mid, mid]
    elif variant == "not_reviewed":
        values.update(medication_review_complete=False, f053_has_drug=None)
    elif variant == "no_empty_confirmation":
        values["no_current_medications_confirmed"] = False
    elif variant == "invented_card":
        values.update(
            f016_medications=[{**c["regimen"]["data"]["medications"][0], "medication_id": "foreign-card"}],
            f053_has_drug=True,
            f054_purpose="高血糖治疗",
            no_current_medications_confirmed=False,
        )
    before = counts(db_session, pid)
    rejected = request(client, a, pid, "phase-review", **values)
    assert rejected.status_code == 422, rejected.text
    assert counts(db_session, pid) == before
    assert ctx(client, a, pid)["regimen"]["id"] == c["regimen"]["id"]


def test_explicit_empty_plan_does_not_manufacture_stop_or_observation(client, v03_test_account, db_session):
    a = v03_test_account
    pid, c = with_drugs(client, a, 1)
    values = phase_values(c)
    values.update(
        f016_medications=[],
        removed_medication_ids=[c["regimen"]["data"]["medications"][0]["medication_id"]],
        no_current_medications_confirmed=True,
    )
    saved = request(client, a, pid, "phase-review", **values)
    assert saved.status_code == 200, saved.text
    p = db_session.get(Patient, pid)
    db_session.refresh(p)
    assert p.current_state == "ST31" and p.has_glucose_lowering_drug is False
    assert p.last_med_stop_date is None and p.actual_stop_confirmed is not True
    assert ctx(client, a, pid)["regimen"]["data"] == {"medications": [], "complete": True}


def test_removed_glucose_drug_cannot_bypass_individual_actual_stop(client, v03_test_account):
    a = v03_test_account
    pid, c = with_drugs(client, a, 1)
    values = phase_values(c)
    values.update(
        f016_medications=[],
        removed_medication_ids=[c["regimen"]["data"]["medications"][0]["medication_id"]],
        no_current_medications_confirmed=True,
        f035_stop_last_med=True,
        f057_actual_stop="已实际停用",
        f036_stop_date="2026-01-15",
        anchors={"f063_applicable_interventions": ["其他"]},
    )
    rejected = request(client, a, pid, "phase-review", **values)
    assert rejected.status_code == 422 and "逐药核对" in rejected.json()["detail"]


@pytest.mark.parametrize("day,status", [("2026-01-01", 200), ("2026-01-15", 200), ("2026-01-16", 422)])
def test_general_examination_allows_past_and_today_explains_future(client, v03_test_account, day, status):
    a = v03_test_account
    pid = setup_patient(client, a)
    values = full_values(ctx(client, a, pid))
    values["examinations"] = [{"kind": "HbA1c", "value": 6.2, "unit": "%", "test_date": day}]
    response = request(client, a, pid, "full-assessment", **values)
    assert response.status_code == status, response.text
    if status == 422:
        assert day in response.json()["detail"] and "2026-01-15" in response.json()["detail"]


@pytest.mark.parametrize(
    "day,qualified",
    [(date(2026, 9, 30), False), (date(2026, 10, 1), True), (date(2026, 10, 20), True), (date(2026, 10, 22), False)],
)
def test_judgement_closed_interval_is_unchanged(day, qualified):
    exam = ExaminationRecord(kind="HbA1c", value=6.2, unit="%", test_date=day, source="本院检查", reliability="可靠")
    assert examination_date_qualified(exam, date(2026, 10, 1), date(2026, 10, 21)) is qualified
