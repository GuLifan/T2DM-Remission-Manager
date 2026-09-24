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

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.test_mode import simulated_date_for_event
from app.models.patient import Patient
from app.models.schemas import PatientOut
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import events as events_repo
from app.repository import patients as patients_repo
from app.repository import users as users_repo


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
    return user.role == "admin" or patient.owner_id == user.id


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
) -> None:
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
    # 幂等：同一个 request_id 只允许成功一次
    if request_id and events_repo.find_by_request_id(db, patient.id, request_id) is not None:
        raise ConflictError("该操作已经提交过，本次未重复记录。", code="DUPLICATE_REQUEST")

    # 模拟日期只能作用于测试患者；真实患者在任何临床写入发生前即被硬阻断
    event_simulated_date = simulated_date_for_event(operator, patient)

    patients_repo.apply_outcome(db, patient, target_state=target_state, updates=updates)
    events_repo.add_event(
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
    )
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
