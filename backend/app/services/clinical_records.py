"""资料继承、引用与补正的统一规则；不在读取时制造新事实。"""
from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.clinical_record import ClinicalRecord
from app.models.clinical_v03 import AssessmentRequest, ClinicalExamination, FullAssessmentV03, MedicationRecord
from app.models.event import Event
from app.models.patient import Patient
from app.models.user import User
from app.utils.clinical_v03_dates import require_nonfuture
from app.utils.measurements import calculate_bmi


def fail(text):
    raise BusinessRuleError(text, code="CLINICAL_DATA_INVALID")


def records(db: Session, patient_id: int, kind: str | None = None):
    stmt = select(ClinicalRecord).where(ClinicalRecord.patient_id == patient_id)
    if kind:
        stmt = stmt.where(ClinicalRecord.kind == kind)
    return list(db.scalars(stmt.order_by(ClinicalRecord.id.desc())).all())


def active(db: Session, patient_id: int, kind: str):
    all_records = records(db, patient_id)
    replaced = {r.supersedes_id for r in all_records if r.supersedes_id}
    by_id = {r.id: r for r in all_records}
    def origin_id(r):
        while r.supersedes_id and r.supersedes_id in by_id:
            r = by_id[r.supersedes_id]
        return r.id
    return sorted([r for r in all_records if r.kind == kind and r.id not in replaced], key=origin_id, reverse=True)


def latest(db: Session, patient_id: int, kind: str):
    rows = active(db, patient_id, kind)
    return rows[0] if rows else None


def out(record: ClinicalRecord, db: Session | None = None):
    operator = db.get(User, record.operator_id) if db else None
    return {"id": record.id, "kind": record.kind, "data": record.data,
            "clinical_date": record.clinical_date, "source_event_id": record.source_event_id,
            "supersedes_id": record.supersedes_id, "created_at": record.created_at,
            "operator_id": record.operator_id, "operator_display_name": operator.display_name if operator else None}


def reference(db: Session, patient_id: int, record_id: int, kind: str):
    record = db.get(ClinicalRecord, record_id)
    if record is None or record.patient_id != patient_id or record.kind != kind:
        raise NotFoundError("未找到该病例的资料记录。")
    if any(r.supersedes_id == record.id for r in records(db, patient_id)):
        fail("该资料已有补正，请刷新后使用最新记录")
    return record


def add(db, patient, user, kind, data, today, *, supersedes_id=None):
    record = ClinicalRecord(patient_id=patient.id, operator_id=user.id, kind=kind,
                            data=data, clinical_date=today, supersedes_id=supersedes_id)
    db.add(record)
    db.flush()
    return record


def drug_state(medications, complete):
    """没有资料与完整无药分开。待核对使用状态即使药效为否也不当作完整核对。"""
    if any(m.status == "使用中" and m.has_glucose_lowering_effect is True for m in medications):
        return True
    if not complete or any(m.status == "待核对" or (m.status == "使用中" and m.has_glucose_lowering_effect is None) for m in medications):
        return None
    return False


def normalize_medications(data):
    return [MedicationRecord.model_validate(m).model_dump(mode="json") for m in data]


