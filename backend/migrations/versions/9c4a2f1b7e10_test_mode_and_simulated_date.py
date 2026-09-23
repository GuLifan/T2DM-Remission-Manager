"""test mode and simulated date

迁移编号：9c4a2f1b7e10
修订内容：增加测试账号、测试患者与模拟日期审计字段
生成时间：2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# 迁移标识
revision: str = "9c4a2f1b7e10"
down_revision: str | None = "375fb4767e0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加第一批测试能力所需字段，并安全回填现有演示数据。"""
    # 测试账号标记默认关闭，避免迁移后普通账号意外获得测试能力
    op.add_column(
        "users",
        sa.Column("is_test_account", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # 模拟日期按账号持久保存；空值表示使用真实日期
    op.add_column("users", sa.Column("simulated_date", sa.Date(), nullable=True))
    # 测试患者标记默认关闭，真实患者不会因迁移自动进入测试范围
    op.add_column(
        "patients",
        sa.Column("is_test_patient", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # 事件保存实际使用的模拟日期；真实日期下保持为空
    op.add_column("events", sa.Column("simulated_date", sa.Date(), nullable=True))

    # 当前开发库中的 admin 是约定测试账号；其他账号保持普通账号
    op.execute(sa.text("UPDATE users SET is_test_account = 1 WHERE username = 'admin'"))
    # 只回填交接手册明确列出的 3 位演示患者，不做模糊匹配
    op.execute(
        sa.text(
            "UPDATE patients SET is_test_patient = 1 "
            "WHERE medical_record_no IN ('MRN-DEMO-001', 'MRN-DEMO-002', 'ZY010000001')"
        )
    )


def downgrade() -> None:
    """移除第一批测试能力字段。"""
    op.drop_column("events", "simulated_date")
    op.drop_column("patients", "is_test_patient")
    op.drop_column("users", "simulated_date")
    op.drop_column("users", "is_test_account")
