"""批准v0.4的真实API、数据引用、历史和迁移反例；仅隔离虚构库。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from uuid import uuid4

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import select
from test_clinical_v03_cases import create_patient, reopen, set_date
from test_clinical_v03_cases import v03_test_account as v03_test_account
from test_clinical_v03_contract import migration_config
from test_public_demo import demo as demo

from app.models.clinical_record import ClinicalRecord
from app.models.clinical_v03 import AssessmentRequest, MedicationRecord
from app.models.event import Event
from app.models.patient import Patient
from app.services.clinical_records import drug_state


@pytest.mark.parametrize("years,months,valid", [(None,None,True),(2,None,True),(None,18,True),(2,11,True),(0,0,True),(2,12,False),(0,18,False),(-1,0,False),(None,1.5,False)])
def test_duration_preserves_blank_zero_and_independent_months(years, months, valid):
    values = {"input_schema_version": "v0.4", "request_id": "duration", "expected_revision": 1,
                  "duration_years": years, "duration_months": months}
    if valid:
        result = AssessmentRequest(**values)
        assert (result.duration_years, result.duration_months) == (years, months)
    else:
        with pytest.raises(ValidationError):
            AssessmentRequest(**values)


@pytest.mark.parametrize("precision,value", [("unknown",None),("year","2024"),("month","2024-06")])
def test_partial_drug_dates_never_manufacture_a_day(precision, value):
    med = MedicationRecord(name="虚构药", dose="待核对", status="使用中", purposes=["肾脏保护", "心血管保护"],
                           start_precision=precision, start_value=value)
    assert med.started_on is None and med.start_value == value
    assert med.matches_purpose("器官获益")


def request(client, account, pid, action, **payload):
    current = client.get(f"/api/patients/{pid}", headers=account["headers"]).json()
    return client.post(f"/api/patients/{pid}/clinical-v03/{action}", headers=account["headers"], json={
        "input_schema_version": "v0.4", "request_id": uuid4().hex,
        "expected_revision": current["clinical_revision"], **payload})


def ctx(client, account, pid):
    r = client.get(f"/api/patients/{pid}/clinical-v04/context", headers=account["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def pre(client, account, pid):
    r = request(client, account, pid, "pre-assessment", f001_t2dm_established="是", f002_acute_unsafe="否",
                f003_type_doubt="否", f004_treatment_context_sufficient="是", f005_refused="否", f061_conclusion="进入完整评估",
                duration_years=None, duration_months=18)
    assert r.status_code == 200, r.text
    assert r.json()["transition_ids"] == ["T01"]


def full_values(context, *, medications=None):
    return {"f018_weight": 73.5, "f019_height": 170, "measured_on": "2026-01-15", "f026_start": "启动",
                "f013_diagnosis_basis": "虚构T2DM诊断经医生核对", "f024_willing": "是", "f025_review_accept": "是",
                "f027_stage": "血糖稳定", "f028_stage_goal": "安全管理", "f023_constraints": ["无"],
                "f029_interventions": ["结构化生活方式", "降糖治疗调整"],
                "regimen_source_id": context["regimen"]["id"], "medication_review_complete": True,
                "current_medication_confirmation": "是" if medications else "否", "f016_medications": medications or [],
                "examinations": [{"kind":"HbA1c","value":8.2,"unit":"%","test_date":"2026-01-15"},
                              {"kind":"指尖血糖","value":7.1,"unit":"mmol/L","test_date":"2026-01-15"}]}


def phase_values(context):
    return {"measurement_id": context["measurement"]["id"], "regimen_source_id": context["regimen"]["id"],
                "f016_medications": context["regimen"]["data"]["medications"], "medication_review_complete": True,
                "f030_safety_issues": ["无"], "f031_stage_indicator": "本次虚构指标", "f032_treatment_changes": ["无"],
                "f033_executable": "可继续", "f034_action": "继续当前阶段", "f035_stop_last_med": False,
                "f053_has_drug": False}


def setup_patient(client, account):
    set_date(client, account, "2026-01-15")
    p = create_patient(client, account, uuid4().hex[:5])
    reopen(client, account, p)
    pre(client, account, p["id"])
    return p["id"]


def test_inheritance_multiexam_measurements_and_immutable_history(client, v03_test_account, db_session):
    a = v03_test_account
    pid = setup_patient(client, a)
    c = ctx(client, a, pid)
    assert c["measurement"] is None and c["duration"]["data"] == {"years":None,"months":18}
    assert request(client, a, pid, "full-assessment", **full_values(c)).status_code == 200
    c = ctx(client, a, pid)
    assert len(c["examinations"]) == 2
    mid, rid = c["measurement"]["id"], c["regimen"]["id"]
    assert c["measurement"]["data"]["measured_on"] == "2026-01-15"
    count = len(list(db_session.scalars(select(ClinicalRecord).where(ClinicalRecord.patient_id == pid))))
    for _ in range(2):
        assert ctx(client, a, pid)["regimen"]["id"] == rid
    assert count == len(list(db_session.scalars(select(ClinicalRecord).where(ClinicalRecord.patient_id == pid))))
    assert request(client, a, pid, "phase-review", **phase_values(c)).status_code == 200
    c = ctx(client, a, pid)
    assert c["measurement"]["id"] == mid and c["regimen"]["id"] == rid
    values = phase_values(c)
    del values["measurement_id"]
    values.update(f018_weight=66, measured_on="2026-01-16")
    set_date(client, a, "2026-01-16")
    saved = request(client, a, pid, "phase-review", **values)
    assert saved.status_code == 200, saved.text
    c = ctx(client, a, pid)
    assert len(c["measurements"]) == 2 and c["weight_reduction_percent"] == 10.2
    detail = client.get(f"/api/patients/{pid}/clinical-v04/events/{saved.json()['assessment_event_id']}", headers=a["headers"]).json()
    assert detail["payload"]["measurement_snapshot"]["weight_kg"] == 66
    assert detail["payload"]["record_refs"]["regimen_id"] == rid


def test_medication_reuse_requires_current_confirmation_and_cannot_delete_saved_card(client, v03_test_account):
    a = v03_test_account
    pid = setup_patient(client, a)
    c = ctx(client, a, pid)
    med = {"name":"自填模拟药", "dose":"演示剂量", "status":"使用中", "has_glucose_lowering_effect":True,
           "purposes":["降糖治疗","肾脏保护"],"start_precision":"month","start_value":"2025-12"}
    values = full_values(c, medications=[med])
    values["current_medication_confirmation"] = None
    assert request(client, a, pid, "full-assessment", **values).status_code == 422
    assert not ctx(client, a, pid)["measurements"]  # 事务回滚，不留下半条测量
    values["current_medication_confirmation"] = "是"
    good = request(client, a, pid, "full-assessment", **values)
    assert good.status_code == 200, good.text
    c = ctx(client, a, pid)
    assert c["regimen"]["data"]["medications"][0]["start_value"] == "2025-12"
    assert c["regimen"]["data"]["medications"][0]["started_on"] is None
    bad = phase_values(c)
    bad["f016_medications"] = []
    assert request(client, a, pid, "phase-review", **bad).status_code == 422
    good_phase = phase_values(c)
    good_phase.update(f053_has_drug=True, f054_purpose="高血糖治疗")
    assert request(client, a, pid, "phase-review", **good_phase).status_code == 200
    assert ctx(client, a, pid)["regimen"]["id"] == c["regimen"]["id"]


def test_cross_patient_reference_and_append_only_correction(client, v03_test_account, db_session):
    a = v03_test_account
    pid = setup_patient(client, a)
    assert request(client, a, pid, "full-assessment", **full_values(ctx(client,a,pid))).status_code == 200
    c = ctx(client, a, pid)
    other = setup_patient(client, a)
    values = full_values(ctx(client,a,other))
    values.pop("f018_weight")
    values["measurement_id"] = c["measurement"]["id"]
    assert request(client, a, other, "full-assessment", **values).status_code == 404
    source = db_session.get(Event, c["measurement"]["source_event_id"])
    original = source.payload
    current = client.get(f"/api/patients/{pid}", headers=a["headers"]).json()
    replacement = {**c["measurement"]["data"], "weight_kg":72}
    r = client.post(f"/api/patients/{pid}/clinical-v04/corrections", headers=a["headers"], json={
        "request_id":uuid4().hex,"expected_revision":current["clinical_revision"], "record_id":c["measurement"]["id"],
        "kind":"measurement","reason":"虚构误录更正", "replacement":replacement})
    assert r.status_code == 200, r.text
    db_session.refresh(source)
    assert source.payload == original
    assert ctx(client,a,pid)["measurement"]["data"]["weight_kg"] == 72
    db_session.get(Patient,pid).archived = True
    db_session.commit()
    body = r.json()
    assert client.post(f"/api/patients/{pid}/clinical-v04/corrections", headers=a["headers"], json={
        "request_id":uuid4().hex,"expected_revision":body["patient_revision"], "record_id":body["record"]["id"],
        "kind":"measurement","reason":"归档不可写", "replacement":replacement}).status_code == 403


def test_unknown_and_complete_empty_medications_are_distinct():
    assert drug_state([], False) is None
    assert drug_state([], True) is False
    med = MedicationRecord(name="模拟", dose="待核对", status="待核对", purposes=["其他"])
    assert drug_state([med], True) is None


def test_public_new_routes_reject_other_doctor_and_reads_never_write(client, demo):
    _, register = demo
    owner, patients, _, _ = register()
    other, others, _, _ = register()
    a = {"headers": owner}
    pid = patients[0]["id"]
    response = request(client, a, pid, "pre-assessment", f001_t2dm_established="是", f002_acute_unsafe="否",
                       f003_type_doubt="否", f004_treatment_context_sufficient="是", f005_refused="否",
                       f061_conclusion="进入完整评估", f018_weight=70, f019_height=165)
    assert response.status_code == 200, response.text
    eid = response.json()["assessment_event_id"]
    before = client.get(f"/api/patients/{pid}", headers=owner).json()["clinical_revision"]
    c = ctx(client, a, pid)
    for suffix in ["context", "records", f"events/{eid}"]:
        route = f"/api/patients/{pid}/clinical-v04/{suffix}"
        assert client.get(route, headers=owner).status_code == 200
        assert client.get(route, headers=other).status_code == 404
    assert client.get(f"/api/patients/{pid}", headers=owner).json()["clinical_revision"] == before
    foreign = client.post(f"/api/patients/{others[0]['id']}/clinical-v04/corrections", headers=other, json={
        "request_id": uuid4().hex, "expected_revision": others[0]["clinical_revision"],
        "record_id": c["measurement"]["id"], "kind": "measurement", "replacement": c["measurement"]["data"],
        "reason": "跨病例补正必须拒绝"})
    assert foreign.status_code == 404


def test_correction_invalidates_current_e4_snapshot_without_rewriting_it(client, v03_test_account, db_session):
    a = v03_test_account
    pid = setup_patient(client, a)
    assert request(client, a, pid, "full-assessment", **full_values(ctx(client, a, pid))).status_code == 200
    patient = db_session.get(Patient, pid)
    patient.current_state = "ST50"
    patient.stage = None
    patient.actual_stop_confirmed = True
    patient.has_glucose_lowering_drug = False
    patient.last_med_stop_date = date(2025, 10, 15)
    patient.applicable_interventions = ["其他"]
    patient.observation_status = "active"
    db_session.commit()
    c = ctx(client, a, pid)
    exam = {"kind": "HbA1c", "value": 6.2, "unit": "%", "source": "本院检查",
            "test_date": "2026-01-15", "reliability": "可靠"}
    judged = request(client, a, pid, "remission-judge", measurement_id=c["measurement"]["id"],
                     regimen_source_id=c["regimen"]["id"], medication_review_complete=True,
                     f041_diagnosis_credible="是", f042_drug_free_3m="是", f043_hba1c_reliable="是",
                     f053_has_drug=False, f059_completeness="完整", f058_examination=exam,
                     examinations=[exam], anchors={"f063_applicable_interventions": ["其他"]})
    assert judged.status_code == 200, judged.text
    assert judged.json()["transition_ids"] == ["T34"]
    event = db_session.get(Event, judged.json()["assessment_event_id"])
    original = event.payload
    corrected = client.post(f"/api/patients/{pid}/clinical-v04/corrections", headers=a["headers"], json={
        "request_id": uuid4().hex, "expected_revision": judged.json()["patient_revision"],
        "record_id": c["measurement"]["id"], "kind": "measurement", "reason": "虚构体重误录",
        "replacement": {**c["measurement"]["data"], "weight_kg": 72}})
    assert corrected.status_code == 200, corrected.text
    stale = request(client, a, pid, "remission-confirm", f048_confirm="确认", assessment_event_id=event.id)
    assert stale.status_code == 422 and stale.json()["code"] == "OBJECTIVE_CHECK_REQUIRED"
    db_session.refresh(event)
    assert event.payload == original


def test_real_v03_upgrade_keeps_rows_payload_and_backup_restore(tmp_path):
    config = migration_config(tmp_path)
    command.upgrade(config, "d03demo001")
    dbpath = tmp_path / "etmms.db"
    payload = json.dumps({"clinical_date":"2026-01-15", "measurement_snapshot":{"weight_kg":73.5,"height_cm":170,"bmi":25.4},
                          "f016_medications":[], "f016_no_medication_confirmed":False}, ensure_ascii=False)
    with sqlite3.connect(dbpath) as db:
        db.execute("INSERT INTO users (id,username,display_name,password_hash,role,is_active,failed_login_count,is_test_account,created_at) VALUES (1,'v04-old','旧账号','unchanged','doctor',1,0,1,'2026-01-01')")
        db.execute("INSERT INTO patients (id,name,gender,birth_date,medical_record_no,department,profile_complete,is_test_patient,current_state,clinical_contract_version,clinical_revision,observation_status,observation_cycle,archived,created_at,updated_at) VALUES (1,'虚构旧病例','女','1980-01-01','migration-v04','内分泌科',1,1,'ST20','v0.3',1,'none',0,0,'2026-01-01','2026-01-01')")
        db.execute("INSERT INTO events (id,patient_id,operator_id,source,rule_id,source_state,target_state,output_text,payload,clinical_contract_version,created_at) VALUES (1,1,1,'doctor','E1-B01','ST10','ST20','原文结论',?,'v0.3','2026-01-15')", (payload,))
    command.upgrade(config, "head")
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT payload FROM events").fetchone()[0] == payload
        assert db.execute("SELECT password_hash FROM users").fetchone()[0] == "unchanged"
        projected = dict(db.execute("SELECT kind,data FROM clinical_records"))
        assert json.loads(projected["measurement"])["measured_on"] is None
        assert json.loads(projected["medication_regimen"])["complete"] is False
        count = db.execute("SELECT count(*) FROM clinical_records").fetchone()[0]
    backups = list((tmp_path / "migration_backups").glob("pre-v04-*.db"))
    assert len(backups) == 1
    restored = tmp_path / "restored.db"
    with sqlite3.connect(backups[0]) as source, sqlite3.connect(restored) as dest:
        source.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert dest.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "d03demo001"
        assert dest.execute("SELECT payload FROM events").fetchone()[0] == payload
    command.upgrade(config, "head")
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT count(*) FROM clinical_records").fetchone()[0] == count
    assert len(list((tmp_path / "migration_backups").glob("pre-v04-*.db"))) == 1


def test_old_tab_cannot_downgrade_new_input_gates(client, v03_test_account):
    a = v03_test_account
    pid = setup_patient(client, a)
    patient = client.get(f"/api/patients/{pid}", headers=a["headers"]).json()
    result = client.post(f"/api/patients/{pid}/clinical-v03/full-assessment", headers=a["headers"], json={
        "request_id": uuid4().hex, "expected_revision": patient["clinical_revision"],
        "f018_weight": 70, "f019_height": 165, "f026_start": "当前不启动"})
    assert result.status_code == 409 and result.json()["code"] == "V04_INPUT_REQUIRED"


def test_weight_only_preassessment_can_confirm_height_with_reference_in_e2(client, v03_test_account):
    a = v03_test_account
    set_date(client, a, "2026-01-15")
    patient = create_patient(client, a, "height-only-" + uuid4().hex[:5])
    reopen(client, a, patient)
    pid = patient["id"]
    saved = request(client, a, pid, "pre-assessment", f018_weight=73.5,
                    f001_t2dm_established="是", f002_acute_unsafe="否", f003_type_doubt="否",
                    f004_treatment_context_sufficient="是", f005_refused="否", f061_conclusion="进入完整评估")
    assert saved.status_code == 200, saved.text
    c = ctx(client, a, pid)
    assert c["measurement"]["data"]["bmi"] is None
    values = full_values(c)
    values.pop("f018_weight")
    values["measurement_id"] = c["measurement"]["id"]
    full = request(client, a, pid, "full-assessment", **values)
    assert full.status_code == 200, full.text
    detail = client.get(f"/api/patients/{pid}/clinical-v04/events/{full.json()['assessment_event_id']}", headers=a["headers"]).json()
    assert detail["payload"]["measurement_snapshot"]["bmi"] == 25.4
    assert detail["payload"]["measurement_snapshot"]["height_cm"] == 170
    assert ctx(client, a, pid)["measurement"]["data"]["bmi"] is None
