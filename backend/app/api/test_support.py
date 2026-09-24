"""
模块名称：test_support.py
所属层级：接口层（api）
功能说明：第一批测试能力接口——账号级模拟日期与测试患者状态跳转。

安全边界：
    1. 所有写入口都要求 ETMMS_TEST_MODE 已开启且当前账号为测试账号；
    2. 状态跳转与模拟日期下的流程只能作用于明确标记的测试患者；
    3. 测试跳转不修改正式状态机矩阵，事件以 source='debug' 单独留痕；
    4. 真实患者由后端返回 403，前端隐藏按钮不是安全边界。

修改历史：
    - 2026-09-24  v1.0  第一批测试可用性实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import (
    get_patient_or_404,
    patient_out,
    require_patient_write_access,
)
from app.config import get_settings
from app.core.clock import system_clock
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.test_mode import (
    effective_today,
    effective_today_for_patient,
    require_test_account,
    require_test_patient,
    test_capability_enabled,
)
from app.domain import enums
from app.domain.states import ALL_STATES, ST31, ST32, ST40, ST50, ST60, state_name
from app.models.schemas import DebugJumpIn, PatientOut, SimulatedDateIn, TestContextOut
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import events as events_repo
from app.repository import users as users_repo
from app.repository.database import get_db
from app.utils.date_utils import add_months_clamped

router = APIRouter(tags=["测试支持"])


def _context(user: User) -> TestContextOut:
    """构造当前账号的测试能力与日期上下文。"""
    return TestContextOut(
        test_mode_enabled=get_settings().test_mode,
        can_use_test_tools=test_capability_enabled(user),
        real_date=system_clock.today(),
        effective_date=effective_today(user),
        simulated_date=user.simulated_date if test_capability_enabled(user) else None,
    )


@router.get("/test-context", response_model=TestContextOut)
def read_test_context(current_user: User = Depends(get_current_user)) -> TestContextOut:
    """读取当前日期；普通账号也可读取，但不能修改。"""
    return _context(current_user)


@router.post("/test-context/simulated-date", response_model=TestContextOut)
def set_simulated_date(
    payload: SimulatedDateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TestContextOut:
    """设置或清除当前测试账号的持久化模拟日期。"""
    require_test_account(current_user)
    users_repo.set_simulated_date(db, current_user, payload.simulated_date)
    audit_repo.write_audit(
        db,
        action="simulated_date_set" if payload.simulated_date else "simulated_date_clear",
        operator_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
        detail={
            "simulated_date": payload.simulated_date.isoformat() if payload.simulated_date else None
        },
    )
    db.commit()
    return _context(current_user)


@router.post("/patients/{patient_id}/debug/jump-state", response_model=PatientOut)
def debug_jump_state(
    patient_id: int,
    payload: DebugJumpIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientOut:
    """把测试患者直接切换到指定状态，并以 debug 事件留痕。"""
    patient = get_patient_or_404(db, patient_id)
    require_patient_write_access(current_user, patient)
    require_test_account(current_user)
    require_test_patient(patient)

    if payload.target_state not in ALL_STATES:
        raise BusinessRuleError("请选择有效的测试环节。", code="UNKNOWN_DEBUG_STATE")
    if payload.request_id and events_repo.find_by_request_id(db, patient.id, payload.request_id):
        raise ConflictError("该测试跳转已经执行过，本次未重复记录。", code="DUPLICATE_REQUEST")

    # 调试入口刻意不调用 validate_transition；正式流程仍只能走领域状态机
    source_state = patient.current_state
    target_state = payload.target_state
    today = effective_today_for_patient(current_user, patient)
    patient.current_state = target_state

    # 主动管理页面需要明确阶段；其他页面不保留过期阶段标签
    if target_state == ST31:
        patient.stage = enums.STAGE_STABLE
    elif target_state == ST32:
        patient.stage = enums.STAGE_INDUCTION
    else:
        patient.stage = None

    # 为观察与判定页面补最小测试锚点；只影响已标记测试患者
    if target_state == ST40 and patient.last_med_stop_date is None:
        patient.last_med_stop_date = today
        patient.earliest_judge_date = add_months_clamped(today, 3)
        patient.has_glucose_lowering_drug = False
    if target_state == ST50:
        patient.last_med_stop_date = patient.last_med_stop_date or add_months_clamped(today, -3)
        patient.earliest_judge_date = patient.earliest_judge_date or today
        patient.has_glucose_lowering_drug = False
    if target_state == ST60 and patient.remission_confirmed_date is None:
        patient.remission_confirmed_date = today

    output_text = f"测试模式：已切换至“{state_name(target_state)}”。本记录不属于正式临床流程。"
    events_repo.add_event(
        db,
        patient_id=patient.id,
        operator_id=current_user.id,
        source="debug",
        rule_id="DEBUG-JUMP",
        source_state=source_state,
        target_state=target_state,
        template_id=None,
        output_text=output_text,
        payload={"target_state": target_state},
        request_id=payload.request_id,
        simulated_date=current_user.simulated_date,
    )
    audit_repo.write_audit(
        db,
        action="debug_jump_state",
        operator_id=current_user.id,
        target_type="patient",
        target_id=patient.id,
        detail={
            "source_state": source_state,
            "target_state": target_state,
            "simulated_date": current_user.simulated_date.isoformat()
            if current_user.simulated_date
            else None,
        },
    )
    db.commit()
    return patient_out(db, patient, current_user)
