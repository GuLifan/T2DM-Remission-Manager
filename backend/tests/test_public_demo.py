"""公网 demo 契约：邀请、越权读取/写入、重置历史、会话撤销及持久化。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.demo_guard import _attempts
from app.models.demo import DemoInvite
from app.models.patient import Patient
from app.models.user import User
from app.repository.users import create_user


@pytest.fixture()
def demo(client, doctor, db_session):
    settings = get_settings()
    old = settings.demo_mode
    settings.demo_mode = True
    _attempts.clear()
    # 管理员预先由维护工具建立；此处直接在隔离数据库模拟初始化。
    admin = create_user(
        db_session,
        username=f"admin_{uuid4().hex[:8]}",
        display_name="模拟管理员",
        password="Demo-admin-123",
        role="admin",
    )
    admin.is_test_account = True
    db_session.commit()
    login = client.post("/api/auth/login", json={"username": admin.username, "password": "Demo-admin-123"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": "Bearer " + login.json()["token"]}

    def register():
        invite = client.post("/api/admin/invites", headers=headers, json={"label": "模拟医生"})
        assert invite.status_code == 201, invite.text
        payload = {
            "username": "demo_" + uuid4().hex[:8],
            "display_name": "模拟医生",
            "password": "Demo-doctor-123",
            "password_confirm": "Demo-doctor-123",
            "invite_code": invite.json()["code"],
        }
        registered = client.post("/api/auth/register", json=payload)
        assert registered.status_code == 201, registered.text
        login = client.post("/api/auth/login", json={"username": payload["username"], "password": payload["password"]})
        assert login.status_code == 200, login.text
        actor = {"Authorization": "Bearer " + login.json()["token"]}
        cases = client.get("/api/patients", headers=actor).json()
        assert cases == [], "医生注册不得自动生成任何病例"
        # 本地回归夹具通过正式建档接口从零生成，不是部署时病例种子。
        cases = []
        for index in range(3):
            fresh = client.post(
                "/api/demo/cases",
                headers=actor,
                json={
                    "name": f"全新隔离记录-{index}-" + uuid4().hex[:6],
                    "gender": "女",
                    "birth_date": "1988-02-01",
                    "department": "内分泌科",
                },
            )
            assert fresh.status_code == 201, fresh.text
            cases.append(fresh.json())
        assert all(
            p["height_cm"] is None and p["weight_kg"] is None and p["clinical_contract_version"] == "v0.3"
            for p in cases
        )
        return actor, cases, payload, invite.json()["id"]

    yield headers, register
    settings.demo_mode = old
    _attempts.clear()


def test_invite_required_one_use_and_admin_initialization_closed(client, demo, db_session):
    admin, register = demo
    actor, cases, payload, invitation = register()
    assert client.post("/api/auth/register", json={**payload, "username": "x" + uuid4().hex[:8]}).status_code == 422
    assert (
        client.post(
            "/api/auth/register", json={**payload, "username": "x" + uuid4().hex[:8], "invite_code": ""}
        ).status_code
        == 422
    )
    assert client.post("/api/auth/bootstrap", json={}).status_code == 403
    assert client.get("/api/auth/status").json()["needs_bootstrap"] is False
    saved = db_session.get(DemoInvite, invitation)
    assert saved.digest != payload["invite_code"] and saved.used_by is not None


@pytest.mark.parametrize("mode", ["revoked", "expired"])
def test_revoked_expired_invite_rejected(client, demo, db_session, mode):
    admin, _ = demo
    invite = client.post("/api/admin/invites", headers=admin, json={}).json()
    if mode == "revoked":
        client.post(f"/api/admin/invites/{invite['id']}/revoke", headers=admin)
    else:
        db_session.get(DemoInvite, invite["id"]).expires_at = datetime.now() - timedelta(days=1)
        db_session.commit()
    response = client.post(
        "/api/auth/register",
        json={
            "username": "demo_" + uuid4().hex[:8],
            "display_name": "模拟医生",
            "password": "Demo-doctor-123",
            "password_confirm": "Demo-doctor-123",
            "invite_code": invite["code"],
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "suffix,method",
    [
        ("", "get"),
        ("/events", "get"),
        ("/clinical-v03/observation", "get"),
        ("/clinical-v03/pre-assessment", "post"),
        ("/reset", "post"),
        ("/height", "put"),
        ("/debug/jump-state", "post"),
    ],
)
def test_other_doctor_cannot_access_any_patient_subpath(client, demo, suffix, method):
    admin, register = demo
    alice, cases, _, _ = register()
    bob, others, _, _ = register()
    response = getattr(client, method)(f"/api/patients/{cases[0]['id']}{suffix}", headers=bob)
    assert response.status_code == 404, response.text
    assert not {p["id"] for p in cases}.intersection(p["id"] for p in others)
    assert client.get(f"/api/patients/{cases[0]['id']}", headers=admin).status_code == 200


def test_reset_archives_history_is_read_only_and_date_is_personal(client, demo, db_session):
    _, register = demo
    alice, cases, _, _ = register()
    bob, _, _, _ = register()
    old = cases[0]
    assert (
        client.post(
            "/api/test-context/simulated-date", headers=alice, json={"simulated_date": "2026-01-15"}
        ).status_code
        == 403
    )
    assert client.get("/api/test-context", headers=bob).json()["simulated_date"] is None
    events_before = client.get(f"/api/patients/{old['id']}/events", headers=alice).json()
    fresh = client.post(f"/api/patients/{old['id']}/reset", headers=alice)
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["id"] != old["id"] and fresh.json()["current_state"] == "ST10"
    assert fresh.json()["name"] == old["name"] and fresh.json()["birth_date"] == old["birth_date"]
    assert fresh.json()["weight_kg"] is None and fresh.json()["height_cm"] is None
    archived = client.get(f"/api/patients/{old['id']}", headers=alice).json()
    assert archived["archived"] and not archived["can_edit"]
    assert client.get(f"/api/patients/{old['id']}/events", headers=alice).json() == events_before
    assert (
        client.post(f"/api/patients/{old['id']}/clinical-v03/pre-assessment", headers=alice, json={}).status_code == 403
    )
    db_session.expire_all()
    assert db_session.get(Patient, old["id"]).archived


def test_logout_and_disable_revoke_sessions(client, demo, db_session):
    admin, register = demo
    actor, _, payload, _ = register()
    assert client.post("/api/auth/logout", headers=actor).status_code == 204
    assert client.get("/api/auth/me", headers=actor).status_code == 401
    login = client.post(
        "/api/auth/login", json={"username": payload["username"], "password": payload["password"]}
    ).json()
    actor = {"Authorization": "Bearer " + login["token"]}
    user = db_session.scalar(select(User).where(User.username == payload["username"]))
    assert (
        client.put(f"/api/admin/users/{user.id}/enabled", headers=admin, json={"is_active": False}).status_code == 200
    )
    assert client.get("/api/auth/me", headers=actor).status_code == 401


def test_old_writes_and_admin_endpoints_closed_to_doctors(client, demo):
    _, register = demo
    actor, cases, _, _ = register()
    for path in ["/api/admin/users", "/api/admin/invites"]:
        assert client.get(path, headers=actor).status_code == 403
    for suffix in ["/debug/jump-state", "/profile", "/owner", "/reopen", "/phase-review"]:
        assert client.post(f"/api/patients/{cases[0]['id']}{suffix}", headers=actor).status_code == 403
    assert client.post("/api/patients/import", headers=actor).status_code == 403


def test_concurrent_invite_consumption_registers_only_one_doctor(client, demo):
    admin, _ = demo
    invitation = client.post("/api/admin/invites", headers=admin, json={}).json()

    def register_one(index):
        return client.post(
            "/api/auth/register",
            json={
                "username": f"race_{index}_" + uuid4().hex[:8],
                "display_name": "模拟并发医生",
                "password": "Synthetic-password-123",
                "password_confirm": "Synthetic-password-123",
                "invite_code": invitation["code"],
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(register_one, [1, 2]))
    assert sorted(statuses) == [201, 422]


def test_validation_does_not_echo_credentials_and_auth_is_rate_limited(client, demo):
    secret = "Synthetic-private-input-123"
    invalid = client.post("/api/auth/register", json={"username": "x", "password": secret, "invite_code": secret})
    assert invalid.status_code == 422
    assert secret not in invalid.text
    _attempts.clear()
    statuses = [
        client.post("/api/auth/login", json={"username": "missing-qa", "password": secret}).status_code
        for _ in range(21)
    ]
    assert statuses[:20] == [422] * 20 and statuses[20] == 429


def test_fresh_registration_has_zero_records_and_manual_case_has_no_clinical_history(client, demo):
    admin, _ = demo
    invite = client.post("/api/admin/invites", headers=admin, json={}).json()
    username = "fresh_" + uuid4().hex[:8]
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": "从零测试医师",
            "password": "Fresh-synthetic-123",
            "password_confirm": "Fresh-synthetic-123",
            "invite_code": invite["code"],
        },
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": username, "password": "Fresh-synthetic-123"}).json()
    actor = {"Authorization": "Bearer " + login["token"]}
    assert client.get("/api/patients", headers=actor).json() == []
    assert client.post("/api/demo/cases", headers=actor, json={"case_number": 1}).status_code == 422
    assert client.post("/api/demo/cases", headers=actor, json={}).status_code == 422
    assert client.get("/api/patients", headers=actor).json() == []
    created = client.post(
        "/api/demo/cases",
        headers=actor,
        json={"name": "新编虚构甲", "gender": "男", "birth_date": "1990-05-15", "department": "内分泌科"},
    )
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["name"] == "新编虚构甲" and case["birth_date"] == "1990-05-01"
    assert case["current_state"] == "ST10" and case["demo_case"] is None
    for key in [
        "height_cm",
        "weight_kg",
        "bmi",
        "stage",
        "last_med_stop_date",
        "remission_confirmed_date",
        "has_glucose_lowering_drug",
    ]:
        assert case[key] is None
    assert client.get(f"/api/patients/{case['id']}/events", headers=actor).json()["total"] == 0