def prepare(db: Session, patient: Patient, user: User, payload, today: date):
    """提交前做全部校验，新增记录尚未提交；事件失败时请求关闭会话一并回滚。"""
    refs = {}
    snapshot = None
    updates = {}
    if isinstance(payload, AssessmentRequest):
        plans = getattr(payload, "f029_interventions", getattr(payload, "interventions", []))
        if isinstance(payload, FullAssessmentV03) and payload.f026_start != "启动":
            plans = []  # 非启动不以隐藏的旧计划阻断当前决定。
        if "其他" in plans and not payload.intervention_other:
            fail("选择其他干预时请填写说明")
        if payload.measurement_id:
            m = reference(db, patient.id, payload.measurement_id, "measurement")
            if m.clinical_date and m.clinical_date > today:
                fail("不能沿用本次评估日期之后保存的测量")
            snapshot = {**m.data, "measurement_id": m.id}
        elif payload.f018_weight is not None:
            height = patient.height_cm or payload.f019_height
            if patient.height_cm and payload.f019_height and abs(patient.height_cm - payload.f019_height) > 1e-6:
                fail("身高已锁定，请由管理员更正")
            measured_on = payload.measured_on or today
            require_nonfuture(measured_on, today, "测量日期")
            snapshot = {"weight_kg": payload.f018_weight, "height_cm": height,
                        "bmi": float(calculate_bmi(height, payload.f018_weight)) if height else None,
                        "measured_on": measured_on.isoformat(), "date_basis": "本次录入测量日"}
            m = add(db, patient, user, "measurement", snapshot, today)
            snapshot = {**snapshot, "measurement_id": m.id}
        elif payload.f019_height is not None:
            if patient.height_cm and abs(patient.height_cm - payload.f019_height) > 1e-6:
                fail("身高已锁定，请由管理员更正")
            updates["height_cm"] = payload.f019_height
        if (isinstance(payload, FullAssessmentV03) and payload.f026_start == "启动"
                and (not snapshot or not snapshot.get("weight_kg") or not (patient.height_cm or payload.f019_height or snapshot.get("height_cm")))):
            fail("首次启动请补齐体重及确认身高，或引用已有测量")
        if snapshot:
            effective_height = patient.height_cm or payload.f019_height or snapshot.get("height_cm")
            # 引用的是原体重，不冻结本次已确认的有效身高；旧测量记录仍不改写。
            snapshot = {**snapshot, "height_cm": effective_height,
                        "bmi": calculate_bmi(effective_height, snapshot["weight_kg"])}
            updates.update({"weight_kg": snapshot["weight_kg"], "height_cm": effective_height,
                            "bmi": float(calculate_bmi(effective_height, snapshot["weight_kg"])) if effective_height else None})
            refs["measurement_id"] = snapshot["measurement_id"]
        # 字段必须显式提供才改变病程；空与0严格区分。
        if {"duration_years", "duration_months"}.intersection(payload.model_fields_set):
            data = {"years": payload.duration_years, "months": payload.duration_months}
            prev = latest(db, patient.id, "duration")
            if not prev or prev.data != data:
                prev = add(db, patient, user, "duration", data, today)
            refs["duration_id"] = prev.id
        exams = [reference(db, patient.id, eid, "examination") for eid in payload.examination_ids]
        for e in exams:
            exam = ClinicalExamination.model_validate(e.data)
            validate_exam_dates(exam, today)
        for exam in payload.examinations:
            validate_exam_dates(exam, today)
            exams.append(add(db, patient, user, "examination", exam.model_dump(mode="json"), today))
        refs["examination_ids"] = [e.id for e in exams]
    if "f016_medications" in type(payload).model_fields and (
            not hasattr(payload, "transition_id") or payload.transition_id in {"P05A", "P05B"}) and not (
            isinstance(payload, FullAssessmentV03) and payload.f026_start != "启动"):
        old = latest(db, patient.id, "medication_regimen")
        if old and payload.regimen_source_id != old.id:
            raise ConflictError("用药方案已更新，请重新打开病例核对。", code="STALE_REGIMEN")
        if not old and payload.regimen_source_id:
            fail("该病例没有可引用的用药方案")
        if old and patient.current_state in {"ST31", "ST32", "ST40", "ST50", "ST60"}:
            inherited = drug_state([MedicationRecord.model_validate(m) for m in old.data.get("medications", [])], old.data.get("complete", False))
            if inherited is not patient.has_glucose_lowering_drug and not payload.medication_reconciliation_confirmed:
                fail("历史药物明细与汇总不一致，请明确核对并确认本次当前方案；原记录保留。")
        meds = payload.f016_medications
        state = drug_state(meds, payload.medication_review_complete)
        if isinstance(payload, FullAssessmentV03) and payload.f026_start == "启动":
            choice = payload.current_medication_confirmation
            if choice is None:
                fail("请由医生本次确认当前用药核对结论")
            if choice != {True: "是", False: "否", None: "待核实"}[state]:
                fail("本次用药核对结论与药物明细/完整性不一致")
        if hasattr(payload, "f053_has_drug") and payload.f053_has_drug is not state:
            fail("是否仍有降糖作用药与当前完整用药方案不一致")
        if getattr(payload, "f050_med_status", None) == "未使用" and state is not False:
            fail("当前用药尚未核实完整，不能记为未使用降糖作用药")
        if getattr(payload, "f057_actual_stop", None) == "已实际停用":
            stopped = [m for m in meds if m.has_glucose_lowering_effect is True]
            if any(m.status != "已停用" or not m.stopped_on for m in stopped):
                fail("请逐药核对所有降糖作用药物的实际停用状态和日期")
            if stopped and max(m.stopped_on for m in stopped) != payload.f036_stop_date:
                fail("最后停药日须与逐药核对的最后实际停用日一致")
        old_meds = normalize_medications(old.data.get("medications", [])) if old else []
        for i, m in enumerate(old_meds):
            if not m.get("medication_id"):
                m["medication_id"] = f"legacy-{old.id}-{i}"
        old_ids = {m.get("medication_id") for m in old_meds if m.get("medication_id")}
        incoming_ids = {m.medication_id for m in meds if m.medication_id}
        removed_ids = old_ids - incoming_ids
        if set(payload.removed_medication_ids) != removed_ids:
            fail("本次移除药物与来源方案不一致，请重新核对移除项目")
        if incoming_ids - old_ids:
            fail("药物卡标识不属于当前来源方案，请重新添加独立药物卡")
        if removed_ids and not payload.medication_review_complete:
            fail("移除药物后请重新完整核对当前方案")
        if removed_ids and not meds and not payload.no_current_medications_confirmed:
            fail("全部移除后，请明确确认本次当前无药；移除不代表已经实际停药")
        if payload.no_current_medications_confirmed and meds:
            fail("当前仍有药物卡，不能确认本次当前无药")
        if getattr(payload, "f057_actual_stop", None) == "已实际停用" and any(
            m.get("medication_id") in removed_ids and m.get("has_glucose_lowering_effect") is True
            for m in old_meds
        ):
            fail("本次确认实际全部停药时，请保留降糖药卡并逐药核对停用状态和日期；之后可从当前方案移除")
        if len(incoming_ids) != sum(bool(m.medication_id) for m in meds):
            fail("药物卡标识重复，请重新添加独立药物卡")
        for m in meds:
            if not m.purposes and not m.purpose:
                fail("请填写每种药物的实际用药目的")
            if not m.medication_id:
                m.medication_id = uuid4().hex
            for value in (m.started_on, m.stopped_on):
                if value:
                    require_nonfuture(value, today, "实际用药日期")
            if m.start_value:
                part = today.isoformat()[:len(m.start_value)]
                if m.start_value > part:
                    fail("药物开始时间不能晚于本次记录日")
        data = {"medications": [m.model_dump(mode="json") for m in meds], "complete": payload.medication_review_complete}
        if old and data == {"medications": old_meds, "complete": old.data.get("complete", False)}:
            regimen = old
        else:
            regimen = add(db, patient, user, "medication_regimen", data, today)
        refs["regimen_id"] = regimen.id
        updates["has_glucose_lowering_drug"] = state
    return snapshot, refs, updates


