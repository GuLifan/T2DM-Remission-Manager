"""
模块名称：observation.py
所属层级：接口层（api）
功能说明：单元4（缓解观察期，系统自动状态）的三个入口。

设计要点：
    - 观察期为系统自动状态：**没有"进入观察期"按钮，也没有停药确认页**；
    - 查询接口不写库（纯读取），到期与否由系统按 F040 计算；
    - 到期后由医生点击"进入缓解判定"（A1-B03）——这是系统开放入口，不是新增临床节点。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, record_outcome, require_state
from app.core.clock import system_clock
from app.core.exceptions import BusinessRuleError
from app.domain import templates
from app.domain.states import ST40, ST50
from app.models.clinical import MedicationRestartInput, MedicationRestartResult, ObservationStatus
from app.models.user import User
from app.repository.database import get_db
from app.services.observation import evaluate_medication_restart, get_observation_status

router = APIRouter(prefix="/patients", tags=["单元4：缓解观察期"])


@router.get("/{patient_id}/observation", response_model=ObservationStatus)
def read_observation(
    patient_id: int,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObservationStatus:
    """读取观察期状态（只读，不产生事件）。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST40,), "缓解观察期")
    return get_observation_status(
        last_med_stop_date=patient.last_med_stop_date,
        lifestyle_start_date=patient.lifestyle_start_date,
        surgery_date=patient.surgery_date,
        today=system_clock.today(),
    )


@router.post("/{patient_id}/observation/enter-judge", response_model=ObservationStatus)
def enter_judgement(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObservationStatus:
    """到期后进入正式缓解判定（ST40 → ST50）。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST40,), "缓解观察期")
    status = get_observation_status(
        last_med_stop_date=patient.last_med_stop_date,
        lifestyle_start_date=patient.lifestyle_start_date,
        surgery_date=patient.surgery_date,
        today=system_clock.today(),
    )
    # 未到期不得提前判定：系统只放行"到期"这一条路
    if not status.due:
        raise BusinessRuleError(
            "尚未到达最早可判定日期，暂不能进入缓解判定。", code="NOT_DUE"
        )
    source_state = patient.current_state
    record_outcome(
        db,
        patient=patient,
        operator=current_user,
        source_state=source_state,
        target_state=ST50,
        rule_id="A1-B03",
        template_id="OUT-A1-DUE",
        output_text=templates.render("OUT-A1-DUE"),
        payload={"earliest_judge_date": status.earliest_judge_date.isoformat() if status.earliest_judge_date else None},
        updates={"next_review_date": None},
    )
    return status


@router.post("/{patient_id}/observation/medication-restart", response_model=MedicationRestartResult)
def medication_restart(
    patient_id: int,
    payload: MedicationRestartInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationRestartResult:
    """观察期重新使用降糖作用药物 → 退出观察期并返回阶段复评。"""
    patient = get_patient_or_404(db, patient_id)
    require_state(patient, (ST40,), "缓解观察期")
    source_state = patient.current_state

    try:
        result = evaluate_medication_restart(source_state, payload)
    except ValueError as error:
        # 服务层的值错误在这里转换成医生可读提示
        raise BusinessRuleError(str(error), code="TARGET_STAGE_REQUIRED") from error

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
        updates={
            "stage": result.stage,
            # 退出观察期：可判定观察结束，但保留历史锚点供追溯
            "has_glucose_lowering_drug": True,
            "drug_purpose": payload.f037_reason.replace("因", ""),
        },
    )
    return result
