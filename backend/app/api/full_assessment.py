"""
模块名称：full_assessment.py
所属层级：接口层（api）
功能说明：单元2（完整评估并形成主动管理计划）的提交入口。

一次请求完成：评估资料 + 是否启动 + 当前阶段 + 一个主要目标 + 干预组合 + 首次复评时间
（锁定稿§6：不得拆成连续重复页面）。

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
from app.domain.states import ST00, ST20, ST31, ST32
from app.models.clinical import FullAssessmentInput, FullAssessmentResult
from app.models.user import User
from app.repository.database import get_db
from app.services.full_assessment import evaluate_full_assessment
from app.utils.measurements import calculate_bmi

router = APIRouter(prefix="/patients", tags=["单元2：完整评估与计划"])


@router.post("/{patient_id}/full-assessment", response_model=FullAssessmentResult)
def submit_full_assessment(
    patient_id: int,
    payload: FullAssessmentInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FullAssessmentResult:
    """提交完整评估并形成主动管理计划（或暂缓、或不启动）。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST20,), "完整评估")
    source_state = patient.current_state

    result = evaluate_full_assessment(
        source_state,
        payload,
        effective_today_for_patient(current_user, patient),
    )

    # 完整评估沿用预评估测量值；若医生本次修改，也必须成对提交并同步最新 BMI 快照。
    if (payload.f018_weight is None) != (payload.f019_height is None):
        raise BusinessRuleError("身高和体重需同时填写，或同时留空。", code="MEASUREMENTS_INCOMPLETE")
    measurement_updates: dict[str, object] = {}
    if payload.f018_weight is not None and payload.f019_height is not None:
        measurement_updates = {
            "weight_kg": payload.f018_weight,
            "height_cm": payload.f019_height,
            "bmi": calculate_bmi(payload.f019_height, payload.f018_weight),
        }

    # 按结论更新患者档案字段：启动时写入计划，暂缓时保持不变，不启动时清空计划
    if result.target_state in (ST31, ST32):
        updates: dict[str, object] = {
            **measurement_updates,
            "stage": result.stage,
            "stage_goal": result.stage_goal,
            "interventions": result.interventions,
            "next_review_date": result.next_review_date,
        }
    elif result.target_state == ST00:
        updates = {
            **measurement_updates,
            "stage": None,
            "stage_goal": None,
            "interventions": None,
            "next_review_date": None,
        }
    else:
        # 暂缓补充资料：留在 ST20，档案字段不变
        updates = measurement_updates

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
