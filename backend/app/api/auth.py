"""
模块名称：auth.py
所属层级：接口层（api）
功能说明：账号相关接口——首次运行引导创建账号、登录、登出、查询当前账号。

安全定位（`_SPEC/06` V1.0-Q-03）：账号用于可追溯性与责任绑定；
本版本面向单机/内网，不承诺作为系统安全边界。已实现的基础防护：
密码 scrypt 加盐哈希、令牌 HMAC 签名与超时、连续失败短期锁定。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.flow_common import require_admin
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.security import create_session_token, verify_password
from app.models.schemas import (
    AssignableDoctorOut,
    AuthStatusOut,
    BootstrapIn,
    LoginIn,
    LoginOut,
    RegisterIn,
    RegisterOut,
    UserOut,
)
from app.models.user import User
from app.repository import audit as audit_repo
from app.repository import departments as departments_repo
from app.repository import users as users_repo
from app.repository.database import get_db

router = APIRouter(prefix="/auth", tags=["账号"])


@router.get("/status", response_model=AuthStatusOut)
def auth_status(db: Session = Depends(get_db)) -> AuthStatusOut:
    """查询是否还没有任何账号（首次运行需要引导创建）。"""
    return AuthStatusOut(needs_bootstrap=users_repo.count_users(db) == 0)


@router.post("/bootstrap", response_model=LoginOut)
def bootstrap(payload: BootstrapIn, db: Session = Depends(get_db)) -> LoginOut:
    """创建首个正式管理员账号并直接登录。

    仅在系统内还没有任何账号时可用（防止后续被用来凭空创建账号）；不预置任何默认密码。
    """
    if users_repo.count_users(db) > 0:
        raise ConflictError("系统已存在账号，请直接登录。", code="ALREADY_BOOTSTRAPPED")
    user = users_repo.create_user(
        db,
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        role="admin",
    )
    # 同时建立系统保留账号，供后续系统自动事件记录操作者
    users_repo.system_user(db)
    audit_repo.write_audit(
        db,
        action="account_bootstrap",
        operator_id=user.id,
        target_type="user",
        target_id=user.id,
        detail={"username": user.username},
    )
    token, expires_at = create_session_token(user.id)
    db.commit()
    return LoginOut(token=token, expires_at=expires_at, user=UserOut.model_validate(user))


@router.post("/register", response_model=RegisterOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    """开放注册医生账号；注册成功后必须返回登录页自行登录。"""
    username = payload.username.strip()
    display_name = payload.display_name.strip()
    if len(username) < 3:
        raise BusinessRuleError("登录名至少 3 个非空字符。", code="USERNAME_INVALID")
    if not display_name:
        raise BusinessRuleError("请填写医师姓名。", code="DISPLAY_NAME_REQUIRED")
    if users_repo.get_by_username(db, username) is not None:
        raise ConflictError("该登录名已存在，请更换后重试。", code="USERNAME_DUPLICATED")
    department = payload.department.strip() if payload.department else None
    if department and not departments_repo.is_active_name(db, department):
        raise BusinessRuleError("所选科室不在当前科室字典中，请重新选择。", code="DEPARTMENT_INVALID")
    user = users_repo.create_user(
        db,
        username=username,
        display_name=display_name,
        password=payload.password,
        department=department,
        role="doctor",
    )
    audit_repo.write_audit(
        db,
        action="account_register",
        operator_id=user.id,
        target_type="user",
        target_id=user.id,
        detail={"username": user.username, "department": user.department},
    )
    db.commit()
    return RegisterOut(message="注册成功，请使用新账号登录。")


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    """登录。

    失败处理：账号不存在与密码错误返回同一句提示（避免账号枚举）；
    连续失败达到阈值后短期锁定，并写入审计日志。
    """
    user = users_repo.get_by_username(db, payload.username)
    # 账号不存在：记录审计后返回统一提示
    if user is None:
        audit_repo.write_audit(
            db, action="login_failed", detail={"username": payload.username, "reason": "no_such_account"}
        )
        db.commit()
        raise BusinessRuleError("登录名或密码不正确。", code="LOGIN_FAILED")

    if users_repo.is_locked(user):
        audit_repo.write_audit(
            db, action="login_failed", operator_id=user.id, detail={"reason": "locked"}
        )
        db.commit()
        raise BusinessRuleError("账号已被临时锁定，请稍后再试。", code="ACCOUNT_LOCKED")

    if not user.is_active:
        audit_repo.write_audit(
            db, action="login_failed", operator_id=user.id, detail={"reason": "inactive"}
        )
        db.commit()
        raise BusinessRuleError("账号已停用，请联系系统维护人员。", code="ACCOUNT_INACTIVE")

    if not verify_password(payload.password, user.password_hash):
        users_repo.register_login_failure(db, user)
        audit_repo.write_audit(
            db,
            action="login_failed",
            operator_id=user.id,
            detail={"reason": "bad_password", "failed_count": user.failed_login_count},
        )
        db.commit()
        raise BusinessRuleError("登录名或密码不正确。", code="LOGIN_FAILED")

    users_repo.register_login_success(db, user)
    audit_repo.write_audit(db, action="login", operator_id=user.id)
    token, expires_at = create_session_token(user.id)
    db.commit()
    return LoginOut(token=token, expires_at=expires_at, user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """登出。

    说明：本版本令牌为无状态签名令牌，服务端不维护会话表，
    因此登出以"记录审计 + 前端丢弃令牌"实现；令牌到期后自然失效。
    """
    audit_repo.write_audit(db, action="logout", operator_id=current_user.id)
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """查询当前登录账号（前端用于显示当前医生姓名）。"""
    return UserOut.model_validate(current_user)


@router.get("/assignable-doctors", response_model=list[AssignableDoctorOut])
def assignable_doctors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AssignableDoctorOut]:
    """列出可接管患者的启用医生；只向正式管理员开放。"""
    require_admin(current_user)
    return [AssignableDoctorOut.model_validate(user) for user in users_repo.list_assignable_doctors(db)]
