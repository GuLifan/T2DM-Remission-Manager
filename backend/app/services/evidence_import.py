"""
模块名称：evidence_import.py
所属层级：服务层（services）
功能说明：校验、抽取、分块并原子导入本地医学依据。

临床安全边界：
    - 不翻译、不总结、不生成建议，只保存可回到原材料核对的原文片段。
    - 默认来源带文件哈希与页数基线；基线变化时停止，不自行接受新材料。
    - 单份材料在抽取全部成功后才替换旧索引，失败不会留下半份数据。

修改历史：
    - 2026-09-24  v1.0  M6-A 初始实现
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.repository import evidence as evidence_repo

logger = logging.getLogger(__name__)

CHUNK_TARGET = 1_000
CHUNK_OVERLAP = 120
_CJK_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_BREAK_CHARS = "。！？；.!?;\n"


class EvidenceImportError(RuntimeError):
    """依据材料缺失、不一致或无法完整抽取。"""


@dataclass(frozen=True)
class EvidenceSourceSpec:
    """一份预期来源的稳定清单。"""

    source_key: str
    title: str
    source_type: str
    relative_path: Path
    expected_sha256: str | None = None
    expected_page_count: int | None = None
    expected_section_count: int | None = None


@dataclass(frozen=True)
class ExtractedUnit:
    """不能跨越的原文定位单元：一页 PDF 或一个 Markdown 一级章节。"""

    text: str
    page_no: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class ImportResult:
    """单份材料的导入结果。"""

    source_key: str
    title: str
    status: str
    page_count: int | None
    text_page_count: int | None
    section_count: int | None
    char_count: int | None
    chunk_count: int
    warnings: tuple[str, ...]


DEFAULT_EVIDENCE_SOURCES: tuple[EvidenceSourceSpec, ...] = (
    EvidenceSourceSpec(
        source_key="china-remission-consensus-2021",
        title="2 型糖尿病缓解中国专家共识（2021）",
        source_type="pdf",
        relative_path=Path("医学依据/2型糖尿病缓解中国专家共识-2021.pdf"),
        expected_sha256="394b6706152f91b98ee0cea57b70665c0fc3ab903e59f42cb3f9e506b13c1586",
        expected_page_count=13,
    ),
    EvidenceSourceSpec(
        source_key="china-diabetes-guideline-2024",
        title="中国糖尿病防治指南（2024 版）",
        source_type="pdf",
        relative_path=Path("医学依据/中国糖尿病防治指南（2024版）.pdf"),
        expected_sha256="4884c911879af5aa55a5f5cbd825fdedec0b168c34fde8781bc39d35b4b00c22",
        expected_page_count=124,
    ),
    EvidenceSourceSpec(
        source_key="expert-remission-consensus-2026",
        title="Expert Consensus on Type 2 Diabetes Remission（2026）",
        source_type="pdf",
        relative_path=Path("医学依据/Expert Consensus on Type 2 Diabetes Remission(1).pdf"),
        expected_sha256="c57447caa33fe9d56ff499d3b6e90b1fd81ff2df20ca7e08203fa07bd2f25111",
        expected_page_count=15,
    ),
    EvidenceSourceSpec(
        source_key="clinical-flow-locked-v1",
        title="临床流程锁定稿 v1.0",
        source_type="markdown",
        relative_path=Path("甲方材料/md派生/临床流程锁定稿_v1.0_20260806.md"),
        expected_sha256="6506626276537fb3294b3e2484a7dd974a9bd9243b1d37489ca227f4179f8ce1",
        expected_section_count=15,
    ),
)


class _WarningCollector(logging.Handler):
    """收集 pypdf 的非阻断结构警告，供导入报告展示。"""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _sha256(path: Path) -> str:
    """流式计算材料哈希，避免把大文件一次性读入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_source_path(source_root: Path, relative_path: Path) -> Path:
    """解析并约束来源路径必须位于显式指定的 _DEV 根目录内。"""
    root = source_root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise EvidenceImportError(f"依据来源路径越出指定目录：{relative_path}")
    if not path.is_file():
        raise EvidenceImportError(f"缺少依据材料：{relative_path}")
    return path


def normalize_display_text(text: str) -> str:
    """只规范空白，保留原始段落和医学措辞。"""
    clean = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in clean.split("\n")]
    output: list[str] = []
    blank = False
    for line in lines:
        if line:
            output.append(line)
            blank = False
        elif output and not blank:
            output.append("")
            blank = True
    return "\n".join(output).strip()


