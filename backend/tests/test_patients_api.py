"""
模块名称：test_patients_api.py
所属层级：测试（tests）
功能说明：验证患者档案接口与审计记录。

覆盖内容：
    1. 建档成功且初始状态为常规管理；
    2. 病历号重复被拒（自然语言提示）；
    3. 列表、详情、不存在时的 404；
    4. 事件流水接口可用（初始为空）；
    5. 建档写入审计日志。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog


def _payload(mrn: str) -> dict:
    """构造建档请求体（测试数据，非真实患者）。"""
    return {
        "name": "测试患者",
        "gender": "女",
        "birth_date": "1983-05-12",
        "medical_record_no": mrn,
    }


def test_create_patient_starts_in_regular_care(client, doctor) -> None:
    """建档成功后患者处于常规糖尿病综合管理（ST00）。"""
    response = client.post("/api/patients", json=_payload("MRN-M2-0001"), headers=doctor["headers"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["current_state"] == "ST00"
    assert body["medical_record_no"] == "MRN-M2-0001"
    # 新建档案不应带有阶段信息
    assert body["stage"] is None


def test_duplicate_medical_record_no_is_rejected(client, doctor) -> None:
    """病历号唯一：重复建档返回 409 与自然语言提示。"""
    client.post("/api/patients", json=_payload("MRN-M2-0002"), headers=doctor["headers"])
    response = client.post("/api/patients", json=_payload("MRN-M2-0002"), headers=doctor["headers"])
    assert response.status_code == 409
    assert "病历号已存在" in response.json()["detail"]


def test_list_and_get_patient(client, doctor) -> None:
    """列表包含已建档案；详情可按主键读取。"""
    created = client.post(
        "/api/patients", json=_payload("MRN-M2-0003"), headers=doctor["headers"]
    ).json()

    listed = client.get("/api/patients", headers=doctor["headers"])
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())

    detail = client.get(f"/api/patients/{created['id']}", headers=doctor["headers"])
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]


def test_missing_patient_returns_friendly_404(client, doctor) -> None:
    """不存在的患者返回自然语言 404。"""
    response = client.get("/api/patients/999999", headers=doctor["headers"])
    assert response.status_code == 404
    assert response.json()["detail"] == "未找到该患者档案。"


def test_events_endpoint_is_paginated_and_initially_empty(client, doctor) -> None:
    """新建档案的事件流水应为空，且接口为分页结构。"""
    created = client.post(
        "/api/patients", json=_payload("MRN-M2-0004"), headers=doctor["headers"]
    ).json()
    response = client.get(f"/api/patients/{created['id']}/events", headers=doctor["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_patient_creation_is_audited(client, doctor, db_session) -> None:
    """建档必须写入审计日志，且日志中不含病历内容。"""
    client.post("/api/patients", json=_payload("MRN-M2-0005"), headers=doctor["headers"])
    rows = db_session.scalars(select(AuditLog).where(AuditLog.action == "patient_create")).all()
    assert rows, "建档未写入审计日志"
    # 审计只记录对象与操作者，不记录姓名等病历内容
    for row in rows:
        assert row.target_type == "patient"
        assert "测试患者" not in (row.detail or "")
