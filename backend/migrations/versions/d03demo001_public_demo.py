"""Public demo invitations, sessions and archived test rounds."""

import sqlalchemy as sa
from alembic import op

revision = "d03demo001"
down_revision = "b2d03f7a610c"
branch_labels = None
depends_on = None


def upgrade():
    # 仅新增字段，不覆盖历史事件；重置靠归档和新病例实现。
    op.add_column("patients", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("patients", sa.Column("demo_case", sa.Integer(), nullable=True))
    op.create_table(
        "demo_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digest", sa.String(64), unique=True, nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_table(
        "demo_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_demo_sessions_user_id", "demo_sessions", ["user_id"])


def downgrade():
    # demo 交付不提供自动回滚，避免删除可追溯测试记录。
    raise RuntimeError("请从一致性备份恢复，禁止破坏性降级。")
