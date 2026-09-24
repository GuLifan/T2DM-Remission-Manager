"""
模块名称：evidence.py
所属层级：接口层（api）
功能说明：输出本地依据库状态并提供仅限查阅原文的全文检索接口。

临床与隐私边界：
    - 所有接口均要求登录，但依据是全局资料，不受患者责任归属限制。
    - 结果只返回原文片段和出处，不生成诊疗建议。
    - 检索审计不保存原始查询词、命中正文或本机路径。

修改历史：
    - 2026-09-24  v1.0  M6-B 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import BusinessRuleError
from app.models.schemas import (
    EvidenceMaterialStatusOut,
    EvidenceSearchItemOut,
    EvidenceSearchOut,
    EvidenceStatusOut,
)
from app.models.user import User
from app.repository import evidence as evidence_repo
from app.repository.audit import write_audit
from app.repository.database import get_db
from app.services.evidence_import import DEFAULT_EVIDENCE_SOURCES

router = APIRouter(prefix="/evidence", tags=["医学依据"])


def _status(db: Session) -> EvidenceStatusOut:
    """按已批准的稳定来源清单计算依据库完整状态。"""
    imported = {item.source_key: item for item in evidence_repo.list_evidences(db)}
    materials: list[EvidenceMaterialStatusOut] = []
    for source in DEFAULT_EVIDENCE_SOURCES:
        item = imported.get(source.source_key)
        actual_chunks = evidence_repo.count_chunks(db, item.id) if item is not None else 0
        ready = bool(
            item is not None
            and item.title == source.title
            and item.source_type == source.source_type
            and item.file_name == source.relative_path.name
            and item.sha256.lower() == (source.expected_sha256 or item.sha256).lower()
            and item.chunk_count > 0
            and actual_chunks == item.chunk_count
            and (
                source.expected_page_count is None
                or (
                    item.page_count == source.expected_page_count
                    and item.text_page_count == source.expected_page_count
                )
            )
        )
        materials.append(
            EvidenceMaterialStatusOut(
                source_key=source.source_key,
                title=source.title,
                source_type=source.source_type,
                ready=ready,
                page_count=item.page_count if item is not None else None,
                text_page_count=item.text_page_count if item is not None else None,
                chunk_count=actual_chunks,
                imported_at=item.imported_at if item is not None else None,
            )
        )
    ready_materials = [item for item in materials if item.ready]
    imported_times = [item.imported_at for item in ready_materials if item.imported_at is not None]
    return EvidenceStatusOut(
        expected_count=len(DEFAULT_EVIDENCE_SOURCES),
        indexed_count=len(ready_materials),
        searchable=len(ready_materials) == len(DEFAULT_EVIDENCE_SOURCES),
        last_imported_at=max(imported_times) if imported_times else None,
        materials=materials,
    )


def _snippet(text: str, query: str, *, max_chars: int = 320) -> str:
    """从纯文本中截取含命中词的短片段，不生成 HTML 标记。"""
    if len(text) <= max_chars:
        return text
    index = text.casefold().find(query.casefold())
    if index < 0:
        index = 0
    start = max(0, index - 100)
    end = min(len(text), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)
    return f"{'…' if start else ''}{text[start:end]}{'…' if end < len(text) else ''}"


@router.get("/status", response_model=EvidenceStatusOut)
def evidence_status(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceStatusOut:
    """返回四份预期材料是否完整就绪。"""
    return _status(db)


@router.get("/search", response_model=EvidenceSearchOut)
def search_evidence(
    q: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidenceSearchOut:
    """检索本地依据原文，并写入不含查询内容的审计。"""
    query = " ".join(q.strip().split())
    if len(query) < 2:
        raise BusinessRuleError("请输入至少 2 个字符后再检索医学依据。", "EVIDENCE_QUERY_TOO_SHORT")
    if len(query) > 100:
        raise BusinessRuleError("检索词不能超过 100 个字符。", "EVIDENCE_QUERY_TOO_LONG")
    if limit < 1 or limit > 50:
        raise BusinessRuleError("每次返回数量必须在 1 到 50 之间。", "EVIDENCE_LIMIT_INVALID")

    status = _status(db)
    if not status.searchable:
        raise BusinessRuleError(
            "医学依据尚未完整导入，请联系系统维护人员完成本地导入。",
            "EVIDENCE_NOT_READY",
        )

    search_mode, total, rows = evidence_repo.search_chunks(db, query, limit=limit)
    items = [
        EvidenceSearchItemOut(
            evidence_id=row.evidence_id,
            source_key=row.source_key,
            title=row.title,
            source_type=row.source_type,
            page_no=row.page_no,
            section=row.section,
            snippet=_snippet(row.search_text, query),
        )
        for row in rows
    ]
    write_audit(
        db,
        action="evidence_search",
        operator_id=current_user.id,
        target_type="evidence_library",
        detail={
            "query_chars": len(query),
            "search_mode": search_mode,
            "result_count": total,
            "returned_count": len(items),
        },
    )
    db.commit()
    return EvidenceSearchOut(
        query=query,
        search_mode=search_mode,
        materials_indexed=status.indexed_count,
        total=total,
        returned=len(items),
        items=items,
    )
