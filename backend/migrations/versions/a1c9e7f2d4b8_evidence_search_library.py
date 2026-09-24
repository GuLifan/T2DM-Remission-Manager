"""evidence search library

迁移编号：a1c9e7f2d4b8
修订内容：建立依据材料、原文分块与可选 FTS5 trigram 索引
生成时间：2026-09-24
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "a1c9e7f2d4b8"
down_revision: str | None = "6b7e2d4f9c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)


def _create_fts5_if_supported() -> None:
    """在当前 SQLite 支持 FTS5 trigram 时建立外部内容索引。

    FTS5 是性能优化而不是数据可用性的前提。如果部署环境不支持，普通表仍然
    完整保留，查询服务会按已批准方案退化到参数化 LIKE。
    """
    if context.is_offline_mode():
        # 离线 SQL 无法探测目标 SQLite 编译选项，不输出不可移植的虚拟表 DDL。
        return
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    try:
        enabled = bind.execute(sa.text("SELECT sqlite_compileoption_used('ENABLE_FTS5')")).scalar_one()
        if not enabled:
            logger.warning("当前 SQLite 未启用 FTS5，依据检索将使用 LIKE 降级模式。")
            return
        bind.exec_driver_sql(
            "CREATE VIRTUAL TABLE evidence_chunks_fts USING fts5("
            "search_text, content='evidence_chunks', content_rowid='id', tokenize='trigram'"
            ")"
        )
        bind.exec_driver_sql(
            "CREATE TRIGGER evidence_chunks_ai AFTER INSERT ON evidence_chunks BEGIN "
            "INSERT INTO evidence_chunks_fts(rowid, search_text) VALUES (new.id, new.search_text); END"
        )
        bind.exec_driver_sql(
            "CREATE TRIGGER evidence_chunks_ad AFTER DELETE ON evidence_chunks BEGIN "
            "INSERT INTO evidence_chunks_fts(evidence_chunks_fts, rowid, search_text) "
            "VALUES ('delete', old.id, old.search_text); END"
        )
        bind.exec_driver_sql(
            "CREATE TRIGGER evidence_chunks_au AFTER UPDATE ON evidence_chunks BEGIN "
            "INSERT INTO evidence_chunks_fts(evidence_chunks_fts, rowid, search_text) "
            "VALUES ('delete', old.id, old.search_text); "
            "INSERT INTO evidence_chunks_fts(rowid, search_text) VALUES (new.id, new.search_text); END"
        )
    except sa.exc.DatabaseError as exc:
        # trigram 可能在少数精简 SQLite 中缺失；保留普通表并允许应用层降级。
        # 若失败发生在虚拟表创建之后，必须清掉半成品，避免应用误判索引可用。
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_au")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_ad")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_ai")
        bind.exec_driver_sql("DROP TABLE IF EXISTS evidence_chunks_fts")
        logger.warning("无法建立 FTS5 trigram 索引，将使用 LIKE 降级模式：%s", exc)


def upgrade() -> None:
    """建立可追溯的依据材料与原文分块结构。"""
    op.create_table(
        "evidences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("text_page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_type IN ('pdf', 'markdown')", name="ck_evidences_source_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index("ix_evidences_source_key", "evidences", ["source_key"], unique=True)

    op.create_table(
        "evidence_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", "ordinal", name="uq_evidence_chunks_evidence_ordinal"),
    )
    op.create_index("ix_evidence_chunks_evidence_id", "evidence_chunks", ["evidence_id"], unique=False)
    _create_fts5_if_supported()


def downgrade() -> None:
    """移除依据检索结构；不触碰患者、事件与审计数据。"""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_au")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_ad")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS evidence_chunks_ai")
        bind.exec_driver_sql("DROP TABLE IF EXISTS evidence_chunks_fts")
    op.drop_index("ix_evidence_chunks_evidence_id", table_name="evidence_chunks")
    op.drop_table("evidence_chunks")
    op.drop_index("ix_evidences_source_key", table_name="evidences")
    op.drop_table("evidences")
