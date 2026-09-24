"""
模块名称：pre_assessment.py
所属层级：接口层（api）
功能说明：单元1（60秒缓解预评估）的三个入口——提交预评估、急性安全后快速建档、关闭路径。

临床流程要点：
    - 预评估只产生三类主结论；暂缓为自环（仍停在预评估），必须带前置任务与返回位置；
    - "快速建档"（急性安全稳定化后）与"关闭路径"（分型复核为其他类型）都必须以
      最近一次事件作为守卫，防止绕过预评估直接跳转（`_SPEC/07` IMP-4 / IMP-5）。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, record_outcome, require_profile_complete, require_state
from app.core.exceptions import BusinessRuleError
from app.core.test_mode import effective_today_for_patient
from app.domain import enums, templates
from app.domain.states import ST00, ST10, ST31, ST99
from app.models.clinical import AcuteStabilizedInput, FullAssessmentResult, PreAssessmentInput, PreAssessmentResult
from app.models.user import User
from app.repository import events as events_repo
from app.repository.database import get_db
from app.services import defaults
from app.services.pre_assessment import evaluate_pre_assessment
from app.utils.measurements import calculate_bmi

router = APIRouter(prefix="/patients", tags=["单元1：60秒缓解预评估"])


def _latest_rule_id(db: Session, patient_id: int) -> str | None:
    """取该患者最近一次事件的规则 ID（用于快速建档与关闭路径的入口守卫）。"""
    recent = events_repo.list_events(db, patient_id, limit=1)
    return recent[0].rule_id if recent else None


@router.post("/{patient_id}/pre-assessment", response_model=PreAssessmentResult)
def submit_pre_assessment(
    patient_id: int,
    payload: PreAssessmentInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreAssessmentResult:
    """提交 60 秒预评估，得到三类主结论之一。"""
    patient = get_patient_or_404(db, patient_id)
    require_profile_complete(patient)
    require_state(patient, (ST10,), "60秒缓解预评估")
    source_state = patient.current_state

    result = evaluate_pre_assessment(source_state, payload)

    # 身高与体重必须成对记录，避免档案里长期留下无法解释的半组测量值。
    if (payload.f018_weight is None) != (payload.f019_height is None):
        raise BusinessRuleError("身高和体重需同时填写，或同时留空。", code="MEASUREMENTS_INCOMPLETE")
    measurement_updates: dict[str, object] = {}
    if payload.f018_weight is not None and payload.f019_height is not None:
        measurement_updates = {
            "weight_kg": payload.f018_weight,
            "height_cm": payload.f019_height,
            "bmi": calculate_bmi(payload.f019_height, payload.f018_weight),
        }

    # 回到常规管理时清空阶段相关字段；暂缓（自环）与进入完整评估时不动这些字段
    updates: dict[str, object] = measurement_updates
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
        # 事件载荷保留暂缓原因，便于日后追溯"当时为什么暂缓"
        payload={**payload.model_dump(mode="json"), "hold_reasons": result.hold_reasons},
        request_id=payload.request_id,
        updates=updates,
    )
    return result


@router.post("/{patient_id}/pre-assessment/acute-stabilized", response_model=FullAssessmentResult)
def enter_stable_after_acute(
    patient_id: int,
    payload: AcuteStabilizedInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FullAssessmentResult:
    """急性安全暂缓处理后，医生确认已稳定化 → 快速建档直接进入血糖稳定阶段。

    不重复预评估、不重复完整评估：只补录事件2所需的阶段目标与干预组合（Q-06 裁决）。
    """
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST10,), "60秒缓解预评估")
    # IMP-4 守卫：只有"最近一次是急性安全暂缓"才能走快速建档，避免绕过预评估
    if _latest_rule_id(db, patient.id) != "E1-B02":
        raise BusinessRuleError(
            "只有急性安全暂缓并完成稳定化治疗后，才能直接进入血糖稳定阶段。", code="ACUTE_PATH_ONLY"
        )
    if not payload.interventions:
        raise BusinessRuleError("快速建档时至少选择一种干预组合。", code="INTERVENTIONS_REQUIRED")

    source_state = patient.current_state
    next_review = payload.next_review_date or defaults.default_next_review_date(
        effective_today_for_patient(current_user, patient)
    )
    interventions = "、".join(payload.interventions)
    output_text = templates.render(
        "OUT-E2-STABLE",
        stage_goal=payload.stage_goal,
        interventions=interventions,
        next_review_date=next_review.isoformat(),
    )
    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=ST31,
        rule_id="E1-B02-STABILIZED",
        template_id="OUT-E2-STABLE",
        output_text=output_text,
        payload=payload.model_dump(mode="json"),
        request_id=payload.request_id,
        updates={
            "stage": enums.STAGE_STABLE,
            "stage_goal": payload.stage_goal,
            "interventions": interventions,
            "next_review_date": next_review,
        },
    )
    return FullAssessmentResult(
        rule_id="E1-B02-STABILIZED",
        template_id="OUT-E2-STABLE",
        output_text=output_text,
        target_state=ST31,
        stage=enums.STAGE_STABLE,
        stage_goal=payload.stage_goal,
        interventions=interventions,
        next_review_date=next_review,
    )


@router.post("/{patient_id}/pre-assessment/close-path", response_model=PreAssessmentResult)
def close_path(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreAssessmentResult:
    """分型复核明确为其他类型糖尿病 → 关闭 T2DM 缓解管理路径（终态，无出口）。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST10,), "60秒缓解预评估")
    # IMP-5 守卫：只有"最近一次是分型存疑暂缓"才能关闭路径
    if _latest_rule_id(db, patient.id) != "E1-B03":
        raise BusinessRuleError(
            "只有在分型存疑暂缓并完成复核后，才能关闭本路径。", code="CLOSE_PATH_ONLY"
        )

    source_state = patient.current_state
    output_text = templates.render("SYS-E1-CLOSE")
    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=ST99,
        rule_id="SYS-E1-CLOSE",
        template_id="SYS-E1-CLOSE",
        output_text=output_text,
        payload={"reason": "分型复核明确为其他类型糖尿病"},
        updates={"stage": None, "stage_goal": None, "interventions": None, "next_review_date": None},
    )
    return PreAssessmentResult(
        conclusion="关闭路径",
        rule_id="SYS-E1-CLOSE",
        template_id="SYS-E1-CLOSE",
        output_text=output_text,
        target_state=ST99,
        hold_reasons=[],
    )
