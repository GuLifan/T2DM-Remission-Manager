"""
模块名称：users.py
所属层级：数据访问层（repository）
功能说明：账号相关的数据访问与基础防护（失败计数、短时锁定、保留的系统账号）。

事务约定：本模块只 add/flush，**不 commit**——一次请求的提交由接口层统一完成，
以保证"业务数据 + 事件流水 + 审计日志"要么全部写入、要么全部不写入。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User

# 连续失败多少次后锁定，以及锁定时长（分钟）
LOCK_THRESHOLD = 5
LOCK_MINUTES = 15
# 系统保留账号的登录名（自动事件的操作者；不用于登录）
SYSTEM_USERNAME = "__system__"


def count_users(db: Session) -> int:
    """统计账号总数（判定是否需要首次引导创建账号）。"""
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def get_by_username(db: Session, username: str) -> User | None:
    """按登录名查询账号。"""
    return db.scalar(select(User).where(User.username == username))


def get_by_id(db: Session, user_id: int) -> User | None:
    """按主键查询账号。"""
    return db.get(User, user_id)


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    department: str | None = None,
    role: str = "doctor",
    is_active: bool = True,
) -> User:
    """创建账号（密码在写入前完成哈希）。

    参数:
        db (Session): 数据库会话。
        username (str): 登录名。
        display_name (str): 界面显示姓名（会记入事件流水的操作者）。
        password (str): 明文密码，仅在此处使用，不落盘。
        department (str | None): 所属科室，注册时可不填。
        role (str): 角色，本版本为 doctor。
        is_active (bool): 是否可登录。
    """
    user = User(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        department=department,
        role=role,
        is_active=is_active,
        failed_login_count=0,
        locked_until=None,
    )
    db.add(user)
    db.flush()
    return user


def system_user(db: Session) -> User:
    """获取（或首次创建）系统保留账号。

    为什么需要：系统自动事件（例如停用最后一种降糖药后自动进入观察期）
    同样必须记录操作者。系统账号不可登录（is_active=False，且密码哈希为占位值）。
    """
    existing = get_by_username(db, SYSTEM_USERNAME)
    if existing is not None:
        return existing
    user = User(
        username=SYSTEM_USERNAME,
        display_name="系统自动",
        # 占位哈希：无法通过任何密码校验（verify_password 会因格式不识别返回 False）
        password_hash="!disabled",
        role="system",
        is_active=False,
        failed_login_count=0,
        locked_until=None,
    )
    db.add(user)
    db.flush()
    return user


def is_locked(user: User, now: datetime | None = None) -> bool:
    """判断账号当前是否处于锁定状态。"""
    if user.locked_until is None:
        return False
    return user.locked_until > (now or datetime.now())


def register_login_success(db: Session, user: User) -> None:
    """登录成功后：清零失败计数、记录最近登录时间。"""
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now()
    db.flush()


def register_login_failure(db: Session, user: User) -> None:
    """登录失败后：累加失败次数，达到阈值则短期锁定。"""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= LOCK_THRESHOLD:
        # 达到阈值：锁定一段时间，避免被持续猜密码
        user.locked_until = datetime.now() + timedelta(minutes=LOCK_MINUTES)
        user.failed_login_count = 0
    db.flush()


def set_simulated_date(db: Session, user: User, value: date | None) -> None:
    """保存账号级模拟日期；空值表示恢复真实日期。"""
    user.simulated_date = value
    db.flush()
