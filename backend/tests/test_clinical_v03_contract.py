"""V03-A独立契约、日期与历史迁移测试；所有库均为临时测试目录。"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.flow_common import record_outcome, require_revision
from app.config import BACKEND_DIR, Settings
from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.clinical_v03 import ATOMIC_TRANSITIONS, SOURCE_SHA256, SUPPLEMENTAL_TRANSITIONS, require_transition
from app.models.audit import AuditLog
from app.models.clinical_v03 import (
    ExaminationRecord,
    MedicationRestartV03,
    ObservationAnchors,
    PhaseReviewV03,
    PostRemissionV03,
    PreAssessmentV03,
    PreRecoveryV03,
    RemissionConfirmV03,
    RemissionJudgeV03,
    SupplementalDecisionV03,
)
from app.models.event import Event
from app.models.patient import Patient
from app.models.user import User
from app.repository import patients as patients_repo
from app.repository.migration_backup import backup_before_v03
from app.services.clinical_v03 import (
    Context,
    evaluate_judge,
    evaluate_observation,
    evaluate_phase,
    evaluate_post,
    evaluate_recovery,
    evaluate_restart,
    evaluate_supplement,
)
from app.utils.clinical_v03_dates import compute_earliest, examination_date_qualified

ROOT = BACKEND_DIR.parent
BASE = {"request_id": "test-v03", "expected_revision": 1, "f018_weight": 70}
PHASE = {**BASE, "f030_safety_issues": ["无"], "f031_stage_indicator": "本次医生核对", "f032_treatment_changes": ["无"], "f033_executable": "可继续", "f034_action": "继续当前阶段", "f035_stop_last_med": False, "f053_has_drug": None}


def test_atomic_contract_matches_all_51_original_rows():
    # 公开基线保留已核对原工作簿的51条转移与来源哈希，不发布内部工作簿。
    baseline = json.loads((Path(__file__).parent / "fixtures/clinical_source_contract.json").read_text(encoding="utf-8"))
    assert baseline["source_workbook_sha256"] == SOURCE_SHA256
    assert len(ATOMIC_TRANSITIONS) == 51 and len(SUPPLEMENTAL_TRANSITIONS) == 7
    for actual, row in zip(ATOMIC_TRANSITIONS, baseline["transitions"], strict=True):
        assert (actual.id, actual.rule_id, actual.source, actual.target, actual.condition) == tuple(row)
    for actual, excel_row in zip(ATOMIC_TRANSITIONS, baseline["excel_rows"], strict=True):
        assert actual.excel_row == excel_row
        assert not actual.supplemental


@pytest.mark.parametrize("transition", [*ATOMIC_TRANSITIONS, *SUPPLEMENTAL_TRANSITIONS], ids=lambda t: t.id)
def test_each_transition_has_exactly_one_source_and_target(transition):
    assert require_transition(transition.id, transition.source, transition.target) == transition
    with pytest.raises(BusinessRuleError):
        require_transition(transition.id, "ST99", transition.target)


def test_new_weight_and_explicit_conclusion_are_required():
    values = {**BASE, "f001_t2dm_established": "是", "f002_acute_unsafe": "否", "f003_type_doubt": "否", "f004_treatment_context_sufficient": "是", "f005_refused": "否", "f061_conclusion": "进入完整评估"}
    assert PreAssessmentV03(**values).clinical_contract_version == "v0.3"
    for key in ["f018_weight", "f061_conclusion", "expected_revision", "request_id"]:
        with pytest.raises(ValidationError):
            PreAssessmentV03(**{k: v for k, v in values.items() if k != key})
    with pytest.raises(ValidationError):
        PreAssessmentV03(**values, unknown_clinical_flag=True)


def test_unknown_drug_is_not_false_or_defaulted():
    assert PhaseReviewV03(**PHASE).f053_has_drug is None
    with pytest.raises(ValidationError):
        PhaseReviewV03(**{k: v for k, v in PHASE.items() if k != "f053_has_drug"})
    with pytest.raises(ValidationError):
        PhaseReviewV03(**{**PHASE, "f053_has_drug": "否"})


@pytest.mark.parametrize("execution", ["仅计划停用", "待核对"])
def test_planned_stop_cannot_be_used_as_actual_date(execution):
    values = {**PHASE, "f035_stop_last_med": True, "f057_actual_stop": execution, "planned_stop_date": "2026-05-01"}
    assert PhaseReviewV03(**values).f036_stop_date is None
    with pytest.raises(ValidationError):
        PhaseReviewV03(**values, f036_stop_date="2026-05-01")


@pytest.mark.parametrize("has_drug", [True, None])
def test_actual_all_stop_requires_explicit_no_drug(has_drug):
    with pytest.raises(ValidationError):
        PhaseReviewV03(**{**PHASE, "f035_stop_last_med": True, "f057_actual_stop": "已实际停用", "f036_stop_date": "2026-05-01", "f053_has_drug": has_drug})


def test_actual_stop_rejects_inconsistent_medication_record():
    values = {**PHASE, "f035_stop_last_med": True, "f057_actual_stop": "已实际停用", "f036_stop_date": "2026-05-01", "f053_has_drug": False}
    assert PhaseReviewV03(**values).f036_stop_date == date(2026, 5, 1)
    with pytest.raises(ValidationError):
        PhaseReviewV03(**values, f016_medications=[{"name": "演示药", "dose": "演示剂量", "status": "使用中", "purpose": "器官获益", "has_glucose_lowering_effect": None}])


@pytest.mark.parametrize("field", ["f030_safety_issues", "f032_treatment_changes"])
def test_multiselect_exclusion_is_server_enforced(field):
    with pytest.raises(ValidationError):
        PhaseReviewV03(**{**PHASE, field: ["无", "新增"]})


def test_missing_applicable_date_does_not_get_skipped():
    anchors = ObservationAnchors(f063_applicable_interventions=["结构化生活方式"])
    earliest, tasks = compute_earliest(date(2026, 5, 1), anchors, today=date(2026, 8, 1))
    assert earliest is None and tasks
    assert compute_earliest(date(2026, 5, 1), None, today=date(2026, 8, 1))[0] is None


def test_earliest_uses_only_explicitly_applicable_dates():
    anchors = ObservationAnchors(f063_applicable_interventions=["结构化生活方式"], f038_lifestyle_start_date=date(2026, 1, 15), f039_surgery_date=date(2026, 6, 1))
    assert compute_earliest(date(2026, 5, 1), anchors, today=date(2026, 8, 1)) == (date(2026, 8, 1), [])
    anchors.f063_applicable_interventions.append("代谢手术")
    assert compute_earliest(date(2026, 5, 1), anchors, today=date(2026, 8, 1))[0] == date(2026, 9, 1)
    with pytest.raises(BusinessRuleError):
        compute_earliest(date(2026, 8, 2), anchors, today=date(2026, 8, 1))


@pytest.mark.parametrize("kind", ["HbA1c", "FPG", "CGM估算HbA1c"])
@pytest.mark.parametrize("check_date,expected", [("2026-07-31", False), ("2026-08-01", True), ("2026-08-15", True), ("2026-08-16", False)])
def test_examination_date_closed_interval(kind, check_date, expected):
    exam = ExaminationRecord(kind=kind, value=5.9, unit="mmol/L" if kind == "FPG" else "%", source="虚构化验", reliability="可靠", test_date=date(2026, 1, 1) if kind == "CGM估算HbA1c" else check_date, report_end_date=check_date if kind == "CGM估算HbA1c" else None)
    assert examination_date_qualified(exam, date(2026, 8, 1), date(2026, 8, 15)) is expected


def test_confirm_requires_specific_assessment_event():
    assert RemissionConfirmV03(request_id="x", expected_revision=2, f048_confirm="确认", assessment_event_id=1).clinical_contract_version == "v0.3"
    with pytest.raises(ValidationError):
        RemissionConfirmV03(request_id="x", expected_revision=2, f048_confirm="确认")
    with pytest.raises(ValidationError):
        SupplementalDecisionV03(request_id="supplement", expected_revision=1, transition_id="P02",
                                doctor_confirmed=False, reason="演示", evidence_summary="演示新证据")


@pytest.mark.parametrize(
    ("result", "pending", "transition", "target"),
    [
        ("分型仍为T2DM", ["分型存疑"], "T05", "ST20"),
        ("分型明确其他类型", ["分型存疑"], "T06", "ST99"),
        ("急性已处理返回结论", ["急性安全"], "T07", "ST10"),
        ("急性已处理进入血糖稳定", ["急性安全"], "T08", "ST31"),
    ],
)
def test_pre_recovery_uses_exact_exit(result, pending, transition, target):
    payload = PreRecoveryV03(**BASE, result=result, doctor_confirmed=True, evidence_summary="虚构复核结果",
                             stage_goal="先安全稳定血糖", interventions=["结构化生活方式"])
    actual = evaluate_recovery(Context("ST10"), payload, date(2026, 10, 12), pending)
    assert actual.transition_ids == [transition] and actual.target_state == target


def test_plan_stop_never_starts_observation_but_actual_stop_does():
    planned = PhaseReviewV03(**{**PHASE, "f035_stop_last_med": True, "f057_actual_stop": "仅计划停用",
                               "planned_stop_date": "2026-10-20"})
    result = evaluate_phase(Context("ST31", stage="血糖稳定"), planned, date(2026, 10, 12))
    assert result.transition_ids == ["T14A"] and result.target_state == "ST31"
    actual = PhaseReviewV03(**{**PHASE, "f035_stop_last_med": True, "f057_actual_stop": "已实际停用",
                              "f036_stop_date": "2026-07-01", "f053_has_drug": False,
                              "anchors": {"f063_applicable_interventions": ["其他"]}})
    result = evaluate_phase(Context("ST32", stage="缓解诱导", observation_cycle=2), actual, date(2026, 10, 12))
    assert result.transition_ids == ["T18B", "T22"] and result.target_state == "ST40"
    assert result.updates["observation_cycle"] == 3 and result.updates["actual_stop_confirmed"] is True


def test_benefit_restart_pauses_clock_without_false_failure():
    medication = {"name": "虚构获益药", "dose": "演示剂量", "status": "使用中",
                  "has_glucose_lowering_effect": True, "purpose": "器官获益"}
    payload = MedicationRestartV03(request_id="restart", expected_revision=1, f037_reason="因器官获益",
                                   f016_medications=[medication])
    result = evaluate_restart(Context("ST40", observation_status="active"), payload)
    assert result.transition_ids == ["T27"] and result.target_state == "ST40"
    paused = Context("ST40", stop_date=date(2026, 1, 1), anchors=ObservationAnchors(
        f063_applicable_interventions=["其他"]), observation_status="suspended_benefit",
        actual_stop_confirmed=False, has_drug=True)
    refresh = evaluate_observation(paused, date(2026, 10, 12))
    assert refresh.transition_ids == [] and "暂停" in refresh.output_text


def test_judge_uses_current_qualified_check_and_doctor_still_confirms():
    anchors = ObservationAnchors(f063_applicable_interventions=["其他"])
    ctx = Context("ST50", stop_date=date(2026, 7, 1), anchors=anchors, observation_status="active",
                  actual_stop_confirmed=True, has_drug=False)
    common = {**BASE, "f041_diagnosis_credible": "是", "f042_drug_free_3m": "是",
              "f043_hba1c_reliable": "是", "f053_has_drug": False, "f059_completeness": "完整",
              "anchors": anchors.model_dump(mode="json")}
    old = RemissionJudgeV03(**common, f058_examination={"kind": "HbA1c", "value": 6.1, "unit": "%",
                                                             "source": "虚构实验室", "test_date": "2026-09-30",
                                                             "reliability": "可靠"})
    assert evaluate_judge(ctx, old, date(2026, 10, 12)).transition_ids == ["T31"]
    current = RemissionJudgeV03(**common, f058_examination={"kind": "HbA1c", "value": 6.1, "unit": "%",
                                                                 "source": "虚构实验室", "test_date": "2026-10-01",
                                                                 "reliability": "可靠"})
    result = evaluate_judge(ctx, current, date(2026, 10, 12))
    assert result.transition_ids == ["T34"] and result.objective_met and result.target_state == "ST50"


def test_post_remission_benefit_drug_stays_unevaluable():
    payload = PostRemissionV03(**BASE, f050_med_status="因器官获益", f055_glucose_state="暂不能可靠解释",
                               risk_increase_confirmed=False,
                               f016_medications=[{"name": "虚构获益药", "dose": "演示剂量", "status": "使用中",
                                                  "has_glucose_lowering_effect": True, "purpose": "器官获益"}])
    result = evaluate_post(Context("ST60", confirmed_date=date(2026, 1, 1)), payload, date(2026, 10, 12))
    assert result.transition_ids == ["T41"] and result.target_state == "ST60"
    assert result.updates["current_remission_evaluation"] == "不可评价"


@pytest.mark.parametrize(
    ("key", "source", "target"),
    [("P01", "ST00", "ST10"), ("P02", "ST50", "ST20"), ("P03A", "ST31", "ST20"),
     ("P03B", "ST32", "ST20"), ("P04", "ST60", "ST20"),
     ("P05A", "ST60", "ST31"), ("P05B", "ST60", "ST32")],
)
def test_each_supplemental_exit_requires_explicit_doctor_decision(key, source, target):
    payload = SupplementalDecisionV03(request_id=f"supplement-{key}", expected_revision=1,
                                      transition_id=key, doctor_confirmed=True, reason="虚构医生决定",
                                      evidence_summary="虚构证据摘要", remission_termination_confirmed=key == "P04",
                                      f050_med_status="因器官获益" if key.startswith("P05") else None,
                                      medication_review_complete=key.startswith("P05"),
                                      f016_medications=[{"name":"获益药物", "dose":"待核对", "status":"使用中", "has_glucose_lowering_effect":True, "purposes":["肾脏保护"]}] if key.startswith("P05") else [])
    result = evaluate_supplement(Context(source), payload)
    assert result.transition_ids == [key] and result.target_state == target


def test_v03_objective_event_and_same_snapshot_confirmation_over_http(client, doctor, db_session):
    user = db_session.get(User, doctor["user"]["id"])
    item = _patient(db_session, user)
    item.current_state = "ST50"
    item.clinical_contract_version = "v0.3"
    item.last_med_stop_date = date.today().replace(day=1)
    # 选择足够早的停药日，避免测试依赖当月天数。
    item.last_med_stop_date = date(date.today().year - 1, date.today().month, 1)
    item.applicable_interventions = ["其他"]
    item.observation_status = "active"
    item.actual_stop_confirmed = True
    item.has_glucose_lowering_drug = False
    db_session.commit()
    db_session.refresh(item)
    payload = {
        "clinical_contract_version": "v0.3", "request_id": uuid4().hex,
        "expected_revision": item.clinical_revision, "f018_weight": 65, "f019_height": 165,
        "f041_diagnosis_credible": "是", "f042_drug_free_3m": "是", "f043_hba1c_reliable": "是",
        "f053_has_drug": False, "f059_completeness": "完整",
        "f058_examination": {"kind": "HbA1c", "value": 6.1, "unit": "%", "source": "虚构实验室",
                              "test_date": date.today().isoformat(), "reliability": "可靠"},
        "anchors": {"f063_applicable_interventions": ["其他"]},
    }
    judged = client.post(f"/api/patients/{item.id}/clinical-v03/remission-judge",
                         headers=doctor["headers"], json=payload)
    assert judged.status_code == 200, judged.text
    body = judged.json()
    assert body["transition_ids"] == ["T34"] and body["objective_met"] is True
    confirmed = client.post(f"/api/patients/{item.id}/clinical-v03/remission-confirm", headers=doctor["headers"],
                            json={"clinical_contract_version": "v0.3", "request_id": uuid4().hex,
                                  "expected_revision": body["patient_revision"], "f048_confirm": "确认",
                                  "assessment_event_id": body["assessment_event_id"]})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["transition_ids"] == ["T35", "T44"]


def migration_config(data_dir: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["settings"] = Settings(data_dir=data_dir)
    return config


def test_migration_preserves_history_and_marks_legacy_pending(tmp_path):
    """真实运行旧头→新头，保存旧载荷/日期/药物未知；不是仅create_all。"""
    config = migration_config(tmp_path)
    command.upgrade(config, "a1c9e7f2d4b8")
    db_path = tmp_path / "etmms.db"
    with sqlite3.connect(db_path) as db:
        for pid, state in [(1, "ST40"), (2, "ST60")]:
            db.execute("INSERT INTO patients (id,name,gender,birth_date,medical_record_no,department,profile_complete,is_test_patient,current_state,created_at,updated_at,remission_confirmed_date,last_med_stop_date) VALUES (?,?,?,?,?,'内分泌科',1,0,?,'2026-01-01','2026-01-01','2026-08-01','2026-05-01')", (pid, "隔离历史患者", "女", "1980-01-01", f"legacy-{pid}", state))
        db.execute("INSERT INTO events (id,patient_id,operator_id,source,rule_id,source_state,target_state,output_text,payload,created_at) VALUES (1,2,1,'doctor','E4-B04','ST50','ST60','历史确认','{\"old\":\"原样保留\"}','2026-08-01')")
        old_event = db.execute("SELECT payload,output_text,created_at FROM events").fetchone()
    command.upgrade(config, "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT payload,output_text,created_at FROM events").fetchone() == old_event
        assert db.execute("SELECT clinical_contract_version,transition_ids FROM events").fetchone() == ("v1.0", None)
        assert db.execute("SELECT current_state,observation_status,applicable_interventions,actual_stop_confirmed,has_glucose_lowering_drug FROM patients WHERE id=1").fetchone() == ("ST40", "legacy_pending", None, None, None)
        assert db.execute("SELECT current_state,remission_confirmed_date,current_remission_evaluation FROM patients WHERE id=2").fetchone() == ("ST60", "2026-08-01", "待核对")
    backups = list((tmp_path / "migration_backups").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT payload,output_text,created_at FROM events").fetchone() == old_event
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    command.upgrade(config, "head")
    assert len(list((tmp_path / "migration_backups").glob("*.db"))) == 1


def test_backup_includes_committed_wal_and_is_not_overwritten(tmp_path):
    source = tmp_path / "wal.db"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE marker (value TEXT)")
        db.execute("INSERT INTO marker VALUES ('已提交WAL')")
        db.commit()
        a = backup_before_v03(source)
        b = backup_before_v03(source)
        assert a != b and a and b
        with sqlite3.connect(a) as backup:
            assert backup.execute("SELECT value FROM marker").fetchone()[0] == "已提交WAL"


def _patient(db, user):
    item = patients_repo.create_patient(db, name="隔离并发患者", gender="女", birth_date=date(1980, 1, 1), medical_record_no=uuid4().hex, owner_id=user.id)
    db.commit()
    return item


def test_optimistic_revision_and_stale_outcome_rollback(client, doctor, db_session):
    user = db_session.get(User, doctor["user"]["id"])
    item = _patient(db_session, user)
    with Session(db_session.bind) as other:
        stale = other.get(Patient, item.id)
        revision = stale.clinical_revision
        item.stage_goal = "更新后的事实"
        db_session.commit()
        with pytest.raises(ConflictError):
            require_revision(item, revision)
        with pytest.raises(ConflictError) as exc:
            record_outcome(other, patient=stale, operator=other.get(User, user.id), source_state="ST00", target_state="ST10", rule_id="SYS-REOPEN", template_id=None, output_text="重新发起", request_id="stale-test")
        assert exc.value.code == "STALE_PATIENT"
        assert other.scalar(select(Event).where(Event.patient_id == item.id)) is None
        assert other.scalar(select(AuditLog).where(AuditLog.target_id == item.id, AuditLog.action == "event_write")) is None
    with Session(db_session.bind) as first, Session(db_session.bind) as second:
        left = first.get(Patient, item.id)
        right = second.get(Patient, item.id)
        left.stage_goal = "再次更新"
        first.commit()
        right.stage_goal = "旧版本覆盖"
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()


def test_v03_event_records_exact_transition_and_contract(client, doctor, db_session):
    user = db_session.get(User, doctor["user"]["id"])
    item = _patient(db_session, user)
    revision = item.clinical_revision
    record_outcome(db_session, patient=item, operator=user, source_state="ST00", target_state="ST10", rule_id="SYS-REOPEN", template_id=None, output_text="医生确认重新发起", request_id="new-v03", clinical_contract_version="v0.3", transition_ids=["P01"], expected_revision=revision, updates={"clinical_contract_version": "v0.3"})
    event = db_session.scalar(select(Event).where(Event.patient_id == item.id))
    assert event.clinical_contract_version == "v0.3" and event.transition_ids == ["P01"]
    assert item.clinical_revision > revision
