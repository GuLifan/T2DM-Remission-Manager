"""
模块名称：evidence.py
所属层级：数据访问层（repository）
功能说明：依据材料与原文分块的数据访问，以及 FTS5/LIKE 双路径检索。

事务约定：除只读查询外，本模块只 add/delete/flush，不 commit；调用者负责事务。

修改历史：
    - 2026-09-24  v1.0  M6-A 初始实现
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.models.evidence import Evidence, EvidenceChunk


@dataclass(frozen=True)
class EvidenceChunkInput:
    """准备写入数据库的依据分块。"""

    ordinal: int
    page_no: int | None
    section: str | None
    content: str
    search_text: str
    char_count: int


@dataclass(frozen=True)
class EvidenceSearchRow:
    """仓储层检索结果；接口层后续据此生成纯文本响应。"""

    chunk_id: int
    evidence_id: int
    source_key: str
    title: str
    source_type: str
    page_no: int | None
    section: str | None
    content: str


def get_by_source_key(db: Session, source_key: str) -> Evidence | None:
    """按稳定材料键查询。"""
    return db.scalar(select(Evidence).where(Evidence.source_key == source_key))


def count_chunks(db: Session, evidence_id: int) -> int:
    """返回某份材料当前的实际分块数。"""
    return int(
        db.scalar(
            select(func.count(EvidenceChunk.id)).where(EvidenceChunk.evidence_id == evidence_id)
        )
        or 0
    )


def replace_evidence(
    db: Session,
    *,
    source_key: str,
    title: str,
    source_type: str,
    file_name: str,
    sha256: str,
    page_count: int | None,
    text_page_count: int | None,
    chunks: Iterable[EvidenceChunkInput],
) -> Evidence:
    """在当前事务中原子替换一份材料及其全部分块。"""
    chunk_list = list(chunks)
    evidence = get_by_source_key(db, source_key)
    if evidence is None:
        evidence = Evidence(
            source_key=source_key,
            title=title,
            source_type=source_type,
            file_name=file_name,
            sha256=sha256,
            page_count=page_count,
            text_page_count=text_page_count,
            chunk_count=len(chunk_list),
            imported_at=datetime.now(),
        )
        db.add(evidence)
        db.flush()
    else:
        # 普通 DELETE 会逐行触发 SQLite FTS 同步触发器；事务失败时旧分块自动恢复。
        db.execute(delete(EvidenceChunk).where(EvidenceChunk.evidence_id == evidence.id))
        db.flush()

    evidence.title = title
    evidence.source_type = source_type
    evidence.file_name = file_name
    evidence.sha256 = sha256
    evidence.page_count = page_count
    evidence.text_page_count = text_page_count
    evidence.chunk_count = len(chunk_list)
    evidence.imported_at = datetime.now()

    db.add_all(
        [
            EvidenceChunk(
                evidence_id=evidence.id,
                ordinal=item.ordinal,
                page_no=item.page_no,
                section=item.section,
                content=item.content,
                search_text=item.search_text,
                char_count=item.char_count,
            )
            for item in chunk_list
        ]
    )
    db.flush()
    return evidence


def fts5_index_available(db: Session) -> bool:
    """判断迁移是否成功建立 FTS5 虚拟表。"""
    if db.bind is None or db.bind.dialect.name != "sqlite":
        return False
    row = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'evidence_chunks_fts'")
    ).first()
    return row is not None


def _fts_phrase(query: str) -> str:
    """把用户输入变为单个 FTS 短语，禁止其被解释为操作符。"""
    return f'"{query.replace(chr(34), chr(34) * 2)}"'


def _escape_like(query: str) -> str:
    """转义 LIKE 通配符与转义符本身。"""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_chunks(db: Session, query: str, *, limit: int = 20) -> tuple[str, list[EvidenceSearchRow]]:
    """检索原文分块；返回实际模式和稳定排序的结果。"""
    normalized = " ".join(query.strip().split())
    if not normalized:
        return "like", []
    safe_limit = max(1, min(limit, 50))
    if len(normalized) >= 3 and fts5_index_available(db):
        rows = db.execute(
            text(
                "SELECT ec.id AS chunk_id, e.id AS evidence_id, e.source_key, e.title, "
                "e.source_type, ec.page_no, ec.section, ec.content "
                "FROM evidence_chunks_fts "
                "JOIN evidence_chunks ec ON ec.id = evidence_chunks_fts.rowid "
                "JOIN evidences e ON e.id = ec.evidence_id "
                "WHERE evidence_chunks_fts MATCH :query "
                "ORDER BY bm25(evidence_chunks_fts), e.source_key, "
                "COALESCE(ec.page_no, 0), ec.ordinal LIMIT :limit"
            ),
            {"query": _fts_phrase(normalized), "limit": safe_limit},
        ).mappings()
        return "fts5_trigram", [EvidenceSearchRow(**row) for row in rows]

    pattern = f"%{_escape_like(normalized)}%"
    rows = db.execute(
        text(
            "SELECT ec.id AS chunk_id, e.id AS evidence_id, e.source_key, e.title, "
            "e.source_type, ec.page_no, ec.section, ec.content "
            "FROM evidence_chunks ec JOIN evidences e ON e.id = ec.evidence_id "
            "WHERE ec.search_text LIKE :pattern ESCAPE '\\' "
            "ORDER BY e.source_key, COALESCE(ec.page_no, 0), ec.ordinal LIMIT :limit"
        ),
        {"pattern": pattern, "limit": safe_limit},
    ).mappings()
    return "like", [EvidenceSearchRow(**row) for row in rows]
