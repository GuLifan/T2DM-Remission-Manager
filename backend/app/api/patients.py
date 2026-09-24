"""
模块名称：patients.py
所属层级：接口层（api）
功能说明：患者档案接口——建档、列表、详情、事件流水（分页）。

临床流程的推进（预评估及之后）在 M4 接入，本文件只处理档案本身。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import record_outcome, require_profile_complete
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.test_mode import test_capability_enabled
from app.domain import templates
from app.domain.states import ST00, ST10
from app.models.schemas import (
    EventOut,
    EventPage,
    ImportRowResult,
    PatientCreateIn,
    PatientImportOut,
    PatientOut,
    PatientProfileUpdateIn,
)
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import departments as departments_repo
from app.repository import events as events_repo
from app.repository import patients as patients_repo
from app.repository.database import get_db
from app.services.patient_import import parse_patient_import

router = APIRouter(prefix="/patients", tags=["患者档案"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _cell_text(value: object, label: str) -> str:
    """把导入单元格归一为非空文本；错误文案指向医生看到的中文列名。"""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{label}不能为空。")
    return text


def _cell_int(value: object, label: str) -> int:
    """读取 Excel/CSV 中的整数，拒绝 1980.5 之类模糊值。"""
    text = _cell_text(value, label)
    number = float(text)
    if not number.is_integer():
        raise ValueError(f"{label}必须为整数。")
    return int(number)


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """建立患者档案。新患者一律从"常规糖尿病综合管理"开始。"""
    medical_record_no = payload.medical_record_no.strip()
    name = payload.name.strip()
    if not name or not medical_record_no:
        raise BusinessRuleError("姓名和住院号不能为空。", code="PATIENT_PROFILE_INVALID")
    # 住院号唯一性预检：给出自然语言提示，而不是让数据库唯一约束报错
    if patients_repo.find_by_medical_record_no(db, medical_record_no) is not None:
        raise ConflictError("该住院号已存在，请核对后重新建档。", code="MRN_DUPLICATED")
    if not departments_repo.is_active_name(db, payload.department):
        raise BusinessRuleError("所选科室不在当前科室字典中，请重新选择。", code="DEPARTMENT_INVALID")
    patient = patients_repo.create_patient(
        db,
        name=name,
        gender=payload.gender,
        birth_date=payload.birth_date,
        medical_record_no=medical_record_no,
        department=payload.department,
        contact_phone=payload.contact_phone.strip() if payload.contact_phone else None,
        created_by=current_user.id,
        # 测试模式中的测试账号所建患者自动进入测试数据边界；普通入口不提供手工切换
        is_test_patient=test_capability_enabled(current_user),
    )
    # 审计只记录"谁建了档"，不记录病历内容
    audit_repo.write_audit(
        db,
        action="patient_create",
        operator_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()
    return PatientOut.model_validate(patient)


@router.post("/import", response_model=PatientImportOut)
async def import_patients(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientImportOut:
    """批量导入 xlsx/csv；重复住院号跳过，其他问题逐行报告。"""
    filename = file.filename or ""
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise BusinessRuleError("导入文件不能超过 5 MB。", code="IMPORT_TOO_LARGE")
    try:
        parsed_rows = parse_patient_import(filename, content)
    except ValueError as exc:
        raise BusinessRuleError(str(exc), code="IMPORT_FILE_INVALID") from exc

    valid_departments = {item.name for item in departments_repo.list_active(db)}
    seen_numbers: set[str] = set()
    results: list[ImportRowResult] = []
    success_count = skipped_count = failed_count = 0

    for row_number, raw in parsed_rows:
        medical_record_no: str | None = None
        try:
            name = _cell_text(raw["姓名"], "姓名")
            birth_year = _cell_int(raw["出生年"], "出生年")
            birth_month = _cell_int(raw["出生月"], "出生月")
            gender = _cell_text(raw["性别"], "性别")
            medical_record_no = _cell_text(raw["住院号"], "住院号")
            department = _cell_text(raw["当前科室"], "当前科室")
            contact_phone = str(raw["联系方式"]).strip() if raw["联系方式"] is not None else None
            contact_phone = contact_phone or None

            if gender not in {"男", "女"}:
                raise ValueError("性别只能填写男或女。")
            if not 1900 <= birth_year <= date.today().year:
                raise ValueError("出生年超出允许范围。")
            if not 1 <= birth_month <= 12:
                raise ValueError("出生月必须为 1–12。")
            if department not in valid_departments:
                raise ValueError("当前科室不在科室字典中。")
            if len(contact_phone or "") > 64:
                raise ValueError("联系方式不能超过 64 个字符。")

            if medical_record_no in seen_numbers or patients_repo.find_by_medical_record_no(db, medical_record_no):
                skipped_count += 1
                seen_numbers.add(medical_record_no)
                results.append(
                    ImportRowResult(
                        row=row_number,
                        medical_record_no=medical_record_no,
                        status="skipped",
                        message="住院号重复，已跳过且未覆盖既有患者。",
                    )
                )
                continue

            patients_repo.create_patient(
                db,
                name=name,
                gender=gender,
                birth_date=date(birth_year, birth_month, 1),
                medical_record_no=medical_record_no,
                department=department,
                contact_phone=contact_phone,
                created_by=current_user.id,
                profile_complete=False,
                is_test_patient=test_capability_enabled(current_user),
            )
            seen_numbers.add(medical_record_no)
            success_count += 1
            results.append(
                ImportRowResult(
                    row=row_number,
                    medical_record_no=medical_record_no,
                    status="success",
                    message="导入成功，首次使用前需完善患者资料。",
                )
            )
        except (TypeError, ValueError) as exc:
            failed_count += 1
            results.append(
                ImportRowResult(
                    row=row_number,
                    medical_record_no=medical_record_no,
                    status="failed",
                    message=str(exc),
                )
            )

    audit_repo.write_audit(
        db,
        action="patient_import",
        operator_id=current_user.id,
        target_type="patient_batch",
        detail={
            "filename": filename,
            "success_count": success_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        },
    )
    db.commit()
    return PatientImportOut(
        success_count=success_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        rows=results,
    )


@router.get("", response_model=list[PatientOut])
def list_patients(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PatientOut]:
    """列出患者档案（按建档时间倒序）。"""
    return [PatientOut.model_validate(item) for item in patients_repo.list_patients(db)]


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """查询单个患者档案。"""
    patient = patients_repo.get_patient(db, patient_id)
    if patient is None:
        raise NotFoundError("未找到该患者档案。")
    return PatientOut.model_validate(patient)


@router.put("/{patient_id}/profile", response_model=PatientOut)
def update_patient_profile(
    patient_id: int,
    payload: PatientProfileUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """核对并完善患者基本资料；完成后解除预评估门禁。"""
    patient = patients_repo.get_patient(db, patient_id)
    if patient is None:
        raise NotFoundError("未找到该患者档案。")
    medical_record_no = payload.medical_record_no.strip()
    name = payload.name.strip()
    if not name or not medical_record_no:
        raise BusinessRuleError("姓名和住院号不能为空。", code="PATIENT_PROFILE_INVALID")
    duplicated = patients_repo.find_by_medical_record_no(db, medical_record_no)
    if duplicated is not None and duplicated.id != patient.id:
        raise ConflictError("该住院号已存在，请核对后重新填写。", code="MRN_DUPLICATED")
    if not departments_repo.is_active_name(db, payload.department):
        raise BusinessRuleError("所选科室不在当前科室字典中，请重新选择。", code="DEPARTMENT_INVALID")
    patients_repo.update_profile(
        db,
        patient,
        name=name,
        gender=payload.gender,
        birth_date=payload.birth_date,
        medical_record_no=medical_record_no,
        department=payload.department,
        contact_phone=payload.contact_phone.strip() if payload.contact_phone else None,
    )
    audit_repo.write_audit(
        db,
        action="patient_profile_complete",
        operator_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
    )
    db.commit()
    return PatientOut.model_validate(patient)


@router.get("/{patient_id}/events", response_model=EventPage)
def list_events(
    patient_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventPage:
    """查询患者的事件流水（按时间倒序分页）。"""
    if patients_repo.get_patient(db, patient_id) is None:
        raise NotFoundError("未找到该患者档案。")
    total = events_repo.count_events(db, patient_id)
    items = [EventOut.model_validate(item) for item in events_repo.list_events(db, patient_id, limit=limit, offset=offset)]
    return EventPage(total=total, items=items)


@router.post("/{patient_id}/reopen", response_model=PatientOut)
def reopen_pre_assessment(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """从常规糖尿病综合管理重新发起 60 秒预评估（ST00 → ST10）。

    为什么需要：锁定稿§11 规定"条件或意愿改变时可重新发起预评估"，
    这是常规管理状态的合法出口；不构成新增临床节点。
    """
    patient = patients_repo.get_patient(db, patient_id)
    if patient is None:
        raise NotFoundError("未找到该患者档案。")
    require_profile_complete(patient)
    if patient.current_state != ST00:
        raise BusinessRuleError(
            "只有处于常规糖尿病综合管理的患者才能重新发起预评估。", code="WRONG_STATE"
        )
    source_state = patient.current_state
    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=ST10,
        rule_id="REOPEN",
        template_id="SYS-ST00-REOPEN",
        output_text=templates.render("SYS-ST00-REOPEN"),
        payload=None,
    )
    return PatientOut.model_validate(patient)
