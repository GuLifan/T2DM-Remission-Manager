"""
模块名称：test_auth_api.py
所属层级：测试（tests）
功能说明：验证账号接口的完整链路与防护行为。

覆盖内容：
    1. 首次引导创建账号、重复引导被拒；
    2. 登录成功、密码错误、账号锁定；
    3. 会话令牌访问受保护接口、无令牌被拒、登出写审计；
    4. 审计日志确实记录了登录与失败。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog
from app.repository import users as users_repo
from tests.conftest import TEST_DOCTOR


def test_status_reports_bootstrap_needed_then_done(client, doctor) -> None:
    """引导创建之后，状态接口应报告不需要再引导。"""
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["needs_bootstrap"] is False
    assert doctor["user"]["role"] == "admin"


def test_open_registration_requires_matching_password_and_valid_department(client, doctor) -> None:
    """开放注册成功后不自动登录；密码确认与科室字典均由后端再次校验。"""
    registered = client.post(
        "/api/auth/register",
        json={
            "username": "doctor_registered",
            "display_name": "注册医生",
            "department": "内分泌科",
            "password": "Register-Passw0rd",
            "password_confirm": "Register-Passw0rd",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["message"] == "注册成功，请使用新账号登录。"

    login = client.post(
        "/api/auth/login",
        json={"username": "doctor_registered", "password": "Register-Passw0rd"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["department"] == "内分泌科"
    assert login.json()["user"]["role"] == "doctor"

    mismatch = client.post(
        "/api/auth/register",
        json={
            "username": "doctor_mismatch",
            "display_name": "密码不一致",
            "password": "Register-Passw0rd",
            "password_confirm": "Different-Passw0rd",
        },
    )
    assert mismatch.status_code == 422

    invalid_department = client.post(
        "/api/auth/register",
        json={
            "username": "doctor_bad_department",
            "display_name": "错误科室",
            "department": "不存在的科室",
            "password": "Register-Passw0rd",
            "password_confirm": "Register-Passw0rd",
        },
    )
    assert invalid_department.status_code == 422


def test_bootstrap_rejected_when_accounts_exist(client, doctor) -> None:
    """已存在账号时再次引导必须被拒绝（防止凭空建号）。"""
    response = client.post("/api/auth/bootstrap", json=TEST_DOCTOR)
    assert response.status_code == 409
    assert "已存在账号" in response.json()["detail"]


def test_login_success_and_me(client, doctor) -> None:
    """登录成功后可读取当前账号信息。"""
    login = client.post(
        "/api/auth/login",
        json={"username": TEST_DOCTOR["username"], "password": TEST_DOCTOR["password"]},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == TEST_DOCTOR["display_name"]
    # 响应中不得出现任何凭据字段
    assert "password_hash" not in me.json()


def test_login_rejects_wrong_password(client, doctor) -> None:
    """密码错误时返回统一的自然语言提示。"""
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_DOCTOR["username"], "password": "definitely-wrong"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "登录名或密码不正确。"


def test_login_rejects_unknown_account_with_same_message(client, doctor) -> None:
    """账号不存在与密码错误必须返回同一句提示，避免账号枚举。"""
    response = client.post(
        "/api/auth/login",
        json={"username": "no_such_doctor", "password": "whatever-123"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "登录名或密码不正确。"


def test_account_locks_after_repeated_failures(client, db_session) -> None:
    """连续失败达到阈值后账号被短期锁定。"""
    # 单独建一个账号，避免影响其他测试使用的账号
    users_repo.create_user(
        db_session,
        username="lock_target",
        display_name="锁定测试",
        password="Test-Passw0rd",
    )
    db_session.commit()

    for _ in range(users_repo.LOCK_THRESHOLD):
        response = client.post(
            "/api/auth/login",
            json={"username": "lock_target", "password": "wrong-password"},
        )
        assert response.status_code == 422

    # 再次尝试（即使密码正确）应被锁定拦截
    locked = client.post(
        "/api/auth/login",
        json={"username": "lock_target", "password": "Test-Passw0rd"},
    )
    assert locked.status_code == 422
    assert "临时锁定" in locked.json()["detail"]


def test_protected_endpoint_requires_token(client) -> None:
    """无令牌访问受保护接口必须返回 401 与自然语言提示。"""
    response = client.get("/api/patients")
    assert response.status_code == 401
    assert "登录" in response.json()["detail"]


def test_protected_endpoint_rejects_bad_token(client) -> None:
    """无效令牌必须被拒绝。"""
    response = client.get("/api/patients", headers={"Authorization": "Bearer v1.bad.token"})
    assert response.status_code == 401


def test_logout_writes_audit(client, doctor, db_session) -> None:
    """登出应写入审计日志。"""
    response = client.post("/api/auth/logout", headers=doctor["headers"])
    assert response.status_code == 204

    actions = set(db_session.scalars(select(AuditLog.action)).all())
    # 登录（含引导）与登出都应留下痕迹
    assert "logout" in actions
    assert actions & {"login", "account_bootstrap"}


def test_login_failure_is_audited(client, db_session) -> None:
    """登录失败必须写入审计日志（含原因）。"""
    client.post("/api/auth/login", json={"username": "audit_target", "password": "x" * 8})
    rows = db_session.scalars(select(AuditLog).where(AuditLog.action == "login_failed")).all()
    assert rows, "登录失败未写入审计日志"
    # 审计细节中不得包含密码
    for row in rows:
        assert "x" * 8 not in (row.detail or "")
