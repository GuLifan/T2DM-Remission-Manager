"""0.4.1日期权限与既有数据兼容；只使用隔离库，不更改真实运行数据。"""
import json
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_public_demo import demo as demo

from app.core.clock import system_clock
from app.core.test_mode import effective_today_for_patient, simulated_date_for_event
from app.models.audit import AuditLog
from app.models.event import Event
from app.models.patient import Patient
from app.models.user import User


@pytest.mark.parametrize("requested", [None, "2050-01-01"])
def test_doctor_cannot_set_or_clear_date_even_with_old_saved_value(client, demo, db_session, monkeypatch, requested):
    admin, register = demo
    headers, cases, payload, _ = register()
    actor = db_session.scalar(select(User).where(User.username == payload["username"]))
    actor.simulated_date = date(2050, 1, 1)
    db_session.commit()
    monkeypatch.setattr(system_clock, "today", lambda: date(2026, 10, 20))
    context = client.get("/api/test-context", headers=headers).json()
    assert context["effective_date"] == context["real_date"] == "2026-10-20"
    assert context["can_manage_date"] is False and context["simulated_date"] is None
    denied = client.post("/api/test-context/simulated-date", headers=headers, json={"simulated_date": requested})
    assert denied.status_code == 403 and denied.json()["code"] == "ADMIN_REQUIRED"
    assert client.get("/api/auth/me", headers=headers).json()["simulated_date"] is None
    db_session.refresh(actor)
    assert actor.simulated_date == date(2050, 1, 1), "旧值留存，但不能再驱动业务日期"
    patient = db_session.get(Patient, cases[0]["id"])
    assert effective_today_for_patient(actor, patient) == date(2026, 10, 20)
    assert simulated_date_for_event(actor, patient) is None
    # 管理员自己的日期仍可维护，普通账号上下文不跟随。
    assert client.post("/api/test-context/simulated-date", headers=admin, json={"simulated_date": "2027-02-01"}).status_code == 200
    assert client.get("/api/test-context", headers=headers).json()["effective_date"] == "2026-10-20"


def test_doctor_new_event_uses_real_date_and_preserves_original_number(client, demo, db_session, monkeypatch):
    _, register = demo
    headers, cases, payload, _ = register()
    actor = db_session.scalar(select(User).where(User.username == payload["username"]))
    actor.simulated_date = date(2050, 1, 1)
    db_session.commit()
    monkeypatch.setattr(system_clock, "today", lambda: date(2026, 10, 20))
    patient = cases[0]
    before_number = patient["medical_record_no"]
    saved = client.post(f"/api/patients/{patient['id']}/clinical-v03/pre-assessment", headers=headers, json={
        "input_schema_version": "v0.4", "request_id": uuid4().hex, "expected_revision": patient["clinical_revision"],
        "f001_t2dm_established": "是", "f002_acute_unsafe": "否", "f003_type_doubt": "否",
        "f004_treatment_context_sufficient": "是", "f005_refused": "否", "f061_conclusion": "进入完整评估",
    })
    assert saved.status_code == 200, saved.text
    event = db_session.scalar(select(Event).where(Event.patient_id == patient["id"]).order_by(Event.id.desc()))
    assert json.loads(event.payload)["clinical_date"] == "2026-10-20" and event.simulated_date is None
    response = client.get(f"/api/patients/{patient['id']}", headers=headers).json()
    assert response["display_record_no"] == f"ETMMS-{patient['id']:06d}"
    assert response["medical_record_no"] == before_number
    assert db_session.get(Patient, patient["id"]).medical_record_no == before_number


def test_admin_date_changes_are_audited_and_do_not_rewrite_history(client, demo, db_session):
    admin, register = demo
    headers, cases, _, _ = register()
    pid = cases[0]["id"]
    history = client.get(f"/api/patients/{pid}/events", headers=headers).json()
    before = db_session.query(AuditLog).filter(AuditLog.action == "simulated_date_set").count()
    for value in ["2027-01-01", None]:
        response = client.post("/api/test-context/simulated-date", headers=admin, json={"simulated_date": value})
        assert response.status_code == 200 and response.json()["can_manage_date"] is True
        assert response.json()["simulated_date"] == value
    assert db_session.query(AuditLog).filter(AuditLog.action == "simulated_date_set").count() == before + 1
    assert client.get(f"/api/patients/{pid}/events", headers=headers).json() == history
    fresh = client.post(f"/api/patients/{pid}/reset", headers=headers)
    assert fresh.status_code == 201 and fresh.json()["id"] != pid
    assert client.get(f"/api/patients/{pid}", headers=headers).json()["archived"] is True
