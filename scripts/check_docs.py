"""
脚本名称：check_docs.py
所属层级：辅助脚本（scripts）
功能说明：文档与实现的一致性自查，是 V1.0 的合并门禁之一（见 UI.md 第 6 节、_SPEC/07 第十二节）。

检查项：
    1. Token 定义一致：根目录 UI.md 第 2 节列出的 `--etmms-*` 与
       frontend/src/styles/tokens.css 中的定义必须完全一致。
    2. Token 使用率：tokens.css 中每个 Token 必须在前端源码中被引用至少一次；
       未使用的 Token 视为缺陷（V0.1 的教训：定义了整套 Liquid Glass 却零引用）。
    3. 输出模板覆盖：以甲方原件《临床流程实现表_输出模板》为基准，
       其列出的每个模板 ID 都必须登记在 MAPPING.md 中（防止实现漏掉锁定文案）。
       同时核对 SYS 级兜底提示也已登记。
    4. mapping 覆盖进度：统计 MAPPING.md 中仍为"待回填"的实现位置数量。

用法：
    python scripts\\check_docs.py          # 执行检查，1/2/3 项失败时返回非零退出码

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 项目根目录（本脚本位于 <root>/scripts/check_docs.py）
ROOT = Path(__file__).resolve().parent.parent
UI_MD = ROOT / "UI.md"
TOKENS_CSS = ROOT / "frontend" / "src" / "styles" / "tokens.css"
FRONTEND_SRC = ROOT / "frontend" / "src"
SPEC_04 = ROOT / "_SPEC" / "04_字段与输出模板_v1.0.md"
MAPPING = ROOT / "MAPPING.md"
# 甲方输出模板原件（md 派生版）：模板清单的权威基准
EVIDENCE_TEMPLATE_DOC = ROOT / "_DEV" / "甲方材料" / "md派生" / "临床流程实现表_输出模板.md"

# Token 定义与引用的匹配模式
TOKEN_DEFINE = re.compile(r"^\s*(--etmms-[a-z0-9-]+)\s*:", re.MULTILINE)
TOKEN_USAGE = re.compile(r"var\(\s*(--etmms-[a-z0-9-]+)")
# 模板 ID 形如 OUT-E1-ENTER / SYS-E1-CLOSE
TEMPLATE_ID = re.compile(r"\b(?:OUT|SYS)-[A-Z0-9]+(?:-[A-Z0-9]+)+\b")


def tokens_in(path: Path) -> set[str]:
    """读取文件中出现的 Token 定义名。"""
    return set(TOKEN_DEFINE.findall(path.read_text(encoding="utf-8")))


def check_token_definition() -> tuple[bool, str]:
    """检查 1：UI.md 与 tokens.css 的 Token 集合必须一致。"""
    ui_tokens = set(re.findall(r"(--etmms-[a-z0-9-]+)\s*:", UI_MD.read_text(encoding="utf-8")))
    css_tokens = tokens_in(TOKENS_CSS)
    only_in_ui = sorted(ui_tokens - css_tokens)
    only_in_css = sorted(css_tokens - ui_tokens)
    if only_in_ui or only_in_css:
        detail = []
        if only_in_ui:
            detail.append(f"UI.md 有但 tokens.css 缺失：{only_in_ui}")
        if only_in_css:
            detail.append(f"tokens.css 有但 UI.md 未登记：{only_in_css}")
        return False, "；".join(detail)
    return True, f"UI.md 与 tokens.css 的 Token 完全一致（共 {len(css_tokens)} 个）"


def check_token_usage() -> tuple[bool, str]:
    """检查 2：每个 Token 至少被引用一次。"""
    defined = tokens_in(TOKENS_CSS)
    used: set[str] = set()
    for path in FRONTEND_SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".css", ".ts", ".tsx"}:
            continue
        # 跳过 Token 定义文件自身，否则每个 Token 都算"被使用"
        if path.name == "tokens.css":
            continue
        used |= set(TOKEN_USAGE.findall(path.read_text(encoding="utf-8")))
    unused = sorted(defined - used)
    if unused:
        return False, f"存在未被使用的 Token（{len(unused)} 个）：{unused}"
    return True, f"全部 {len(defined)} 个 Token 均已被引用"


def check_template_count() -> tuple[bool, str]:
    """检查 3：以甲方原件为基准核对模板覆盖与计数口径。"""
    canonical_ids = set(TEMPLATE_ID.findall(EVIDENCE_TEMPLATE_DOC.read_text(encoding="utf-8")))
    mapping_ids = set(TEMPLATE_ID.findall(MAPPING.read_text(encoding="utf-8")))
    spec_text = SPEC_04.read_text(encoding="utf-8")

    # 1) 甲方原件中的每个锁定模板都必须登记在 MAPPING.md
    missing = sorted(canonical_ids - mapping_ids)
    if missing:
        return False, f"MAPPING.md 未覆盖的锁定模板（{len(missing)} 个）：{missing}"

    # 2) SYS 级提示也必须登记（它们是代码中的真实出口，容易漏记）：
    #    2 条临床兜底提示（关闭路径、保留缓解观察）+ 1 条操作提示（重新发起预评估）
    sys_ids = {item for item in mapping_ids if item.startswith("SYS-")}
    if len(sys_ids) != 3:
        return False, f"MAPPING.md 中 SYS 级提示应为 3 个，实际 {len(sys_ids)} 个：{sorted(sys_ids)}"

    # 3) _SPEC/04 的计数口径必须是"30 条锁定 OUT-* + 3 条 SYS 级提示"
    if "30 条锁定 `OUT-*` + 3 条 SYS 级提示" not in spec_text:
        return False, "_SPEC/04 的模板计数口径未更新（应为「30 条锁定 OUT-* + 3 条 SYS 级提示」）"

    return True, (
        f"甲方原件 {len(canonical_ids)} 个锁定模板全部已登记；"
        f"SYS 级提示 {len(sys_ids)} 个；_SPEC/04 计数口径一致"
    )


def report_mapping_progress() -> str:
    """检查 4：报告 MAPPING.md 的实现位置回填进度（不判定失败）。"""
    text = MAPPING.read_text(encoding="utf-8")
    pending = text.count("待回填")
    return f"MAPPING.md 中待回填的实现位置单元格：{pending} 处（M3/M4 完成后应归零）"


def main() -> int:
    """执行全部检查并输出结果。"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    checks = [
        ("Token 定义一致", check_token_definition),
        ("Token 使用率", check_token_usage),
        ("输出模板计数", check_template_count),
    ]
    failed = 0
    for name, func in checks:
        ok, detail = func()
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {name}：{detail}")
        if not ok:
            failed += 1
    print(f"[INFO] {report_mapping_progress()}")
    print(f"结果：{len(checks) - failed}/{len(checks)} 项通过。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