def normalize_search_text(text: str) -> str:
    """生成检索文本；只移除汉字之间的版式空白，不改变字词。"""
    normalized = normalize_display_text(text)
    normalized = re.sub(fr"(?<=[{_CJK_RANGE}])\s+(?=[{_CJK_RANGE}])", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_pdf(path: Path) -> tuple[list[ExtractedUnit], tuple[str, ...]]:
    """逐页抽取 PDF；任一空文本页都视为整份材料失败。"""
    collector = _WarningCollector()
    pypdf_logger = logging.getLogger("pypdf")
    pypdf_logger.addHandler(collector)
    try:
        reader = PdfReader(path)
        units: list[ExtractedUnit] = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = normalize_display_text(page.extract_text() or "")
            if not text:
                raise EvidenceImportError(f"{path.name} 的 PDF 第 {page_no} 页没有可提取文本。")
            units.append(ExtractedUnit(text=text, page_no=page_no))
        return units, tuple(dict.fromkeys(collector.messages))
    except EvidenceImportError:
        raise
    except Exception as exc:
        raise EvidenceImportError(f"无法解析 PDF {path.name}：{exc}") from exc
    finally:
        pypdf_logger.removeHandler(collector)


def _extract_markdown(path: Path) -> list[ExtractedUnit]:
    """按一级标题拆分锁定稿，不跨章节建块。"""
    text = path.read_text(encoding="utf-8")
    units: list[ExtractedUnit] = []
    title: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            if title is not None:
                content = normalize_display_text("\n".join([title, *body]))
                if content:
                    units.append(ExtractedUnit(text=content, section=title))
            title = match.group(1).strip()
            body = []
        elif title is not None:
            body.append(line)
    if title is not None:
        content = normalize_display_text("\n".join([title, *body]))
        if content:
            units.append(ExtractedUnit(text=content, section=title))
    if not units:
        raise EvidenceImportError(f"{path.name} 未找到可导入的 Markdown 一级章节。")
    return units


def _choose_chunk_end(text: str, start: int, hard_end: int) -> int:
    """优先在目标范围末端的自然标点处分块。"""
    if hard_end >= len(text):
        return len(text)
    lower_bound = start + int(CHUNK_TARGET * 0.65)
    for index in range(hard_end - 1, lower_bound - 1, -1):
        if text[index] in _BREAK_CHARS:
            return index + 1
    return hard_end


def chunk_units(units: list[ExtractedUnit]) -> list[evidence_repo.EvidenceChunkInput]:
    """在页/章边界内分块，并保留少量上下文重叠。"""
    chunks: list[evidence_repo.EvidenceChunkInput] = []
    ordinal = 1
    for unit in units:
        start = 0
        while start < len(unit.text):
            hard_end = min(start + CHUNK_TARGET, len(unit.text))
            end = _choose_chunk_end(unit.text, start, hard_end)
            content = unit.text[start:end].strip()
            if content:
                search_text = normalize_search_text(content)
                chunks.append(
                    evidence_repo.EvidenceChunkInput(
                        ordinal=ordinal,
                        page_no=unit.page_no,
                        section=unit.section,
                        content=content,
                        search_text=search_text,
                        char_count=len(content),
                    )
                )
                ordinal += 1
            if end >= len(unit.text):
                break
            start = max(start + 1, end - CHUNK_OVERLAP)
    if not chunks:
        raise EvidenceImportError("材料没有生成任何可检索分块。")
    return chunks


def import_evidence_source(
    db: Session,
    *,
    source_root: Path,
    source: EvidenceSourceSpec,
) -> ImportResult:
    """校验并原子导入一份材料；本函数负责提交或回滚该材料事务。"""
    path = _resolve_source_path(source_root, source.relative_path)
    digest = _sha256(path)
    if source.expected_sha256 and digest.lower() != source.expected_sha256.lower():
        raise EvidenceImportError(
            f"{path.name} 的 SHA-256 与已批准基线不一致，请停止并重新核对材料。"
        )

    existing = evidence_repo.get_by_source_key(db, source.source_key)
    if (
        existing is not None
        and existing.sha256 == digest
        and existing.chunk_count > 0
        and evidence_repo.count_chunks(db, existing.id) == existing.chunk_count
    ):
        return ImportResult(
            source_key=source.source_key,
            title=source.title,
            status="skipped",
            page_count=existing.page_count,
            text_page_count=existing.text_page_count,
            section_count=None if source.source_type == "pdf" else source.expected_section_count,
            # 数据表只保存分块字符数；分块存在重叠，不能伪装成原文净字符数。
            char_count=None,
            chunk_count=existing.chunk_count,
            warnings=(),
        )

    try:
        warnings: tuple[str, ...] = ()
        if source.source_type == "pdf":
            units, warnings = _extract_pdf(path)
            page_count = len(units)
            text_page_count = len(units)
            section_count = None
            if source.expected_page_count is not None and page_count != source.expected_page_count:
                raise EvidenceImportError(
                    f"{path.name} 页数为 {page_count}，与已批准基线 {source.expected_page_count} 不一致。"
                )
        elif source.source_type == "markdown":
            units = _extract_markdown(path)
            page_count = None
            text_page_count = None
            section_count = len(units)
            if source.expected_section_count is not None and section_count != source.expected_section_count:
                raise EvidenceImportError(
                    f"{path.name} 一级章节数为 {section_count}，"
                    f"与已批准基线 {source.expected_section_count} 不一致。"
                )
        else:
            raise EvidenceImportError(f"不支持的依据来源类型：{source.source_type}")

        chunks = chunk_units(units)
        evidence_repo.replace_evidence(
            db,
            source_key=source.source_key,
            title=source.title,
            source_type=source.source_type,
            file_name=path.name,
            sha256=digest,
            page_count=page_count,
            text_page_count=text_page_count,
            chunks=chunks,
        )
        db.commit()
        return ImportResult(
            source_key=source.source_key,
            title=source.title,
            status="imported",
            page_count=page_count,
            text_page_count=text_page_count,
            section_count=section_count,
            char_count=sum(len(unit.text) for unit in units),
            chunk_count=len(chunks),
            warnings=warnings,
        )
    except Exception:
        db.rollback()
        raise
