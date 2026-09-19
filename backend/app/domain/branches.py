"""
模块名称：branches.py
所属层级：领域层（domain）
功能说明：阶段复评分支的**优先级表**（单一数据源），以及"被忽略分支"的显式报告。

为什么需要它（V0.1 的实测缺陷）：
    V0.1 把 8 个复评分支做成 4 组互不排斥的勾选框，优先级藏在代码里。
    医生同时勾选"停用最后一种药"和"明显血糖失控"时，只会走失控分支，
    **停药日期被静默丢弃**——既不报错也不提示，属于会误导临床操作的设计缺陷。

V1.0 的做法：
    1. 分支按优先级显式排列（数字小者优先）；
    2. 前端按本表渲染，互斥分支用单选，被覆盖项禁用并写明原因；
    3. 后端再次按本表裁决，并把**被忽略的分支与原因**写进事件载荷，绝不静默丢弃。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Branch:
    """一个复评分支。"""

    priority: int
    key: str
    rule_id: str
    label: str
    hint: str
    template_id: str
    # 目标状态："current" 表示留在当前阶段，否则为具体状态代码
    target: str


@dataclass(frozen=True)
class IgnoredBranch:
    """被更高优先级分支覆盖的分支（必须向医生与事件流水说明原因）。"""

    branch: Branch
    reason: str


# 阶段复评分支优先级：数字小者优先
PHASE_REVIEW_BRANCHES: tuple[Branch, ...] = (
    Branch(
        priority=1,
        key="uncontrolled",
        rule_id="E3-B08",
        label="存在明显血糖失控（医生确认）",
        hint="确认后阶段置为血糖稳定，并生成治疗调整任务。",
        template_id="OUT-E3-ADJUST",
        target="ST31",
    ),
    Branch(
        priority=2,
        key="on_treatment_non_diabetic",
        rule_id="E3-B06",
        label="治疗下血糖已达非糖尿病范围，且仍在使用获益药",
        hint="只记录当前状态，不建议停药、不进入观察期。",
        template_id="OUT-E3-ON-TREATMENT",
        target="current",
    ),
    Branch(
        priority=3,
        key="stop_last_med",
        rule_id="E3-B07",
        label="停用最后一种具有降糖作用的药物",
        hint="记录停药日期后，系统自动进入缓解观察期。",
        template_id="OUT-E3-OBS-ENTER",
        target="ST40",
    ),
    Branch(
        priority=4,
        key="routine_action",
        rule_id="E3-B01..B05",
        label="常规复评动作（继续 / 调整 / 转换阶段 / 结束主动管理）",
        hint="按所选动作更新阶段、目标与下次复评日期。",
        template_id="",  # 具体模板由所选动作决定
        target="",
    ),
)

# 互斥约束：这些分支不能同时为真（在界面与接口层都要拦住）
EXCLUSIVE_PAIRS: tuple[tuple[str, str, str], ...] = (
    (
        "stop_last_med",
        "on_treatment_non_diabetic",
        "不能同时记录“停用最后一种降糖药”与“仍在使用降糖药”，请核对本次实际情况。",
    ),
)


def branch_by_key(key: str) -> Branch:
    """按 key 取分支定义；不存在时抛 KeyError（属工程缺陷）。"""
    for branch in PHASE_REVIEW_BRANCHES:
        if branch.key == key:
            return branch
    raise KeyError(f"未知的复评分支：{key}")


def resolve_branch(hits: set[str]) -> tuple[Branch, list[IgnoredBranch]]:
    """按优先级裁决实际生效的分支。

    参数:
        hits (set[str]): 本次为真的分支 key 集合。

    返回:
        tuple[Branch, list[IgnoredBranch]]: 生效分支，以及被忽略的分支与原因。

    异常:
        ValueError: 同时命中了互斥分支（调用方应转成医生可读提示）。
    """
    # 先做互斥校验：互斥项同时为真说明医生填了自相矛盾的内容
    for left, right, message in EXCLUSIVE_PAIRS:
        if left in hits and right in hits:
            raise ValueError(message)

    matched = [branch for branch in sorted(PHASE_REVIEW_BRANCHES, key=lambda item: item.priority) if branch.key in hits]
    if not matched:
        # 常规复评动作是兜底分支：只要医生提交了动作就必然命中
        matched = [branch_by_key("routine_action")]

    chosen = matched[0]
    ignored = [
        IgnoredBranch(
            branch=branch,
            reason=f"本次已被优先级更高的分支「{chosen.label}」覆盖，未生效；如需按该分支处理，请取消上一项勾选。",
        )
        for branch in matched[1:]
    ]
    return chosen, ignored
