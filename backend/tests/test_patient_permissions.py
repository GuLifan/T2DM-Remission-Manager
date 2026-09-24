"""
模块名称：test_patient_permissions.py
所属层级：后端接口测试
功能说明：验证第三批正式角色、患者责任归属、横向权限与转移审计。

关键边界：
    1. 所有登录账号都可以读取患者，但普通医生只能写自己负责的患者；
    2. 管理员可以写全部患者，并且只有管理员可以转移责任归属；
    3. 测试账号标记不授予管理权限，也不得绕过患者责任归属；
    4. 转移只改变 owner_id，created_by 永久保留。
"""

from __future__ import annotations

from datetime import datetime

from app.config import get_settings
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.user import User

PASSWORD = "Permission-Passw0rd"


def _doctor_login(client, username: str, display_name: str) -> dict:
    """通过公开注册准备普通医生并返回登录态；重复运行时直接复用账号。"""
    registered = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": display_name,
            "department": "内分泌科",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
    )
    assert registered.status_code in {201, 409}, registered.text
    login = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["user"]["role"] == "doctor"
    return {
        "headers": {"Authorization": f"Bearer {body['token']}"},
        "user": body["user"],
    }


def _patient_payload(mrn: str) -> dict:
    """构造与真实患者无关的最小测试档案。"""
    return {
        "name": "权限测试患者",
        "gender": "女",
        "birth_date": "1988-06-01",
        "medical_record_no": mrn,
    }


def test_all_accounts_can_read_but_non_owner_cannot_write(client, doctor) -> None:
    """非责任医生可看列表和详情，但任何档案或流程写入都返回统一 403。"""
    other = _doctor_login(client, "permission_reader", "只读医生")
    created = client.post(
        "/api/patients",
        json=_patient_payload("MRN-PERM-READ"),
        headers=doctor["headers"],
    ).json()

    listed = client.get("/api/patients", headers=other["headers"])
    assert listed.status_code == 200
    listed_patient = next(item for item in listed.json() if item["id"] == created["id"])
    assert listed_patient["can_edit"] is False
    assert listed_patient["owner_display_name"] == doctor["user"]["display_name"]

    detail = client.get(f"/api/patients/{created['id']}", headers=other["headers"])
    assert detail.status_code == 200
    assert detail.json()["can_edit"] is False

    blocked = client.post(f"/api/patients/{created['id']}/reopen", headers=other["headers"])
    assert blocked.status_code == 403
    assert blocked.json() == {
        "detail": "您的账户暂无权限编辑此条记录",
        "code": "PATIENT_WRITE_FORBIDDEN",
    }


def test_admin_transfer_is_audited_and_flips_doctor_permissions(
    client, doctor, db_session
) -> None:
    """管理员转移后新责任医生立即可写、原责任医生立即只读，创建者不变。"""
    original = _doctor_login(client, "permission_owner_a", "责任医生甲")
    new_owner = _doctor_login(client, "permission_owner_b", "责任医生乙")
    created_response = client.post(
        "/api/patients",
        json=_patient_payload("MRN-PERM-TRANSFER"),
        headers=original["headers"],
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()

    patient = db_session.get(Patient, created["id"])
    assert patient is not None
    patient.updated_at = datetime(2020, 1, 1)
    db_session.commit()

    denied_list = client.get("/api/auth/assignable-doctors", headers=original["headers"])
    assert denied_list.status_code == 403
    available = client.get("/api/auth/assignable-doctors", headers=doctor["headers"])
    assert available.status_code == 200
    assert new_owner["user"]["id"] in {item["id"] for item in available.json()}
    assert doctor["user"]["id"] not in {item["id"] for item in available.json()}

    transferred = client.put(
        f"/api/patients/{created['id']}/owner",
        json={"owner_id": new_owner["user"]["id"]},
        headers=doctor["headers"],
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["created_by"] == original["user"]["id"]
    assert transferred.json()["owner_id"] == new_owner["user"]["id"]
    assert transferred.json()["owner_display_name"] == new_owner["user"]["display_name"]
    assert transferred.json()["can_edit"] is True
    assert datetime.fromisoformat(transferred.json()["updated_at"]) > datetime(2020, 1, 1)

    old_view = client.get(f"/api/patients/{created['id']}", headers=original["headers"])
    new_view = client.get(f"/api/patients/{created['id']}", headers=new_owner["headers"])
    assert old_view.json()["can_edit"] is False
    assert new_view.json()["can_edit"] is True
    assert client.post(
        f"/api/patients/{created['id']}/reopen", headers=original["headers"]
    ).status_code == 403
    assert client.post(
        f"/api/patients/{created['id']}/reopen", headers=new_owner["headers"]
    ).status_code == 200

    db_session.expire_all()
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "patient_owner_transfer",
            AuditLog.target_id == created["id"],
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert str(original["user"]["id"]) in (audit.detail or "")
    assert str(new_owner["user"]["id"]) in (audit.detail or "")


def test_test_account_flag_does_not_bypass_patient_ownership(client, doctor, db_session) -> None:
    """普通医生即使带测试账号标记，也不能跳转其他医生负责的测试患者。"""
    test_doctor = _doctor_login(client, "permission_test_doctor", "测试权限医生")
    target = client.post(
        "/api/patients",
        json=_patient_payload("MRN-PERM-TEST-GUARD"),
        headers=doctor["headers"],
    ).json()

    settings = get_settings()
    previous_mode = settings.test_mode
    user = db_session.get(User, test_doctor["user"]["id"])
    patient = db_session.get(Patient, target["id"])
    assert user is not None and patient is not None
    previous_flag = user.is_test_account
    previous_patient_flag = patient.is_test_patient
    settings.test_mode = True
    user.is_test_account = True
    patient.is_test_patient = True
    db_session.commit()
    try:
        blocked = client.post(
            f"/api/patients/{target['id']}/debug/jump-state",
            json={"target_state": "ST40"},
            headers=test_doctor["headers"],
        )
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "PATIENT_WRITE_FORBIDDEN"
    finally:
        user = db_session.get(User, test_doctor["user"]["id"])
        patient = db_session.get(Patient, target["id"])
        assert user is not None and patient is not None
        user.is_test_account = previous_flag
        patient.is_test_patient = previous_patient_flag
        db_session.commit()
        settings.test_mode = previous_mode
