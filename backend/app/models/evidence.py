"""
模块名称：evidence.py
所属层级：数据模型层（models）
功能说明：医学依据材料及其可检索文本分块。

设计边界：
    - 只保存原始材料的可复核片段，不生成临床建议。
    - PDF 分块不跨页，Markdown 分块不跨一级章节。
    - 原始文件绝对路径不入库，避免泄露本机目录结构。

修改历史：
    - 2026-09-24  v1.0  M6-A 初始实现
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Evidence(Base):
    """一份可检索依据材料的元数据。"""

    __tablename__ = "evidences"
    __table_args__ = (
        CheckConstraint("source_type IN ('pdf', 'markdown')", name="ck_evidences_source_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 稳定键不依赖本机文件名，材料文件改名后仍可识别为同一来源。
    source_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(16))
    # 只记录文件名，不记录绝对路径。
    file_name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    chunks: Mapped[list[EvidenceChunk]] = relationship(
        back_populates="evidence",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvidenceChunk(Base):
    """依据材料中的一个原文分块。"""

    __tablename__ = "evidence_chunks"
    __table_args__ = (
        UniqueConstraint("evidence_id", "ordinal", name="uq_evidence_chunks_evidence_ordinal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidences.id", ondelete="CASCADE"),
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    # PDF 页码从 1 开始；Markdown 依据使用 section，page_no 为空。
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    # search_text 仅做空白规范化，不翻译、不总结、不改变医学语义。
    search_text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)

    evidence: Mapped[Evidence] = relationship(back_populates="chunks")
