"""
模块名称：states.py
所属层级：领域层（domain）
功能说明：状态常量、中文名称与流程单元定义。

临床依据：《临床流程锁定稿 v1.0》第四～十一节；`_SPEC/03` 第一节（状态全集 ST00–ST99）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现（自 V0.1 继承状态集，未增删改）
"""

from __future__ import annotations

# ===== 9 个状态（锁定，不得增删）=====
ST00 = "ST00"  # 常规糖尿病综合管理（入口/返回态）
ST10 = "ST10"  # 60秒缓解预评估
ST20 = "ST20"  # 完整评估并形成主动管理计划
ST31 = "ST31"  # 主动管理—血糖稳定阶段
ST32 = "ST32"  # 主动管理—缓解诱导阶段
ST40 = "ST40"  # 缓解观察期（系统自动状态）
ST50 = "ST50"  # 缓解判定
ST60 = "ST60"  # 缓解后复评
ST99 = "ST99"  # 关闭T2DM缓解路径（终态，无出口）

ALL_STATES: tuple[str, ...] = (ST00, ST10, ST20, ST31, ST32, ST40, ST50, ST60, ST99)

# 状态中文名称：前台只使用这些名称，禁止展示状态代码
STATE_NAMES: dict[str, str] = {
    ST00: "常规糖尿病综合管理",
    ST10: "60秒缓解预评估",
    ST20: "完整评估并形成主动管理计划",
    ST31: "主动管理—血糖稳定阶段",
    ST32: "主动管理—缓解诱导阶段",
    ST40: "缓解观察期",
    ST50: "缓解判定",
    ST60: "缓解后复评",
    ST99: "关闭T2DM缓解路径",
}

# 主动管理的两个阶段（阶段复评发生在此二者之间）
ACTIVE_STAGES: tuple[str, str] = (ST31, ST32)


def state_name(state: str) -> str:
    """返回状态的中文名称；未知状态返回"未知状态"而不是泄漏代码（V0.1 的 L2 缺陷）。"""
    return STATE_NAMES.get(state, "未知状态")


# ===== 6 个流程单元（侧边导航与交付文档共用）=====
FLOW_UNITS: tuple[dict[str, object], ...] = (
    {"key": "pre", "index": 1, "label": "60秒缓解预评估", "states": (ST10,)},
    {"key": "full", "index": 2, "label": "完整评估与计划", "states": (ST20,)},
    {"key": "review", "index": 3, "label": "阶段复评", "states": (ST31, ST32)},
    {"key": "obs", "index": 4, "label": "缓解观察期", "states": (ST40,)},
    {"key": "judge", "index": 5, "label": "缓解判定", "states": (ST50,)},
    {"key": "post", "index": 6, "label": "缓解后复评", "states": (ST60,)},
)


def active_unit_key(state: str) -> str:
    """返回状态所属的流程单元 key（供前端导航高亮）；ST00/ST99 不属于任何单元。"""
    for unit in FLOW_UNITS:
        if state in unit["states"]:  # type: ignore[operator]
            return str(unit["key"])
    return ""
