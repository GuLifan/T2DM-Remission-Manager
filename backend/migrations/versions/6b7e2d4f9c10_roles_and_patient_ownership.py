"""roles and patient ownership

迁移编号：6b7e2d4f9c10
修订内容：正式启用管理员角色，并增加患者当前责任归属
生成时间：2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b7e2d4f9c10"
down_revision: str | None = "4f8e1c2d9a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立正式角色与责任归属，并对旧库做确定性安全回填。"""
    # 只有在旧库完全没有管理员时才提升一个账号；已停用账号和系统账号绝不获得权限。
    op.execute(
        sa.text(
            "UPDATE users SET role = 'admin' "
            "WHERE id = ("
            "SELECT id FROM users "
            "WHERE is_active = 1 AND username != '__system__' "
            "ORDER BY created_at ASC, id ASC LIMIT 1"
            ") AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin')"
        )
    )

    # SQLite 用 batch 重建表以可靠增加外键与索引。
    with op.batch_alter_table("patients") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_patients_owner_id_users", "users", ["owner_id"], ["id"])
        batch_op.create_index("ix_patients_owner_id", ["owner_id"], unique=False)

    # 原始创建者与当前责任人首次一致；少数旧数据若没有创建者，则归给正式管理员。
    op.execute(sa.text("UPDATE patients SET owner_id = created_by WHERE created_by IS NOT NULL"))
    op.execute(
        sa.text(
            "UPDATE patients SET owner_id = ("
            "SELECT id FROM users WHERE role = 'admin' AND is_active = 1 ORDER BY id LIMIT 1"
            ") WHERE owner_id IS NULL"
        )
    )


def downgrade() -> None:
    """移除当前责任归属；既有角色数据保留，避免误降级人工设置的管理员。"""
    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_index("ix_patients_owner_id")
        batch_op.drop_constraint("fk_patients_owner_id_users", type_="foreignkey")
        batch_op.drop_column("owner_id")
