"""
模块名称：dependencies.py
所属层级：接口层（api）
功能说明：FastAPI 依赖——从请求头解析会话令牌并返回当前账号。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError
from app.core.security import verify_session_token
from app.models.user import User
from app.repository import users as users_repo
from app.repository.database import get_db


def get_current_user(
    authorization: str | None = Header(default=None, description="Bearer <会话令牌>"),
    db: Session = Depends(get_db),
) -> User:
    """解析并校验会话令牌，返回当前登录账号。

    失败时统一返回 401 与自然语言提示（不泄漏"用户不存在/令牌格式错误"等内部差异）。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("请先登录后再操作。")
    token = authorization.split(" ", 1)[1].strip()
    user_id = verify_session_token(token)
    if user_id is None:
        raise AuthError("登录状态已失效，请重新登录。")
    user = users_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthError("账号不可用，请联系系统维护人员。")
    return user
