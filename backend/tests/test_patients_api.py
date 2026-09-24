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

from io import BytesIO

from openpyxl import Workbook
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
    assert body["birth_date"] == "1983-05-01"
    assert body["department"] == "内分泌科"
    assert body["created_by"] == doctor["user"]["id"]
    assert body["profile_complete"] is True


def test_duplicate_medical_record_no_is_rejected(client, doctor) -> None:
    """病历号唯一：重复建档返回 409 与自然语言提示。"""
    client.post("/api/patients", json=_payload("MRN-M2-0002"), headers=doctor["headers"])
    response = client.post("/api/patients", json=_payload("MRN-M2-0002"), headers=doctor["headers"])
    assert response.status_code == 409
    assert "住院号已存在" in response.json()["detail"]


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


def test_reference_data_exports_the_approved_dictionaries(client) -> None:
    """注册页和临床表单只消费后端参考字典，避免前后端选项漂移。"""
    response = client.get("/api/reference")
    assert response.status_code == 200
    body = response.json()
    assert len(body["departments"]) == 69
    assert "内分泌科" in body["departments"]
    assert len(body["diagnosis_bases"]) == 6
    assert "胰岛素及其类似物" in body["drug_classes"]


def test_csv_import_reports_each_row_and_requires_profile_completion(client, doctor) -> None:
    """CSV 导入逐行反馈；重复住院号跳过，成功行必须先完善资料再进入预评估。"""
    csv_content = (
        "姓名,出生年,出生月,性别,住院号,当前科室,联系方式\n"
        "导入患者,1988,7,女,MRN-IMPORT-CSV-1,内分泌科,13800000000\n"
        "重复患者,1988,7,女,MRN-IMPORT-CSV-1,内分泌科,\n"
        "错误患者,1988,13,女,MRN-IMPORT-BAD,内分泌科,\n"
    ).encode()
    response = client.post(
        "/api/patients/import",
        files={"file": ("patients.csv", csv_content, "text/csv")},
        headers=doctor["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["success_count"] == 1
    assert response.json()["skipped_count"] == 1
    assert response.json()["failed_count"] == 1

    patients = client.get("/api/patients", headers=doctor["headers"]).json()
    imported = next(item for item in patients if item["medical_record_no"] == "MRN-IMPORT-CSV-1")
    assert imported["profile_complete"] is False
    blocked = client.post(f"/api/patients/{imported['id']}/reopen", headers=doctor["headers"])
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "PROFILE_INCOMPLETE"

    completed = client.put(
        f"/api/patients/{imported['id']}/profile",
        json={
            "name": "导入患者",
            "gender": "女",
            "birth_date": "1988-07-23",
            "medical_record_no": "MRN-IMPORT-CSV-1",
            "department": "内分泌科",
            "contact_phone": "13800000000",
        },
        headers=doctor["headers"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["profile_complete"] is True
    assert completed.json()["birth_date"] == "1988-07-01"
    assert client.post(f"/api/patients/{imported['id']}/reopen", headers=doctor["headers"]).status_code == 200


def test_xlsx_import_and_measurement_bmi_snapshot(client, doctor) -> None:
    """xlsx 可导入；预评估测量值同步患者档案并形成 BMI 快照。"""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["姓名", "出生年", "出生月", "性别", "住院号", "当前科室", "联系方式"])
    worksheet.append(["表格患者", 1990, 3, "男", "MRN-IMPORT-XLSX-1", "内分泌科", None])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    response = client.post(
        "/api/patients/import",
        files={
            "file": (
                "patients.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=doctor["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["success_count"] == 1

    created = client.post(
        "/api/patients", json=_payload("MRN-MEASURE-1"), headers=doctor["headers"]
    ).json()
    client.post(f"/api/patients/{created['id']}/reopen", headers=doctor["headers"])
    pre = client.post(
        f"/api/patients/{created['id']}/pre-assessment",
        json={
            "f001_t2dm_established": "是",
            "f002_acute_unsafe": "否",
            "f003_type_doubt": "否",
            "f004_treatment_context_sufficient": "是",
            "f005_refused": "否",
            "f018_weight": 70,
            "f019_height": 175,
        },
        headers=doctor["headers"],
    )
    assert pre.status_code == 200, pre.text
    detail = client.get(f"/api/patients/{created['id']}", headers=doctor["headers"]).json()
    assert detail["height_cm"] == 175
    assert detail["weight_kg"] == 70
    assert detail["bmi"] == 22.9
