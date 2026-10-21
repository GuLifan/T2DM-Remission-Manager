"""管理员邀请码、账号停用与病例重置接口；历史只归档不删除。"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import get_patient_or_404, patient_out, require_admin, require_patient_write_access
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.demo import DemoInvite, DemoSession
from app.models.schemas import PatientOut
from app.models.user import User
from app.repository.audit import write_audit
from app.repository.database import get_db
from app.repository.departments import is_active_name
from app.services.demo import digest, new_case

router = APIRouter(tags=["demo 管理"])


class InviteIn(BaseModel):
    label: str = Field(default="", max_length=80)
    valid_days: int = Field(default=7, ge=1, le=90)


class UserEnabledIn(BaseModel):
    is_active: bool


class CaseIn(BaseModel):
    """没有场景编号或患者模板；必须手工填写新的虚构资料。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=64)
    gender: str = Field(pattern="^[男女]$")
    birth_date: date
    department: str = Field(min_length=1, max_length=128)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        if value.year < 1900 or value > date.today():
            raise ValueError("请填写1900年至今的有效出生年月")
        return value.replace(day=1)


@router.post("/demo/cases", response_model=PatientOut, status_code=201)
def create_case(payload: CaseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PatientOut:
    if not is_active_name(db, payload.department):
        raise BusinessRuleError("请选择科室字典中的有效科室。", code="DEPARTMENT_INVALID")
    fresh = new_case(db, user, **payload.model_dump())
    write_audit(db, action="demo_case_create", operator_id=user.id, target_type="patient", target_id=fresh.id)
    db.commit()
    return patient_out(db, fresh, user)


@router.get("/admin/invites")
def invites(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_admin(user)
    return [
        {
            "id": i.id,
            "label": i.label,
            "expires_at": i.expires_at,
            "used": i.consumed_at is not None,
            "revoked": i.revoked_at is not None,
        }
        for i in db.scalars(select(DemoInvite).order_by(DemoInvite.id.desc()))
    ]


@router.post("/admin/invites", status_code=201)
def create_invite(payload: InviteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_admin(user)
    code = secrets.token_urlsafe(24)
    invite = DemoInvite(
        digest=digest(code),
        label=payload.label,
        created_by=user.id,
        expires_at=datetime.now() + timedelta(days=payload.valid_days),
    )
    db.add(invite)
    db.flush()
    write_audit(db, action="invite_create", operator_id=user.id, target_type="invite", target_id=invite.id)
    db.commit()
    return {"id": invite.id, "code": code, "expires_at": invite.expires_at}


@router.post("/admin/invites/{invite_id}/revoke")
def revoke(invite_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_admin(user)
    invite = db.get(DemoInvite, invite_id)
    if not invite:
        raise NotFoundError("邀请码不存在。")
    invite.revoked_at = datetime.now()
    write_audit(db, action="invite_revoke", operator_id=user.id, target_type="invite", target_id=invite.id)
    db.commit()
    return {"message": "邀请码已撤销。"}


@router.get("/admin/users")
def users(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_admin(user)
    return [
        {"id": u.id, "username": u.username, "display_name": u.display_name, "is_active": u.is_active}
        for u in db.scalars(select(User).where(User.role == "doctor").order_by(User.id))
    ]


@router.put("/admin/users/{user_id}/enabled")
def enable(
    user_id: int, payload: UserEnabledIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    require_admin(user)
    target = db.get(User, user_id)
    if not target or target.role != "doctor":
        raise BusinessRuleError("只能管理医生账号。", code="DOCTOR_REQUIRED")
    target.is_active = payload.is_active
    db.execute(delete(DemoSession).where(DemoSession.user_id == target.id))
    write_audit(
        db,
        action="doctor_enabled",
        operator_id=user.id,
        target_type="user",
        target_id=target.id,
        detail={"is_active": payload.is_active},
    )
    db.commit()
    return {"message": "账号状态已更新，原有会话已失效。"}


@router.post("/patients/{patient_id}/reset", response_model=PatientOut, status_code=201)
def reset(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PatientOut:
    old = get_patient_or_404(db, patient_id)
    require_patient_write_access(user, old)
    owner = db.get(User, old.owner_id)
    if owner is None or not old.is_test_patient:
        raise BusinessRuleError("仅允许归档并新建归属明确的病例。", code="DEMO_REQUIRED")
    old.archived = True
    # 仅保留本次由医师手工创建的基本虚构资料，临床快照从零开始。
    fresh = new_case(db, owner, name=old.name, gender=old.gender, birth_date=old.birth_date, department=old.department)
    write_audit(
        db,
        action="demo_reset",
        operator_id=user.id,
        target_type="patient",
        target_id=old.id,
        detail={"new_patient_id": fresh.id},
    )
    db.commit()
    return patient_out(db, fresh, user)
