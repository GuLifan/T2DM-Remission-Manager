"""正式v0.3接口；GET只读、刷新推进显式POST、事件/状态/审计同事务。

新入口与旧版并存便于逐步接入；患者一旦采用v0.3，旧临床写接口拒绝降级。
未完成前端接入和全量验收前不重启开发服务，不迁移当前开发数据库。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import (
    get_patient_or_404,
    prepare_measurement_snapshot,
    record_outcome,
    require_patient_write_access,
    require_profile_complete,
    require_revision,
    require_state,
)
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.test_mode import effective_today_for_patient
from app.domain.templates import render
from app.models.clinical_v03 import (
    AssessmentRequest,
    ClinicalExamination,
    ExaminationRecord,
    FullAssessmentV03,
    MedicationRestartV03,
    ObservationAnchors,
    ObservationUpdateV03,
    PhaseReviewV03,
    PostRemissionV03,
    PreAssessmentV03,
    PreRecoveryV03,
    RemissionConfirmV03,
    RemissionJudgeV03,
    SupplementalDecisionV03,
    V03Request,
)
from app.models.event import Event
from app.models.patient import Patient
from app.models.user import User
from app.repository import events as events_repo
from app.repository.database import get_db
from app.services import clinical_records
from app.services import clinical_v03 as service
from app.services.defaults import next_followup_date
from app.utils.clinical_v03_dates import compute_earliest, require_nonfuture

router = APIRouter(prefix="/patients/{patient_id}/clinical-v03", tags=["临床v0.3"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]


def context(patient: Patient) -> service.Context:
    anchors = None
    if patient.applicable_interventions:
        anchors = ObservationAnchors(f063_applicable_interventions=patient.applicable_interventions,
                                     f038_lifestyle_start_date=patient.lifestyle_start_date,
                                     f039_surgery_date=patient.surgery_date)
    return service.Context(patient.current_state, patient.stage, patient.stage_goal, patient.last_med_stop_date,
                           anchors, patient.observation_status, patient.observation_cycle,
                           patient.actual_stop_confirmed, patient.has_glucose_lowering_drug,
                           patient.remission_confirmed_date)


def load(db: Session, pid: int, user: User, payload: V03Request, states: tuple[str, ...]) -> tuple[Patient, date]:
    patient = get_patient_or_404(db, pid)
    require_patient_write_access(user, patient)
    if events_repo.find_by_request_id(db, pid, payload.request_id):
        raise ConflictError("该操作已提交，本次未重复记录。", code="DUPLICATE_REQUEST")
    require_state(patient, states, "本次操作")
    require_revision(patient, payload.expected_revision)
    if payload.input_schema_version == "v0.3" and clinical_records.has_v04_write(db, patient.id):
        raise ConflictError("该病例已采用新版输入，请刷新页面重新核对。", code="V04_INPUT_REQUIRED")
    return patient, effective_today_for_patient(user, patient)


def validate_medication_dates(payload: V03Request, today: date) -> None:
    for med in getattr(payload, "f016_medications", []):
        for value in (med.started_on, med.stopped_on):
            if value:
                require_nonfuture(value, today, "药物实际起止日期")


def submit(db: Session, patient: Patient, actor: User, payload: V03Request,
           result: service.Decision, today: date, *, source: str = "doctor") -> dict:
    updates = dict(result.updates)
    snapshot = None
    refs = {}
    if payload.input_schema_version == "v0.4":
        snapshot, refs, measured = clinical_records.prepare(db, patient, actor, payload, today)
        updates.update(measured)
    elif isinstance(payload, AssessmentRequest):
        snapshot, measured = prepare_measurement_snapshot(patient, weight_kg=payload.f018_weight,
                                                         height_cm=payload.f019_height)
        updates.update(measured)
    if payload.input_schema_version == "v0.3":
        refs = clinical_records.project_legacy_submission(db, patient, actor, payload, today, snapshot)
    validate_medication_dates(payload, today)
    event = record_outcome(db, patient=patient, operator=actor, source_state=patient.current_state,
                          target_state=result.target_state, rule_id=result.rule_id,
                          template_id=result.template_id, output_text=result.output_text,
                          payload={**payload.model_dump(mode="json"), "measurement_snapshot": snapshot,
                                   "clinical_date": today.isoformat(), "tasks": result.tasks, "record_refs": refs},
                          request_id=payload.request_id, source=source, updates=updates,
                          clinical_contract_version="v0.3", transition_ids=result.transition_ids,
                          expected_revision=payload.expected_revision, objective_met=result.objective_met,
                          associated_record_ids=[rid for value in refs.values() for rid in (value if isinstance(value, list) else [value])])
    return response(patient, result, event.id)


def response(patient: Patient, result: service.Decision, event_id: int | None = None) -> dict:
    return {"clinical_contract_version": "v0.3", "transition_ids": result.transition_ids,
            "target_state": result.target_state, "rule_id": result.rule_id,
            "template_id": result.template_id, "output_text": result.output_text,
            "tasks": result.tasks, "objective_met": result.objective_met,
            "patient_revision": patient.clinical_revision, "assessment_event_id": event_id}


@router.post("/pre-assessment")
def pre(patient_id: int, payload: PreAssessmentV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST10",))
    require_profile_complete(patient)
    return submit(db, patient, user, payload, service.evaluate_pre(context(patient), payload), today)


@router.post("/full-assessment")
def full(patient_id: int, payload: FullAssessmentV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST20",))
    evaluated = payload
    if payload.input_schema_version == "v0.4" and payload.examination_ids:
        selected = [ClinicalExamination.model_validate(clinical_records.reference(db, patient.id, eid, "examination").data) for eid in payload.examination_ids]
        evaluated = payload.model_copy(update={"examinations": [*payload.examinations, *selected]})
    return submit(db, patient, user, payload, service.evaluate_full(context(patient), evaluated, today), today)


@router.post("/pre-recovery")
def recovery(patient_id: int, payload: PreRecoveryV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST10",))
    previous = db.scalar(select(Event).where(Event.patient_id == patient.id, Event.source_state == "ST10")
                         .order_by(Event.id.desc()).limit(1))
    values = json.loads(previous.payload or "{}") if previous else {}
    pending = values.get("f011_hold_reasons", [])
    if previous and previous.transition_ids == ["T07"]:
        pending = values.get("tasks", [])
    if not previous or previous.clinical_contract_version != "v0.3":
        raise BusinessRuleError("请先在新版预评估核对暂缓原因。", code="PRE_HOLD_REQUIRED")
    return submit(db, patient, user, payload, service.evaluate_recovery(context(patient), payload, today, pending), today)


@router.post("/phase-review")
def phase(patient_id: int, payload: PhaseReviewV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST31", "ST32"))
    return submit(db, patient, user, payload, service.evaluate_phase(context(patient), payload, today), today)


@router.get("/observation")
def observation(patient_id: int, user: Actor, db: DB) -> dict:
    """查询永不推进，读权限保持原项目规则；返回自然语言状态提示。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, ("ST40",), "缓解观察")
    return response(patient, service.evaluate_observation(context(patient), effective_today_for_patient(user, patient)))


