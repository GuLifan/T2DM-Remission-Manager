"""v0.3转移契约：原51条与已批准7条补充边分开，不修改旧接口规则表。

V03-A只冻结可验证契约；V03-B/C接入服务时必须使用转移ID校验，
不能只按“源状态→目标状态”判定医学条件，也不能把本模块当成自动临床裁决。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import BusinessRuleError
from app.domain.states import ALL_STATES

CONTRACT_VERSION = "v0.3"
LEGACY_VERSION = "v1.0"
# 仅来源术语对照；新接口仍要求字段字典的规范值，不借此推断临床事实。
SOURCE_ALIASES = {"F057": {"是": "已实际停用", "实际已停": "已实际停用"}, "F047": {"未达到": "未满足"}}


@dataclass(frozen=True)
class AtomicTransition:
    """每个ID对应一个源、一个目标；原文和原表行号保留供审计。"""

    id: str
    rule_id: str
    source: str
    target: str
    condition: str
    doctor_required: bool
    excel_row: int | None = None
    supplemental: bool = False


_SOURCE = json.loads(Path(__file__).with_name("clinical_v03_contract.json").read_text(encoding="utf-8"))
SOURCE_SHA256: str = _SOURCE["workbook_sha256"]
ATOMIC_TRANSITIONS = tuple(
    AtomicTransition(
        id=row["id"], rule_id=row["rule_id"], source=row["source"], target=row["target"],
        condition=row["condition"], doctor_required=row["doctor_required"] == "是",
        excel_row=row["excel_row"],
    )
    for row in _SOURCE["atomic_transitions"]
)
# 补充边经Lifan于2026-10-12批准。保持独立，不冒充工作簿原文。
SUPPLEMENTAL_TRANSITIONS = (
    AtomicTransition("P01", "SYS-REOPEN", "ST00", "ST10", "医生明确重新发起，保留原结束史", True, supplemental=True),
    AtomicTransition("P02", "E4-B07", "ST50", "ST20", "医生确认新分型证据/重大变化需完整评估，记录原因", True, supplemental=True),
    AtomicTransition("P03A", "E3-B08", "ST31", "ST20", "医生确认新分型证据/重大变化需完整评估，记录原因", True, supplemental=True),
    AtomicTransition("P03B", "E3-B08", "ST32", "ST20", "医生确认新分型证据/重大变化需完整评估，记录原因", True, supplemental=True),
    AtomicTransition("P04", "E5-B04", "ST60", "ST20", "确认缓解终止且新分型证据/重大变化需完整评估", True, supplemental=True),
    AtomicTransition("P05A", "E5-B03", "ST60", "ST31", "器官/体重获益用药，医生主动选择血糖稳定，不标记终止", True, supplemental=True),
    AtomicTransition("P05B", "E5-B03", "ST60", "ST32", "器官/体重获益用药，医生主动选择缓解诱导，不标记终止", True, supplemental=True),
)
TRANSITIONS_BY_ID = {t.id: t for t in (*ATOMIC_TRANSITIONS, *SUPPLEMENTAL_TRANSITIONS)}
assert len(ATOMIC_TRANSITIONS) == 51 and len(TRANSITIONS_BY_ID) == 58
assert all(t.source in ALL_STATES and t.target in ALL_STATES for t in TRANSITIONS_BY_ID.values())


def require_transition(transition_id: str, source: str, target: str) -> AtomicTransition:
    """拒绝未知ID或错用来源/目标；条件仍必须由具体服务逐条验证。"""
    item = TRANSITIONS_BY_ID.get(transition_id)
    if item is None or item.source != source or item.target != target:
        raise BusinessRuleError("本次操作与当前流程不一致，请刷新后核对。", code="V03_TRANSITION_MISMATCH")
    return item
