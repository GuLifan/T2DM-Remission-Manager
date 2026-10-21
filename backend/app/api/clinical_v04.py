"""v0.4资料读取与补正；临床转移仍使用v0.3锁定契约。"""
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, require_patient_write_access, require_revision
from app.core.exceptions import ConflictError, NotFoundError
from app.core.test_mode import effective_today_for_patient
from app.models.clinical_v03 import ClinicalExamination, MedicationRecord, V03Request
from app.models.event import Event
from app.models.user import User
from app.repository import audit
from app.repository.database import get_db
from app.services import clinical_records as records

router = APIRouter(prefix="/patients/{patient_id}/clinical-v04", tags=["临床资料"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]


def read_patient(db, pid, user):
    patient = get_patient_or_404(db, pid)
    # 此守卫独立于demo中间件，非demo环境也不允许横向读取。
    if user.role != "admin" and patient.owner_id != user.id:
        raise NotFoundError("未找到该病例。")
    return patient


@router.get("/context")
def context(patient_id: int, user: Actor, db: DB):
    patient = read_patient(db, patient_id, user)
    return records.context(db, patient, effective_today_for_patient(user, patient))


@router.get("/records")
def list_records(patient_id: int, user: Actor, db: DB):
    read_patient(db, patient_id, user)
    return [records.out(r, db) for r in records.records(db, patient_id)]


@router.get("/events/{event_id}")
def event_detail(patient_id: int, event_id: int, user: Actor, db: DB):
    read_patient(db, patient_id, user)
    event = db.get(Event, event_id)
    if event is None or event.patient_id != patient_id:
        raise NotFoundError("未找到该病例的评估记录。")
    return {"id": event.id, "output_text": event.output_text, "payload": json.loads(event.payload or "{}"),
            "operator_id": event.operator_id, "created_at": event.created_at,
            "operator_display_name": db.get(User, event.operator_id).display_name if db.get(User, event.operator_id) else "历史账号",
            "corrections": [records.out(r, db) for r in records.records(db, patient_id, "correction")
                            if r.data.get("source_event_id") == event_id]}


class Correction(V03Request):
    record_id: int = Field(gt=0)
    kind: Literal["measurement", "examination", "medication_regimen", "duration"]
    reason: str = Field(min_length=1, max_length=2000)
    replacement: dict


@router.post("/corrections")
def correction(patient_id: int, payload: Correction, user: Actor, db: DB):
    try:
        return save_correction(patient_id, payload, user, db)
    except (ValidationError, TypeError, KeyError):
        db.rollback()
        records.fail("补正资料格式或内容无效，请核对字段、日期和数值")


def save_correction(patient_id: int, payload: Correction, user: Actor, db: DB):
    patient = read_patient(db, patient_id, user)
    require_patient_write_access(user, patient)
    require_revision(patient, payload.expected_revision)
    if any(r.data.get("request_id") == payload.request_id for r in records.records(db, patient_id, "correction")):
        raise ConflictError("该补正已保存，本次未重复记录。")
    previous = records.reference(db, patient_id, payload.record_id, payload.kind)
    latest = records.latest(db, patient_id, payload.kind)
    if payload.kind in {"medication_regimen", "duration"} and previous.id != latest.id:
        records.fail("请对当前有效资料补正，旧方案只能回看")
    today = effective_today_for_patient(user, patient)
    data = payload.replacement
    if payload.kind == "examination":
        exam = ClinicalExamination.model_validate(data)
        records.validate_exam_dates(exam, today)
        data = exam.model_dump(mode="json")
    elif payload.kind == "measurement":
        # 身高更正继续使用管理员专用接口，普通医生只能补正体重/测量日期。
        weight = data.get("weight_kg")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 < weight <= 500:
            records.fail("体重须大于0且不超过500kg")
        if data.get("height_cm") != previous.data.get("height_cm"):
            records.fail("身高更正请使用管理员专用入口")
        raw = data.get("measured_on")
        try:
            measured = date.fromisoformat(raw) if raw else None
        except (ValueError, TypeError):
            records.fail("测量日期无效")
        if measured:
            records.require_nonfuture(measured, today, "测量日期")
        height = data.get("height_cm")
        data = {"weight_kg": weight, "height_cm": height,
                "bmi": float(records.calculate_bmi(height, weight)) if height else None,
                "measured_on": raw, "date_basis": "补正记录"}
    elif payload.kind == "medication_regimen":
        if set(data) != {"medications", "complete"} or not isinstance(data["complete"], bool):
            records.fail("用药补正必须包含完整方案与核对状态")
        meds = [MedicationRecord.model_validate(m) for m in data["medications"]]
        for med in meds:
            for d in (med.started_on, med.stopped_on):
                if d:
                    records.require_nonfuture(d, today, "实际用药日期")
            if med.start_value and med.start_value > today.isoformat()[:len(med.start_value)]:
                records.fail("药物开始时间不能晚于本次记录日")
        data = {"medications": [m.model_dump(mode="json") for m in meds], "complete": data["complete"]}
        # 补正药物撤销观察核对资格，不能借更正记录直接制造实际停药。
        patient.has_glucose_lowering_drug = records.drug_state(meds, data["complete"])
        patient.actual_stop_confirmed = None
        if patient.current_state in {"ST40", "ST50"}:
            patient.observation_status = "needs_review"
    else:
        from app.models.clinical_v03 import AssessmentRequest
        value = AssessmentRequest(input_schema_version="v0.4", request_id=payload.request_id, expected_revision=payload.expected_revision,
                                  duration_years=data.get("years"), duration_months=data.get("months"))
        data = {"years": value.duration_years, "months": value.duration_months}
    new = records.add(db, patient, user, payload.kind, data, today, supersedes_id=previous.id)
    if payload.kind == "measurement" and previous.id == latest.id:
        patient.weight_kg = data["weight_kg"]
        patient.bmi = records.calculate_bmi(patient.height_cm, data["weight_kg"])
    correction_record = records.add(db, patient, user, "correction", {
        "record_id": previous.id, "replacement_id": new.id, "reason": payload.reason,
        "before": previous.data, "after": data, "source_event_id": previous.source_event_id,
        "request_id": payload.request_id,
    }, today)
    patient.objective_assessment_event_id = None
    patient.objective_assessment_revision = None
    patient.objective_assessment_digest = None
    # 即使本来就是空核对资格，也必须提升版本防止覆盖并发草稿。
    patient.clinical_revision += 1
    audit.write_audit(db, action="clinical_correction", operator_id=user.id, target_type="patient",
                      target_id=patient.id, detail={"record_id": previous.id, "replacement_id": new.id})
    db.commit()
    return {"record": records.out(new, db), "correction": records.out(correction_record, db), "patient_revision": patient.clinical_revision}
