"""
模块名称：user.py
所属层级：数据模型层（models）
功能说明：账号模型。账号用于**可追溯性**（事件绑定操作者），按 `_SPEC/06` V1.0-Q-03
          的定位，本版本不把它当作系统安全边界。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """医生账号。"""

    __tablename__ = "users"

    # 主键
    id: Mapped[int] = mapped_column(primary_key=True)
    # 登录名（唯一）
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 界面显示姓名；事件流水的操作者展示用此字段
    display_name: Mapped[str] = mapped_column(String(64))
    # 密码哈希（scrypt 加盐；禁止明文，禁止可逆加密）
    password_hash: Mapped[str] = mapped_column(String(255))
    # 角色：本版本仅 doctor，预留 admin
    role: Mapped[str] = mapped_column(String(16), default="doctor")
    # 是否启用（停用后不可登录，历史事件保留）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 连续登录失败次数与锁定截止时间：基础防护，避免被反复猜密码
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 创建时间与最近登录时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