@router.post("/refresh")
def refresh(patient_id: int, payload: V03Request, user: Actor, db: DB) -> dict:
    """工作台加载时自动调用；只有到期T24才写事件，普通刷新不造临床事件。"""
    patient = get_patient_or_404(db, patient_id)
    require_patient_write_access(user, patient)
    today = effective_today_for_patient(user, patient)
    if patient.current_state != "ST40":
        return {"advanced": False, "patient_revision": patient.clinical_revision}
    require_revision(patient, payload.expected_revision)
    result = service.evaluate_observation(context(patient), today)
    if result.transition_ids != ["T24"]:
        return {**response(patient, result), "advanced": False}
    # 患者版本锁确保同一观察周期只能有一次成功T24；重复刷新已离开ST40无写入。
    return {**submit(db, patient, user, payload, result, today, source="system"), "advanced": True}


@router.post("/medication-restart")
def restart(patient_id: int, payload: MedicationRestartV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST40",))
    return submit(db, patient, user, payload, service.evaluate_restart(context(patient), payload), today)


@router.post("/observation-anchors")
def anchors(patient_id: int, payload: ObservationUpdateV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST40",))
    ctx = context(patient)
    if ctx.observation_status != "active" or ctx.actual_stop_confirmed is not True or ctx.has_drug is not False:
        raise BusinessRuleError("当前不是有效无药观察，不能通过补日期重新开始计时；请医生选择后续管理。", code="OBSERVATION_SUSPENDED")
    earliest, tasks = compute_earliest(ctx.stop_date, payload.anchors, today=today)
    # 补核只保存T22/T23；工作台下一次显式刷新负责幂等T24到期推进。
    result = service.decision(replace(ctx, anchors=payload.anchors), ["T23" if tasks else "T22"],
                              "已保存适用干预及日期，请核对观察安排。", tasks=tasks,
                              updates={"applicable_interventions": payload.anchors.f063_applicable_interventions,
                                       "lifestyle_start_date": payload.anchors.f038_lifestyle_start_date,
                                       "surgery_date": payload.anchors.f039_surgery_date,
                                       "earliest_judge_date": earliest})
    return submit(db, patient, user, payload, result, today)


@router.post("/remission-judge")
def judge(patient_id: int, payload: RemissionJudgeV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST50",))
    if payload.input_schema_version == "v0.4" and payload.f058_examination_id:
        rec = clinical_records.reference(db, patient.id, payload.f058_examination_id, "examination")
        exam = ClinicalExamination.model_validate(rec.data)
        selected = ExaminationRecord.model_validate(exam.model_dump(exclude={"text", "note"}))
        # 独立复核由医生本次选择；不能伪造被引用检查的数值、日期和来源。
        if payload.f058_examination:
            selected.independently_reviewed = payload.f058_examination.independently_reviewed
            received = payload.f058_examination.model_dump(exclude={"independently_reviewed"})
            if received != selected.model_dump(exclude={"independently_reviewed"}):
                clinical_records.fail("判定检查与被引用记录不一致")
        payload.f058_examination = selected
    return submit(db, patient, user, payload, service.evaluate_judge(context(patient), payload, today), today)


@router.post("/remission-confirm")
def confirm(patient_id: int, payload: RemissionConfirmV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST50",))
    assessment = db.get(Event, payload.assessment_event_id)
    latest = db.scalar(select(Event.id).where(Event.patient_id == patient.id).order_by(Event.id.desc()).limit(1))
    if (assessment is None or assessment.patient_id != patient.id or assessment.clinical_contract_version != "v0.3"
            or assessment.transition_ids != ["T34"] or latest != assessment.id
            or patient.objective_assessment_event_id != assessment.id
            or patient.objective_assessment_revision != patient.clinical_revision):
        raise BusinessRuleError("请先完成当前资料的客观核对，旧达标记录不能用于本次确认。", code="OBJECTIVE_CHECK_REQUIRED")
    values = json.loads(assessment.payload)
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != patient.objective_assessment_digest:
        raise BusinessRuleError("判定资料已变化，请重新核对。", code="OBJECTIVE_CHECK_REQUIRED")
    if values["clinical_date"] != today.isoformat():
        raise BusinessRuleError("本次判定日期已变化，请重新核对资料和检查日期。", code="OBJECTIVE_CHECK_REQUIRED")
    # 除缓存外重新执行当时输入+当前观察/药物事实，防止绕过快照资格直接确认。
    request = RemissionJudgeV03.model_validate({k: v for k, v in values.items() if k in RemissionJudgeV03.model_fields})
    checked = service.evaluate_judge(context(patient), request, today)
    if not checked.objective_met or patient.has_glucose_lowering_drug is not False:
        raise BusinessRuleError("当前事实不足以确认缓解，请重新核对。", code="OBJECTIVE_CHECK_REQUIRED")
    if payload.f048_confirm == "暂不确认":
        task = service.require_text(payload.f012_pre_tasks, "暂不确认原因与定向复核任务")
        result = service.decision(context(patient), ["T36"], render("OUT-E4-UNCERTAIN", pre_tasks=task), template="OUT-E4-UNCERTAIN", tasks=[task])
    else:
        result = service.decision(context(patient), ["T35", "T44"], render("OUT-E4-CONFIRMED") + "\n" + render("OUT-E5-FOLLOWUP"), template="OUT-E4-CONFIRMED", updates={"remission_confirmed_date": today, "current_remission_evaluation": "已确认", "next_review_date": next_followup_date(today, today), "observation_status": "completed"})
    return submit(db, patient, user, payload, result, today)


@router.post("/post-remission")
def post(patient_id: int, payload: PostRemissionV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST60",))
    return submit(db, patient, user, payload, service.evaluate_post(context(patient), payload, today), today)


@router.post("/supplemental-decision")
def supplement(patient_id: int, payload: SupplementalDecisionV03, user: Actor, db: DB) -> dict:
    patient, today = load(db, patient_id, user, payload, ("ST00", "ST31", "ST32", "ST50", "ST60"))
    if payload.transition_id == "P01":
        require_profile_complete(patient)
    return submit(db, patient, user, payload, service.evaluate_supplement(context(patient), payload), today)
