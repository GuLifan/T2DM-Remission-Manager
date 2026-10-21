"""demo 持久化模型：邀请只存摘要、会话退出可撤销，不保存明文凭据。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DemoInvite(Base):
    """一次性邀请，原子消费确保并发注册最多成功一次。"""

    __tablename__ = "demo_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DemoSession(Base):
    """会话令牌摘要与到期时间；退出删除本条，签名有效也不能继续访问。"""

    __tablename__ = "demo_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column(Integer)
