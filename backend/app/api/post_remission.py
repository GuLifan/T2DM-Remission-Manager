"""
模块名称：post_remission.py
所属层级：接口层（api）
功能说明：单元6（缓解后复评）的提交入口。

落库约定：缓解维持/风险上升留在缓解后复评（自环）；不可评价与缓解终止返回事件3
（阶段由医生选择）；缓解终止且出现新分型证据时返回完整评估。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, record_outcome, require_state
from app.core.test_mode import effective_today_for_patient
from app.domain import enums
from app.domain.states import ST20, ST31, ST32, ST60
from app.models.clinical import PostRemissionInput, PostRemissionResult
from app.models.user import User
from app.repository.database import get_db
from app.services.post_remission import evaluate_post_remission

router = APIRouter(prefix="/patients", tags=["单元6：缓解后复评"])


@router.post("/{patient_id}/post-remission-review", response_model=PostRemissionResult)
def submit_post_remission_review(
    patient_id: int,
    payload: PostRemissionInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostRemissionResult:
    """提交缓解后复评。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST60,), "缓解后复评")
    source_state = patient.current_state

    result = evaluate_post_remission(
        source_state,
        payload,
        effective_today_for_patient(current_user, patient),
        remission_confirmed_date=patient.remission_confirmed_date,
    )

    updates: dict[str, object] = {"next_review_date": result.next_review_date}
    if result.target_state in (ST31, ST32):
        # 返回主动管理：写入医生选择的阶段
        updates["stage"] = payload.target_stage
        updates["stage_goal"] = None
    if result.target_state == ST20:
        # 出现新分型证据或重大变化：返回完整评估复核
        updates.update({"stage": None, "stage_goal": None, "interventions": None})
    if payload.f050_med_status in (enums.MED_FOR_ORGAN, enums.MED_FOR_WEIGHT):
        # 因器官/体重获益用药：记录用药状态，但不改变缓解历史（不等同于复发）
        updates["has_glucose_lowering_drug"] = True
        updates["drug_purpose"] = payload.f050_med_status.replace("因", "")
    elif payload.f050_med_status == enums.MED_UNUSED:
        updates["has_glucose_lowering_drug"] = False
        updates["drug_purpose"] = None

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
