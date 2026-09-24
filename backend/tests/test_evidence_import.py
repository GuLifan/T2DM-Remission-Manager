"""M6-A 依据材料导入、分块与本地检索测试。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pypdf import PdfWriter
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session

from app.models import Base
from app.models.evidence import Evidence, EvidenceChunk
from app.repository import evidence as evidence_repo
from app.services.evidence_import import (
    EvidenceImportError,
    EvidenceSourceSpec,
    ExtractedUnit,
    chunk_units,
    import_evidence_source,
)


@pytest.fixture(autouse=True)
def clean_evidence_tables(client, db_session):
    """每项测试前后清空依据库，避免共享测试数据库相互影响。"""
    del client  # 触发应用 lifespan，确保 Alembic 已迁移到最新版本
    db_session.execute(delete(EvidenceChunk))
    db_session.execute(delete(Evidence))
    db_session.commit()
    yield
    db_session.execute(delete(EvidenceChunk))
    db_session.execute(delete(Evidence))
    db_session.commit()


def _write_markdown(root: Path, content: str) -> tuple[Path, EvidenceSourceSpec]:
    """生成一份不含真实医学材料的测试 Markdown。"""
    relative = Path("materials/test.md")
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return path, EvidenceSourceSpec(
        source_key="test-markdown",
        title="测试依据",
        source_type="markdown",
        relative_path=relative,
        expected_section_count=2,
    )


def test_migration_creates_evidence_tables_and_fts5(db_session) -> None:
    """当前项目 SQLite 应建立普通表和 trigram 虚拟表。"""
    names = {
        row[0]
        for row in db_session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table', 'trigger') AND name LIKE 'evidence%'"
            )
        )
    }
    assert "evidences" in names
    assert "evidence_chunks" in names
    assert "evidence_chunks_fts" in names
    assert "evidence_chunks_ai" in names
    assert evidence_repo.fts5_index_available(db_session) is True


def test_markdown_import_is_idempotent_and_searches_chinese(db_session, tmp_path: Path) -> None:
    """重复导入不重复，中文长词走 trigram、二字词走 LIKE。"""
    path, source = _write_markdown(
        tmp_path,
        "# 第一章\n糖尿病缓解需要核对停药时间和 HbA1c。\n\n"
        "# 第二章\n这里只保存原始依据，不自动生成临床建议。\n",
    )

    first = import_evidence_source(db_session, source_root=tmp_path, source=source)
    assert first.status == "imported"
    assert first.section_count == 2
    assert first.chunk_count == 2

    second = import_evidence_source(db_session, source_root=tmp_path, source=source)
    assert second.status == "skipped"
    assert db_session.scalar(select(func.count(Evidence.id))) == 1
    assert db_session.scalar(select(func.count(EvidenceChunk.id))) == 2

    mode, total, hits = evidence_repo.search_chunks(db_session, "停药时间")
    assert mode == "fts5_trigram"
    assert total == 1
    assert len(hits) == 1
    assert hits[0].section == "第一章"

    mode, total, hits = evidence_repo.search_chunks(db_session, "缓解")
    assert mode == "like"
    assert total == 1
    assert len(hits) == 1

    mode, total, hits = evidence_repo.search_chunks(db_session, "HbA1c")
    assert mode == "fts5_trigram"
    assert total == 1
    assert len(hits) == 1

    # LIKE 通配符必须按普通字符处理，不能扩大成“匹配全部”。
    mode, total, hits = evidence_repo.search_chunks(db_session, "%_")
    assert mode == "like"
    assert total == 0
    assert hits == []

    # FTS 操作符和引号必须作为普通文本短语处理，不能引发语法错误或扩大结果。
    mode, total, hits = evidence_repo.search_chunks(db_session, '缓解" OR *')
    assert mode == "fts5_trigram"
    assert total == 0
    assert hits == []

    # 文件内容发生变化时替换同一材料，不新增第二份材料。
    old_id = db_session.scalar(select(Evidence.id))
    path.write_text("# 第一章\n更新后的可检索内容。\n# 第二章\n仍然只有两个章节。\n", encoding="utf-8")
    updated = import_evidence_source(db_session, source_root=tmp_path, source=source)
    assert updated.status == "imported"
    assert db_session.scalar(select(Evidence.id)) == old_id
    assert evidence_repo.search_chunks(db_session, "停药时间")[2] == []
    assert len(evidence_repo.search_chunks(db_session, "更新后的")[2]) == 1


def test_import_rejects_hash_change(db_session, tmp_path: Path) -> None:
    """带批准哈希的来源发生变化时必须停止。"""
    path, source = _write_markdown(tmp_path, "# 第一章\n内容甲。\n# 第二章\n内容乙。\n")
    wrong = EvidenceSourceSpec(
        source_key=source.source_key,
        title=source.title,
        source_type=source.source_type,
        relative_path=source.relative_path,
        expected_sha256="0" * 64,
        expected_section_count=2,
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() != wrong.expected_sha256
    with pytest.raises(EvidenceImportError, match="SHA-256"):
        import_evidence_source(db_session, source_root=tmp_path, source=wrong)
    assert db_session.scalar(select(func.count(Evidence.id))) == 0


def test_blank_pdf_is_rejected_without_partial_rows(db_session, tmp_path: Path) -> None:
    """没有文本层的 PDF 不得生成空壳索引。"""
    relative = Path("materials/blank.pdf")
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as handle:
        writer.write(handle)

    source = EvidenceSourceSpec(
        source_key="blank-pdf",
        title="空白 PDF",
        source_type="pdf",
        relative_path=relative,
        expected_page_count=1,
    )
    with pytest.raises(EvidenceImportError, match="没有可提取文本"):
        import_evidence_source(db_session, source_root=tmp_path, source=source)
    assert db_session.scalar(select(func.count(Evidence.id))) == 0
    assert db_session.scalar(select(func.count(EvidenceChunk.id))) == 0


def test_failed_reimport_preserves_previous_index(db_session, tmp_path: Path) -> None:
    """新材料抽取失败时，上一版有效索引保持不变。"""
    path, source = _write_markdown(tmp_path, "# 第一章\n原有内容。\n# 第二章\n原有第二部分。\n")
    import_evidence_source(db_session, source_root=tmp_path, source=source)
    before = db_session.scalar(select(Evidence))
    assert before is not None
    before_hash = before.sha256
    before_chunks = evidence_repo.count_chunks(db_session, before.id)

    path.write_text("这次文件没有一级标题。", encoding="utf-8")
    with pytest.raises(EvidenceImportError, match="未找到可导入"):
        import_evidence_source(db_session, source_root=tmp_path, source=source)

    db_session.expire_all()
    after = db_session.scalar(select(Evidence))
    assert after is not None
    assert after.sha256 == before_hash
    assert evidence_repo.count_chunks(db_session, after.id) == before_chunks
    assert len(evidence_repo.search_chunks(db_session, "原有内容")[2]) == 1


def test_chunking_never_crosses_page_or_section() -> None:
    """即使单元很长，分块也只能在同一页或同一章节内重叠。"""
    units = [
        ExtractedUnit(text="甲" * 2_500, page_no=1),
        ExtractedUnit(text="乙" * 2_500, page_no=2),
        ExtractedUnit(text="章节内容" * 500, section="第三章"),
    ]
    chunks = chunk_units(units)
    assert len(chunks) > 3
    assert all(chunk.page_no in {1, 2, None} for chunk in chunks)
    assert all(not (chunk.page_no is not None and chunk.section is not None) for chunk in chunks)
    assert all(set(chunk.content) <= {"甲"} for chunk in chunks if chunk.page_no == 1)
    assert all(set(chunk.content) <= {"乙"} for chunk in chunks if chunk.page_no == 2)
    assert all(chunk.section == "第三章" for chunk in chunks if chunk.section is not None)


def test_source_path_cannot_escape_root(db_session, tmp_path: Path) -> None:
    """即使调用者传入相对路径，也不能读取指定 _DEV 目录之外的文件。"""
    outside = tmp_path.parent / "outside-evidence.md"
    outside.write_text("# 第一章\n测试。", encoding="utf-8")
    source = EvidenceSourceSpec(
        source_key="outside",
        title="越界材料",
        source_type="markdown",
        relative_path=Path("../outside-evidence.md"),
    )
    try:
        with pytest.raises(EvidenceImportError, match="越出指定目录"):
            import_evidence_source(db_session, source_root=tmp_path, source=source)
    finally:
        outside.unlink(missing_ok=True)


def test_search_falls_back_when_fts_table_is_unavailable() -> None:
    """精简 SQLite 没有 FTS 虚拟表时，普通表仍可用 LIKE 检索。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        evidence_repo.replace_evidence(
            db,
            source_key="fallback",
            title="降级测试依据",
            source_type="markdown",
            file_name="fallback.md",
            sha256="f" * 64,
            page_count=None,
            text_page_count=None,
            chunks=[
                evidence_repo.EvidenceChunkInput(
                    ordinal=1,
                    page_no=None,
                    section="第一章",
                    content="糖尿病缓解与停药时间",
                    search_text="糖尿病缓解与停药时间",
                    char_count=len("糖尿病缓解与停药时间"),
                )
            ],
        )
        db.commit()
        assert evidence_repo.fts5_index_available(db) is False
        mode, total, hits = evidence_repo.search_chunks(db, "停药时间")
        assert mode == "like"
        assert total == 1
        assert len(hits) == 1