def validate_exam_dates(exam, today):
    for value in (exam.test_date, exam.report_start_date, exam.report_end_date):
        if value:
            require_nonfuture(value, today, "检查日期")


def has_v04_write(db, patient_id):
    """已采用新输入结构的病例不能被旧标签页绕过方案版本与核对门禁。"""
    for value in db.scalars(select(Event.payload).where(Event.patient_id == patient_id)):
        try:
            if json.loads(value or "{}").get("input_schema_version") == "v0.4":
                return True
        except (ValueError, AttributeError):
            continue
    return False


def project_legacy_submission(db, patient, user, payload, today, snapshot):
    """兼容期旧输入也追加资料投影，避免先升级数据库、后刷新旧页面产生陈旧资料。

    仅写本次明确给出的字段；不回写事件，也不补造旧输入没有提供的测量日。
    """
    refs = {}
    if snapshot:
        r = add(db, patient, user, "measurement", {**snapshot, "measured_on": None,
                "date_basis": "旧请求未单独记录测量日"}, today)
        refs["measurement_id"] = r.id
    if "f016_medications" in payload.model_fields_set:
        meds = [m.model_dump(mode="json") for m in payload.f016_medications]
        r = add(db, patient, user, "medication_regimen", {"medications": meds,
                "complete": bool(meds or getattr(payload, "f016_no_medication_confirmed", False)), "legacy": True}, today)
        refs["regimen_id"] = r.id
    for field in ("recent_examination", "f058_examination"):
        exam = getattr(payload, field, None)
        if exam:
            r = add(db, patient, user, "examination", exam.model_dump(mode="json"), today)
            refs.setdefault("examination_ids", []).append(r.id)
    return refs


