"""隔离虚构病例及邀请注册；全部写入由调用方同事务提交。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.demo import DemoInvite
from app.models.patient import Patient
from app.models.user import User


def digest(value: str) -> str:
    """不可逆摘要；不把邀请码或会话原文写入数据库。"""
    return hashlib.sha256(value.encode()).hexdigest()


def consume_invite(db: Session, code: str) -> DemoInvite:
    """条件 UPDATE 先取得写锁；同一邀请码并发请求不能各自通过检查。"""
    now = datetime.now()
    result = db.execute(
        update(DemoInvite)
        .where(
            DemoInvite.digest == digest(code.strip()),
            DemoInvite.expires_at > now,
            DemoInvite.consumed_at.is_(None),
            DemoInvite.revoked_at.is_(None),
        )
        .values(consumed_at=now)
        .returning(DemoInvite)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise BusinessRuleError("邀请码无效、已使用或已过期，请向管理员申请。", code="INVITE_INVALID")
    return invite


def new_case(db: Session, user: User, *, name: str, gender: str, birth_date: date, department: str) -> Patient:
    """由医生从零建档；只保存其手工填写的虚构资料，不载入任何预置病例。"""
    patient = Patient(
        name=name,
        gender=gender,
        birth_date=birth_date.replace(day=1),
        medical_record_no=f"DEMO-{user.id}-{secrets.token_hex(6)}",
        department=department,
        created_by=user.id,
        owner_id=user.id,
        profile_complete=True,
        is_test_patient=True,
        current_state="ST10",
        clinical_contract_version="v0.3",
        archived=False,
    )
    db.add(patient)
    db.flush()
    return patient
