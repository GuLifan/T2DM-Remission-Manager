"""
模块名称：remission_judge.py
所属层级：接口层（api）
功能说明：单元5（缓解判定）的三个入口——核对、落库、医生确认。

接口语义（V1.0 修正 V0.1 的 L5 问题）：
    - `POST /remission-judge/check`：**纯查询**，只核对客观条件并返回提示，**不写库、不写事件**；
    - `POST /remission-judge/route`：把核对结论落库（含状态迁移与事件），需要医生选择返回阶段时，
      请求必须带 `target_stage`；缺少时返回提示且不落库；
    - `POST /remission-judge/confirm`：医生确认环节（E4-B04/B05）。

    为什么这样拆：V0.1 的"核对"接口会顺带改变患者状态，HTTP 语义与副作用不一致，
    排查问题时无法分辨"医生看过"和"系统已改状态"。拆分后，核对随时可重复调用而不留痕。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, record_outcome, require_state
from app.core.exceptions import BusinessRuleError
from app.core.test_mode import effective_today_for_patient
from app.domain import enums
from app.domain.states import ST31, ST32, ST50
from app.models.clinical import RemissionConfirmInput, RemissionJudgeInput, RemissionJudgeResult
from app.models.user import User
from app.repository import events as events_repo
from app.repository.database import get_db
from app.services.remission_judge import check_remission, confirm_remission

router = APIRouter(prefix="/patients", tags=["单元5：缓解判定"])


def _run_check(patient, payload: RemissionJudgeInput, current_user: User) -> RemissionJudgeResult:
    """执行客观条件核对（纯函数调用，不触碰数据库）。"""
    return check_remission(
        patient.current_state,
        payload,
        today=effective_today_for_patient(current_user, patient),
        earliest_judge_date=patient.earliest_judge_date,
        has_glucose_lowering_drug=patient.has_glucose_lowering_drug,
    )


@router.post("/{patient_id}/remission-judge/check", response_model=RemissionJudgeResult)
def check(
    patient_id: int,
    payload: RemissionJudgeInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemissionJudgeResult:
    """核对客观条件（只读，不写库、不写事件）。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST50,), "缓解判定")
    return _run_check(patient, payload, current_user)


@router.post("/{patient_id}/remission-judge/route", response_model=RemissionJudgeResult)
def route(
    patient_id: int,
    payload: RemissionJudgeInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemissionJudgeResult:
    """把核对结论落库（状态迁移 + 事件 + 审计同事务）。

    注意：客观条件满足（E4-B03）时**不改变状态**（仍停留在判定环节），
    必须再由医生调用 confirm 才算形成缓解结论——系统绝不自动确认缓解。
    """
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST50,), "缓解判定")
    source_state = patient.current_state
    result = _run_check(patient, payload, current_user)
    target_state = result.target_state

    # 需要医生选择返回阶段的分支：未选择时不落库，只把提示返回给前台
    if result.needs_target_stage:
        if payload.target_stage not in (enums.STAGE_STABLE, enums.STAGE_INDUCTION):
            return result
        target_state = ST31 if payload.target_stage == enums.STAGE_STABLE else ST32

    updates: dict[str, object] = {}
    if target_state in (ST31, ST32):
        updates["stage"] = payload.target_stage
        updates["next_review_date"] = None

    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=target_state,
        rule_id=result.rule_id,
        template_id=result.template_id,
        output_text=result.output_text,
        payload=payload.model_dump(mode="json"),
        request_id=payload.request_id,
        updates=updates,
    )
    # 回填最终目标状态（可能由医生选择的阶段决定）
    result.target_state = target_state
    return result


@router.post("/{patient_id}/remission-judge/confirm", response_model=RemissionJudgeResult)
def confirm(
    patient_id: int,
    payload: RemissionConfirmInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemissionJudgeResult:
    """医生确认是否形成"2型糖尿病缓解"结论。

    入口守卫（IMP-3）：确认前必须已经存在一次"客观条件满足"事件，
    防止绕过核对直接确认缓解。
    """
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST50,), "缓解判定")

    # 守卫：最近的事件里必须存在客观满足记录
    has_objective_event = any(
        event.rule_id == "E4-B03" for event in events_repo.list_events(db, patient.id, limit=50)
    )
    if not has_objective_event:
        raise BusinessRuleError(
            "请先完成客观条件核对，再由医生确认是否形成缓解结论。", code="OBJECTIVE_CHECK_REQUIRED"
        )

    source_state = patient.current_state
    result = confirm_remission(source_state, payload.f048_confirm, payload.f012_pre_tasks)

    updates: dict[str, object] = {}
    if result.target_state == ST50 and payload.f048_confirm == "确认":
        # 理论上不会走到这里（确认必然转 ST60），留作防御
        raise BusinessRuleError("确认动作未能形成缓解结论，请联系系统维护人员。", code="CONFIRM_FAILED")

    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=result.target_state,
        rule_id=result.rule_id,
        template_id=result.template_id,
        output_text=result.output_text,
        payload=payload.model_dump(mode="json"),
        request_id=payload.request_id,
        updates=updates,
    )
    return result