def context(db: Session, patient: Patient, today: date | None = None):
    all_events = list(db.scalars(select(Event).where(Event.patient_id == patient.id).order_by(Event.id)).all())
    carried = {}
    pending = set()
    for event in all_events:
        try:
            p = json.loads(event.payload or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(p, dict):
            continue
        if event.target_state in {"ST31", "ST32"}:
            carried["previous_stage"] = "血糖稳定" if event.target_state == "ST31" else "缓解诱导"
        if p.get("f061_conclusion") == "暂缓进入":
            pending = set(p.get("f011_hold_reasons", []))
        elif p.get("f061_conclusion"):
            pending = set()
        if (p.get("result") or "").startswith("分型"):
            pending.discard("分型存疑")
        if (p.get("result") or "").startswith("急性已处理"):
            pending.discard("急性安全")
        for key in ("f013_diagnosis_basis", "f023_constraints", "f028_stage_goal", "stage_goal", "f029_interventions", "intervention_other"):
            if p.get("f026_start") in {"暂缓补充关键资料", "当前不启动"}:
                continue  # 暂缓仅是本次决定，不用隐藏计划的空默认值覆盖最近有效计划。
            if key in p and p[key] is not None:
                carried[key] = p[key]
        plans = p.get("f029_interventions") if p.get("f026_start") == "启动" else p.get("interventions") if p.get("result") == "急性已处理进入血糖稳定" else None
        if plans is not None:
            carried["f029_interventions"] = plans
            carried["intervention_other"] = p.get("intervention_other") if "其他" in plans else None
    carried["pending_pre_tasks"] = sorted(pending)
    ms = active(db, patient.id, "measurement")
    regimen = latest(db, patient.id, "medication_regimen")
    duration = latest(db, patient.id, "duration")
    change = None
    if len(ms) >= 2:
        baseline = ms[-1].data.get("weight_kg")
        if baseline:
            change = round((baseline - ms[0].data["weight_kg"]) / baseline * 100, 1)
    regimen_out = out(regimen) if regimen else None
    if regimen_out:
        normalized = normalize_medications(regimen.data.get("medications", []))
        for i, med in enumerate(normalized):
            if not med.get("medication_id"):
                med["medication_id"] = f"legacy-{regimen.id}-{i}"
        regimen_out = {**regimen_out, "data": {**regimen.data, "medications": normalized}}
    suggestions = {}
    if today:
        from app.services.defaults import default_next_review_date, next_followup_date
        from app.utils.date_utils import add_months_clamped
        suggestions["suggested_review_date"] = (patient.next_review_date if patient.next_review_date and patient.next_review_date > today
            else next_followup_date(patient.remission_confirmed_date or today, today) if patient.current_state == "ST60"
            else default_next_review_date(today)).isoformat()
        suggestions["drug_free_3m"] = ("是" if today >= add_months_clamped(patient.last_med_stop_date, 3) else "否") if patient.actual_stop_confirmed and patient.last_med_stop_date else "待核对"
    return {**suggestions, "patient_revision": patient.clinical_revision, "measurement": out(ms[0]) if ms else None,
            "measurements": [out(m) for m in ms], "weight_reduction_percent": change,
            "regimen": regimen_out, "duration": out(duration) if duration else None,
            "examinations": [out(e) for e in active(db, patient.id, "examination")], "carried": carried}
