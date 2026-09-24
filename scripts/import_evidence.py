"""
脚本名称：import_evidence.py
所属层级：辅助脚本（scripts）
功能说明：把本机 _DEV 中已批准的三份医学 PDF 与临床流程锁定稿导入依据检索库。

用法：
    cd backend
    uv run python ../scripts/import_evidence.py --source-root ../_DEV

修改历史：
    - 2026-09-24  v1.0  M6-A 初始实现
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 脚本位于项目根 scripts/；显式加入 backend，避免要求用户修改全局 PYTHONPATH。
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.repository.database import SessionLocal  # noqa: E402
from app.repository.migrations import run_migrations  # noqa: E402
from app.services.evidence_import import (  # noqa: E402
    DEFAULT_EVIDENCE_SOURCES,
    EvidenceImportError,
    import_evidence_source,
)


def _print_result(result) -> None:
    """输出一份不含正文和绝对路径的导入摘要。"""
    locator = (
        f"页 {result.text_page_count}/{result.page_count}"
        if result.page_count is not None
        else f"章节 {result.section_count}"
    )
    char_summary = f"，字符 {result.char_count}" if result.char_count is not None else ""
    print(f"[{result.status}] {result.title}：{locator}{char_summary}，分块 {result.chunk_count}", flush=True)
    for warning in result.warnings:
        print(f"  [warning] {warning}", flush=True)


def main() -> int:
    """执行迁移后逐份导入；任一失败返回非零退出码。"""
    parser = argparse.ArgumentParser(description="导入 ETMMS 本地医学依据")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "_DEV",
        help="包含 医学依据/ 与 甲方材料/ 的 _DEV 目录",
    )
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    run_migrations()
    failures: list[str] = []
    for source in DEFAULT_EVIDENCE_SOURCES:
        with SessionLocal() as db:
            try:
                _print_result(import_evidence_source(db, source_root=args.source_root, source=source))
            except EvidenceImportError as exc:
                failures.append(f"{source.title}：{exc}")
                print(f"[failed] {source.title}：{exc}", file=sys.stderr, flush=True)
            except Exception as exc:  # 工程异常只给出材料级上下文，避免输出本机绝对路径
                failures.append(f"{source.title}：{type(exc).__name__}")
                print(
                    f"[failed] {source.title}：发生未预期错误（{type(exc).__name__}）",
                    file=sys.stderr,
                    flush=True,
                )
    if failures:
        print(f"导入未完成：{len(failures)} 份材料失败。旧索引未被半覆盖。", file=sys.stderr)
        return 1
    print("依据导入完成：全部预期材料均已校验。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
