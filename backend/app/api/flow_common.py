"""
模块名称：flow_common.py
所属层级：接口层（api）
功能说明：临床流程接口的共享骨架——患者取用与状态守卫、结果落库、事件与审计同事务写入。

为什么集中（`_SPEC/07` 第九节约定）：
    1. **事件与审计必须同事务**：任何一次决策都要么"状态 + 事件 + 审计"全部写入，
       要么全部不写；分散在各接口里极易漏写审计。
    2. **事务边界在接口层**：服务层是纯函数不提交，仓储只 add+flush，
       提交动作只发生在这里，便于审计与排查。
    3. **幂等**：客户端重复提交（双击、网络重试）不得产生重复事件。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.test_mode import simulated_date_for_event
from app.models.event import Event
from app.models.patient import Patient
from app.models.schemas import PatientOut
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import events as events_repo
from app.repository import patients as patients_repo
from app.repository import users as users_repo
from app.utils.measurements import calculate_bmi


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    """取患者档案；不存在时抛 404（提示为自然语言）。"""
    patient = patients_repo.get_patient(db, patient_id)
    if patient is None:
        raise NotFoundError("未找到该患者档案。")
    return patient


def require_admin(user: User) -> None:
    """守卫：只有正式管理员角色可执行账号或归属管理操作。"""
    if user.role != "admin":
        raise ForbiddenError("只有管理员可以执行此操作。", code="ADMIN_REQUIRED")


def can_edit_patient(user: User, patient: Patient) -> bool:
    """判断账号是否可以改变患者档案或流程状态。"""
    return not patient.archived and (user.role == "admin" or patient.owner_id == user.id)


def require_patient_write_access(user: User, patient: Patient) -> None:
    """患者写权限的唯一守卫；测试账号不得绕过责任归属。"""
    if not can_edit_patient(user, patient):
        raise ForbiddenError(
            "您的账户暂无权限编辑此条记录", code="PATIENT_WRITE_FORBIDDEN"
        )


def patient_out(db: Session, patient: Patient, current_user: User) -> PatientOut:
    """构造含责任医生与当前账号权限的患者响应。"""
    owner = users_repo.get_by_id(db, patient.owner_id) if patient.owner_id is not None else None
    return PatientOut.model_validate(patient).model_copy(
        update={
            "owner_display_name": owner.display_name if owner is not None else None,
            "can_edit": can_edit_patient(current_user, patient),
        }
    )


def require_state(patient: Patient, allowed: tuple[str, ...], action_label: str) -> None:
    """守卫：当前状态不在允许集合内时拒绝操作。

    参数:
        patient (Patient): 目标患者。
        allowed (tuple[str, ...]): 允许执行该操作的状态集合。
        action_label (str): 操作名称（自然语言），用于拼提示语。

    异常:
        BusinessRuleError: 状态不允许时抛出，提示中只出现自然语言，不出现状态代码。
    """
    if patient.current_state not in allowed:
        raise BusinessRuleError(f"当前患者不处于{action_label}环节，请按流程顺序操作。", code="WRONG_STATE")


def require_profile_complete(patient: Patient) -> None:
    """守卫：批量导入患者必须先由医生核对并完善基本资料。"""
    if not patient.profile_complete:
        raise BusinessRuleError("请先完善患者基本资料，再发起60秒缓解预评估。", code="PROFILE_INCOMPLETE")


def require_revision(patient: Patient, expected_revision: int) -> None:
    """v0.3客户端须核对最新患者版本，避免用旧资料做临床确认。"""
    if patient.clinical_revision != expected_revision:
        raise ConflictError("患者资料已更新，请刷新并重新核对本次记录。", code="STALE_PATIENT")


def prepare_measurement_snapshot(
    patient: Patient,
    *,
    weight_kg: float | None,
    height_cm: float | None,
) -> tuple[dict[str, float], dict[str, object]]:
    """校验本次测量并返回事件快照与患者最新值更新。

    每次临床评估必须重新填写体重。身高只在患者尚无身高时允许首次填写；
    已确认身高只能由管理员在患者档案专用接口更正。BMI 只作为数值快照，
    不参与任何临床分支。
    """
    if weight_kg is None:
        raise BusinessRuleError("请填写本次体重，不能沿用上一次记录。", code="WEIGHT_REQUIRED")

    if patient.height_cm is None:
        if height_cm is None:
            raise BusinessRuleError("请先填写并确认患者身高。", code="HEIGHT_REQUIRED")
        effective_height = float(height_cm)
    else:
        effective_height = float(patient.height_cm)
        if height_cm is not None and abs(float(height_cm) - effective_height) > 1e-6:
            raise BusinessRuleError(
                "患者身高已确认并锁定；如需更正，请由管理员在患者工作台操作。",
                code="HEIGHT_LOCKED",
            )

    snapshot = {
        "height_cm": effective_height,
        "weight_kg": float(weight_kg),
        "bmi": float(calculate_bmi(effective_height, float(weight_kg))),
    }
    return snapshot, dict(snapshot)


def record_outcome(
    db: Session,
    *,
    patient: Patient,
    operator: User,
    source_state: str,
    target_state: str,
    rule_id: str,
    template_id: str | None,
    output_text: str,
    payload: dict | None = None,
    request_id: str | None = None,
    source: str = "doctor",
    updates: dict[str, object] | None = None,
    clinical_contract_version: str = "v1.0",
    transition_ids: list[str] | None = None,
    expected_revision: int | None = None,
    objective_met: bool = False,
    associated_record_ids: list[int] | None = None,
) -> Event:
    """写入一次决策的完整结果并提交。

    顺序：幂等检查 → 状态与字段落库 → 事件流水 → 审计日志 → 提交。

    参数:
        source_state (str): 决策前的状态（事件流水要求记录迁移两端）。
        request_id (str | None): 客户端请求标识；重复提交时拒绝，避免重复事件。
        source (str): doctor（医生操作）/ system（系统自动动作）。
        updates (dict | None): 需要一并更新的患者字段。

    异常:
        ConflictError: request_id 已存在（重复提交）。
    """
    # 所有临床落库统一从这里经过，避免新增接口时遗漏横向越权守卫
    require_patient_write_access(operator, patient)
    if patient.current_state != source_state:
        raise ConflictError("患者流程已变化，请刷新后重新核对。", code="STALE_PATIENT")
    if patient.clinical_contract_version == "v0.3" and clinical_contract_version != "v0.3":
        raise BusinessRuleError("此患者已采用新版流程，请刷新工作台后使用新版表单。", code="V03_REQUIRED")
    if clinical_contract_version == "v0.3":
        if expected_revision is None or not transition_ids:
            raise BusinessRuleError("本次记录缺少资料版本或流程核对，请刷新后重试。", code="V03_CONTRACT_REQUIRED")
        require_revision(patient, expected_revision)
    elif clinical_contract_version != "v1.0" or transition_ids is not None:
        raise BusinessRuleError("本次记录的流程版本无法识别。", code="UNKNOWN_CONTRACT")
    if objective_met and (clinical_contract_version != "v0.3" or transition_ids != ["T34"]):
        raise BusinessRuleError("客观核对记录无效，请重新核对。", code="INVALID_OBJECTIVE_EVENT")
    # 幂等：同一个 request_id 只允许成功一次
    if request_id and events_repo.find_by_request_id(db, patient.id, request_id) is not None:
        raise ConflictError("该操作已经提交过，本次未重复记录。", code="DUPLICATE_REQUEST")

    # 模拟日期只能作用于测试患者；真实患者在任何临床写入发生前即被硬阻断
    event_simulated_date = simulated_date_for_event(operator, patient)

    if clinical_contract_version == "v0.3":
        # 任何新的临床决定都会撤销旧客观核对资格；确认动作已在接口验证原快照。
        updates = {**(updates or {}), "clinical_contract_version": "v0.3",
                   "objective_assessment_event_id": None, "objective_assessment_revision": None,
                   "objective_assessment_digest": None}

    try:
        patients_repo.apply_outcome(db, patient, target_state=target_state, updates=updates, transition_ids=transition_ids)
    except StaleDataError as exc:
        # flush失败后必须显式回滚，事件与审计不能成为半笔提交。
        db.rollback()
        raise ConflictError("患者资料已更新，请刷新并重新核对本次记录。", code="STALE_PATIENT") from exc
    event = events_repo.add_event(
        db,
        patient_id=patient.id,
        operator_id=operator.id,
        source=source,
        rule_id=rule_id,
        source_state=source_state,
        target_state=target_state,
        template_id=template_id,
        output_text=output_text,
        payload=payload,
        request_id=request_id,
        simulated_date=event_simulated_date,
        clinical_contract_version=clinical_contract_version,
        transition_ids=transition_ids,
    )
    # 新记录与事件同一事务建立来源；已提交的历史资料绝不改写。
    if associated_record_ids:
        from app.models.clinical_record import ClinicalRecord
        for record_id in set(associated_record_ids):
            record = db.get(ClinicalRecord, record_id)
            if record is None or record.patient_id != patient.id:
                raise BusinessRuleError("资料来源与病例不一致")
            if record.source_event_id is None:
                record.source_event_id = event.id
                record.source_index = record.id
    if objective_met:
        patient.objective_assessment_event_id = event.id
        # 明确预留本次资格写入版本，并将资格绑定同一个版本；不依赖隐式flush次数。
        patient.clinical_revision += 1
        patient.objective_assessment_revision = patient.clinical_revision
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        patient.objective_assessment_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    # 审计只记录"谁做了什么"，不记录临床输入内容
    audit_repo.write_audit(
        db,
        action="event_write",
        operator_id=operator.id,
        target_type="patient",
        target_id=patient.id,
        detail={
            "rule_id": rule_id,
            "source": source,
            "simulated_date": event_simulated_date.isoformat() if event_simulated_date else None,
        },
    )
    db.commit()
    return event
