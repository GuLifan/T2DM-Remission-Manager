"""
模块名称：test_templates_frozen.py
所属层级：测试（tests）
功能说明：锁定输出文案的"冻结"校验——与公开冻结基线逐字比对。

为什么要锁定基线：输出文案是医生实际看到的临床结论，
任何改写都可能改变临床含义。本测试确保代码中的文案与公开基线逐字一致，
一旦有人改写，测试立即失败，须回到变更控制流程（`_SPEC/README.md`）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain import templates

# 由已核对原件提取的公开回归基线；不等同于重新核对原始文档。
SOURCE = Path(__file__).resolve().parent / "fixtures" / "frozen_output_templates.json"


def _parse_source_templates() -> dict[str, str]:
    """载入从已核对原件提取的最小公开基线；不是重读原件。"""
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_source_file_exists() -> None:
    """公开冻结基线必须在位（否则跳过比对会掩盖问题，所以这里直接失败）。"""
    assert SOURCE.exists(), f"未找到公开输出模板基线：{SOURCE}"


def test_templates_match_source_verbatim() -> None:
    """代码中的 30 条锁定文案必须与公开冻结基线逐字一致。"""
    source = _parse_source_templates()
    assert len(source) == 30, f"公开冻结基线应有 30 条模板，实际解析到 {len(source)} 条"

    mismatches: list[str] = []
    for template_id, expected in source.items():
        actual = templates.TEMPLATES.get(template_id)
        if actual is None:
            mismatches.append(f"{template_id}：代码中缺失")
        elif actual != expected:
            mismatches.append(f"{template_id}：\n  原件 {expected}\n  代码 {actual}")
    assert not mismatches, "锁定文案与公开冻结基线不一致：\n" + "\n".join(mismatches)


def test_template_ids_are_unique_and_prefixed() -> None:
    """模板 ID 必须带 OUT-/SYS- 前缀，且不存在未知前缀。"""
    for template_id in templates.TEMPLATES:
        assert template_id.startswith(("OUT-", "SYS-")), f"非法模板 ID：{template_id}"


@pytest.mark.parametrize("template_id", sorted(templates.TEMPLATES))
def test_no_unintended_whitespace(template_id: str) -> None:
    """文案首尾不得有多余空白（逐字锁定的一部分）。"""
    text = templates.TEMPLATES[template_id]
    assert text == text.strip()
