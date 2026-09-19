"""
模块名称：patients.py
所属层级：接口层（api）
功能说明：患者档案接口——建档、列表、详情、事件流水（分页）。

临床流程的推进（预评估及之后）在 M4 接入，本文件只处理档案本身。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.models.schemas import EventOut, EventPage, PatientCreateIn, PatientOut
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import events as events_repo
from app.repository import patients as patients_repo
from app.repository.database import get_db

router = APIRouter(prefix="/patients", tags=["患者档案"])


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """建立患者档案。新患者一律从"常规糖尿病综合管理"开始。"""
    # 病历号唯一性预检：给出自然语言提示，而不是让数据库唯一约束报错
    if patients_repo.find_by_medical_record_no(db, payload.medical_record_no) is not None:
        raise ConflictError("该病历号已存在，请核对后重新建档。", code="MRN_DUPLICATED")
    patient = patients_repo.create_patient(
        db,
        name=payload.name,
        gender=payload.gender,
        birth_date=payload.birth_date,
        medical_record_no=payload.medical_record_no,
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
