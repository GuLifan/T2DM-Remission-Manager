"""
模块名称：test_test_support.py
所属层级：后端接口测试
功能说明：验证第一批测试能力的三重守卫、账号级模拟日期、测试患者自动标记与 debug 事件审计。

修改历史：
    - 2026-09-24  v1.0  第一批测试可用性回归测试
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.config import get_settings
from app.models.event import Event
from app.models.user import User
from app.repository import patients as patients_repo


def _patient(db_session, *, is_test_patient: bool):
    """建立隔离的测试用患者记录，避免依赖开发数据库。"""
    patient = patients_repo.create_patient(
        db_session,
        name="测试患者",
        gender="女",
        birth_date=date(1985, 1, 1),
        medical_record_no=f"MRN-TEST-{uuid4().hex[:12]}",
        is_test_patient=is_test_patient,
    )
    db_session.commit()
    return patient


@pytest.fixture()
def enabled_test_account(doctor, db_session):
    """临时开启测试模式并把公共测试账号标记为测试账号，结束后恢复。"""
    settings = get_settings()
    previous_mode = settings.test_mode
    user = db_session.get(User, doctor["user"]["id"])
    assert user is not None
    previous_flag = user.is_test_account
    previous_date = user.simulated_date

    settings.test_mode = True
    user.is_test_account = True
    user.simulated_date = None
    db_session.commit()
    yield doctor

    user = db_session.get(User, doctor["user"]["id"])
    assert user is not None
    user.is_test_account = previous_flag
    user.simulated_date = previous_date
    db_session.commit()
    settings.test_mode = previous_mode


def test_test_mode_is_disabled_by_default(client, doctor, db_session) -> None:
    """即使账号被标记为测试账号，总开关关闭时仍必须返回 403。"""
    settings = get_settings()
    settings.test_mode = False
    user = db_session.get(User, doctor["user"]["id"])
    assert user is not None
    user.is_test_account = True
    db_session.commit()

    response = client.post(
        "/api/test-context/simulated-date",
        headers=doctor["headers"],
        json={"simulated_date": "2030-01-02"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TEST_MODE_DISABLED"

    user.is_test_account = False
    user.simulated_date = None
    db_session.commit()


def test_non_test_account_cannot_set_simulated_date(client, doctor, db_session) -> None:
    """测试模式开启后，普通账号仍不能使用日期后门。"""
    settings = get_settings()
    previous_mode = settings.test_mode
    settings.test_mode = True
    user = db_session.get(User, doctor["user"]["id"])
    assert user is not None
    user.is_test_account = False
    db_session.commit()

    response = client.post(
        "/api/test-context/simulated-date",
        headers=doctor["headers"],
        json={"simulated_date": "2030-01-02"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TEST_ACCOUNT_REQUIRED"
    settings.test_mode = previous_mode


def test_simulated_date_persists_until_cleared(client, enabled_test_account) -> None:
    """模拟日期按账号持久保存，并可主动恢复真实日期。"""
    set_response = client.post(
        "/api/test-context/simulated-date",
        headers=enabled_test_account["headers"],
        json={"simulated_date": "2030-01-02"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["effective_date"] == "2030-01-02"

    read_response = client.get("/api/test-context", headers=enabled_test_account["headers"])
    assert read_response.status_code == 200
    assert read_response.json()["simulated_date"] == "2030-01-02"

    clear_response = client.post(
        "/api/test-context/simulated-date",
        headers=enabled_test_account["headers"],
        json={"simulated_date": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["simulated_date"] is None
    assert clear_response.json()["effective_date"] == clear_response.json()["real_date"]


def test_test_account_created_patient_is_marked_as_test(client, enabled_test_account) -> None:
    """测试模式中的测试账号建档时自动标记测试患者。"""
    response = client.post(
        "/api/patients",
        headers=enabled_test_account["headers"],
        json={
            "name": "自动标记测试患者",
            "gender": "男",
            "birth_date": "1980-01-01",
            "medical_record_no": f"MRN-AUTO-{uuid4().hex[:12]}",
        },
    )
    assert response.status_code == 201
    assert response.json()["is_test_patient"] is True


def test_real_patient_is_blocked_from_debug_and_simulated_date_writes(
    client, enabled_test_account, db_session
) -> None:
    """真实患者既不能测试跳转，也不能在模拟日期下写临床事件。"""
    patient = _patient(db_session, is_test_patient=False)

    jump = client.post(
        f"/api/patients/{patient.id}/debug/jump-state",
        headers=enabled_test_account["headers"],
        json={"target_state": "ST40", "request_id": f"debug-{uuid4().hex}"},
    )
    assert jump.status_code == 403
    assert jump.json()["code"] == "TEST_PATIENT_REQUIRED"

    set_date = client.post(
        "/api/test-context/simulated-date",
        headers=enabled_test_account["headers"],
        json={"simulated_date": "2030-01-02"},
    )
    assert set_date.status_code == 200
    clinical_write = client.post(
        f"/api/patients/{patient.id}/reopen",
        headers=enabled_test_account["headers"],
    )
    assert clinical_write.status_code == 403
    assert clinical_write.json()["code"] == "TEST_PATIENT_REQUIRED"


def test_debug_jump_and_simulated_event_are_auditable(
    client, enabled_test_account, db_session
) -> None:
    """测试跳转必须写 debug 事件，并记录实际模拟日期。"""
    patient = _patient(db_session, is_test_patient=True)
    set_date = client.post(
        "/api/test-context/simulated-date",
        headers=enabled_test_account["headers"],
        json={"simulated_date": "2030-01-02"},
    )
    assert set_date.status_code == 200

    response = client.post(
        f"/api/patients/{patient.id}/debug/jump-state",
        headers=enabled_test_account["headers"],
        json={"target_state": "ST60", "request_id": f"debug-{uuid4().hex}"},
    )
    assert response.status_code == 200
    assert response.json()["current_state"] == "ST60"

    db_session.expire_all()
    event = (
        db_session.query(Event)
        .filter(Event.patient_id == patient.id, Event.source == "debug")
        .order_by(Event.id.desc())
        .first()
    )
    assert event is not None
    assert event.rule_id == "DEBUG-JUMP"
    assert event.simulated_date == date(2030, 1, 2)
