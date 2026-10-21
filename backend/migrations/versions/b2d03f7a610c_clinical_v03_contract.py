"""临床v0.3契约与历史兼容；不重写旧事件、不推断医学结论。"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d03f7a610c"
down_revision: str | None = "a1c9e7f2d4b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只添加兼容列；未知值保留NULL；旧状态只加工程待核对标签。"""
    columns = [
        sa.Column("clinical_contract_version", sa.String(16), nullable=False, server_default="v1.0"),
        sa.Column("clinical_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("observation_status", sa.String(32), nullable=False, server_default="none"),
        sa.Column("observation_cycle", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applicable_interventions", sa.JSON(), nullable=True),
        sa.Column("actual_stop_confirmed", sa.Boolean(), nullable=True),
        sa.Column("current_remission_evaluation", sa.String(32), nullable=True),
        sa.Column("objective_assessment_event_id", sa.Integer(), nullable=True),
        sa.Column("objective_assessment_revision", sa.Integer(), nullable=True),
        sa.Column("objective_assessment_digest", sa.String(64), nullable=True),
    ]
    for column in columns:
        op.add_column("patients", column)
    op.add_column("events", sa.Column("clinical_contract_version", sa.String(16), nullable=False, server_default="v1.0"))
    op.add_column("events", sa.Column("transition_ids", sa.JSON(), nullable=True))
    # 即使旧ST40有日期，旧契约也没有F057/F063事实，不自动推断新契约合格。
    op.execute(sa.text("UPDATE patients SET observation_status='legacy_pending' WHERE current_state='ST40'"))
    op.execute(sa.text("UPDATE patients SET current_remission_evaluation='待核对' WHERE current_state='ST60'"))


def downgrade() -> None:
    """拒绝丢弃新增临床事实的降级；恢复需明确选择升级前的只读备份。"""
    raise RuntimeError("本迁移包含临床事实和确认快照，不支持破坏性降级；请按备份恢复方案处理。")
