"""
模块名称：phase_review.py
所属层级：接口层（api）
功能说明：单元3（阶段复评与治疗调整）的提交入口。

关键落库约定：
    1. 停用最后一种降糖药时，写入停药日期与最早可判定日期，并清空当前阶段
       （系统自动进入观察期，不存在"进入观察期"按钮）；
    2. 非停药分支**每次复评都按医生本次确认刷新用药状态**（F053/F054）——
       这是 V0.1 的 R1 缺陷修复点：若只在"有药"时写 True，旧值会残留，
       导致缓解判定被陈旧状态错误阻断；
    3. 被更高优先级分支覆盖的说明随响应返回，并由事件载荷留痕，不做静默丢弃。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, record_outcome, require_state
from app.core.clock import system_clock
from app.domain.states import ST00, ST31, ST32
from app.models.clinical import PhaseReviewInput, PhaseReviewResult
from app.models.user import User
from app.repository.database import get_db
from app.services.phase_review import evaluate_phase_review

router = APIRouter(prefix="/patients", tags=["单元3：阶段复评"])


@router.post("/{patient_id}/phase-review", response_model=PhaseReviewResult)
def submit_phase_review(
    patient_id: int,
    payload: PhaseReviewInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PhaseReviewResult:
    """提交阶段复评，执行治疗调整决策。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST31, ST32), "阶段复评")
    source_state = patient.current_state

    result = evaluate_phase_review(
        source_state,
        payload,
        system_clock.today(),
        # 观察期时间锚点由患者档案提供（如适用）
        lifestyle_start_date=patient.lifestyle_start_date,
        surgery_date=patient.surgery_date,
    )

    if result.entered_observation and payload.f036_stop_date is not None:
        # 停用最后一种降糖药：进入观察期，记录锚点与最早可判定日期
        updates: dict[str, object] = {
            "stage": None,
            "next_review_date": None,
            "last_med_stop_date": payload.f036_stop_date,
            "earliest_judge_date": result.earliest_judge_date,
            # 停药后不再存在降糖作用药物（与最小字段映射一致）
            "has_glucose_lowering_drug": False,
            "drug_purpose": None,
        }
    else:
        # 非停药分支：按本次确认刷新用药状态（R1 修复点，禁止只在"有药"时更新）
        updates = {
            "has_glucose_lowering_drug": payload.f053_has_drug,
            "drug_purpose": payload.f054_purpose if payload.f053_has_drug else None,
        }
        if result.target_state in (ST31, ST32):
            updates["stage"] = result.stage
            updates["next_review_date"] = result.next_review_date
        if result.stage_goal is not None:
            updates["stage_goal"] = result.stage_goal
        if result.target_state == ST00:
            updates.update({"stage": None, "stage_goal": None, "interventions": None, "next_review_date": None})

    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=result.target_state,
        rule_id=result.rule_id,
        template_id=result.template_id,
        output_text=result.output_text,
        payload={
            **payload.model_dump(mode="json"),
            # 被忽略的分支写入事件载荷，保证"当时还有哪些分支为真"可追溯
            "ignored_branches": result.ignored_branches,
        },
        request_id=payload.request_id,
        updates=updates,
    )
    return result
