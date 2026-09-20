"""
模块名称：domain_data.py
所属层级：接口层（api）
功能说明：把领域层的"事实"导出给前端，保证前后端与文档指向同一份定义。

为什么必须导出（`_SPEC/07` AD-01）：
    V0.1 的分支优先级在前端与后端各写一套，导致"医生勾了 A 却被 B 覆盖"且无人察觉。
    V1.0 由后端输出状态表与分支优先级表，前端只负责渲染，不允许自行硬编码。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.domain.branches import PHASE_REVIEW_BRANCHES
from app.domain.states import FLOW_UNITS, STATE_NAMES
from app.models.user import User

router = APIRouter(prefix="/domain", tags=["领域数据（供前端渲染）"])


class StateOut(BaseModel):
    """状态定义。code 仅用于前端路由，**不得展示给医生**。"""

    code: str
    name: str


class FlowUnitOut(BaseModel):
    """流程单元定义（侧边导航用）。"""

    key: str
    index: int
    label: str
    states: list[str]


class BranchOut(BaseModel):
    """阶段复评分支定义（按 priority 升序渲染，高优先级在上）。"""

    priority: int
    key: str
    rule_id: str
    label: str
    hint: str
    target: str


@router.get("/states", response_model=list[StateOut])
def list_states(_current_user: User = Depends(get_current_user)) -> list[StateOut]:
    """返回全部状态代码与中文名称。"""
    return [StateOut(code=code, name=STATE_NAMES[code]) for code in STATE_NAMES]


@router.get("/flow-units", response_model=list[FlowUnitOut])
def list_flow_units(_current_user: User = Depends(get_current_user)) -> list[FlowUnitOut]:
    """返回 6 个流程单元定义。"""
    return [
        FlowUnitOut(key=str(unit["key"]), index=int(unit["index"]), label=str(unit["label"]), states=[str(s) for s in unit["states"]])  # type: ignore[arg-type]
        for unit in FLOW_UNITS
    ]


@router.get("/branches", response_model=list[BranchOut])
def list_branches(_current_user: User = Depends(get_current_user)) -> list[BranchOut]:
    """返回阶段复评分支优先级表（前端按此顺序渲染，禁止自行硬编码）。"""
    return [
        BranchOut(
            priority=branch.priority,
            key=branch.key,
            rule_id=branch.rule_id,
            label=branch.label,
            hint=branch.hint,
            target=branch.target,
        )
        for branch in PHASE_REVIEW_BRANCHES
    ]
