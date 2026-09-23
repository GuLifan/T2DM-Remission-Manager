"""
模块名称：events.py
所属层级：数据访问层（repository）
功能说明：临床事件流水的读写。

**核心约束：事件只增不改**——本模块刻意不提供任何 update/delete 接口。
修改历史只能通过新增事件表达，这是临床可追溯性的基础（`_SPEC/07` 4.3）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import Event


def add_event(
    db: Session,
    *,
    patient_id: int,
    operator_id: int,
    rule_id: str,
    source_state: str,
    target_state: str,
    output_text: str,
    source: str = "doctor",
    template_id: str | None = None,
    payload: dict | None = None,
    request_id: str | None = None,
    simulated_date: date | None = None,
) -> Event:
    """追加一条事件流水。

    参数:
        source (str): doctor（医生操作）/ system（系统自动动作）。
        payload (dict | None): 本次输入快照；包含被忽略的分支与原因，保证可追溯。
        request_id (str | None): 客户端请求标识，用于识别重复提交。
        simulated_date (date | None): 本次事件实际采用的模拟日期；真实日期下为空。
    """
    event = Event(
        patient_id=patient_id,
        operator_id=operator_id,
        source=source,
        rule_id=rule_id,
        source_state=source_state,
        target_state=target_state,
        template_id=template_id,
        output_text=output_text,
        # ensure_ascii=False 便于人工查看中文输入快照
        payload=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        request_id=request_id,
        simulated_date=simulated_date,
    )
    db.add(event)
    db.flush()
    return event


def count_events(db: Session, patient_id: int) -> int:
    """统计某患者的事件总数（分页用）。"""
    return int(
        db.scalar(select(func.count()).select_from(Event).where(Event.patient_id == patient_id)) or 0
    )


def list_events(db: Session, patient_id: int, *, limit: int = 50, offset: int = 0) -> list[Event]:
    """按时间倒序分页查询事件（V0.1 无分页，事件表变大后会拖慢查询）。"""
    statement = (
        select(Event)
        .where(Event.patient_id == patient_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


def find_by_request_id(db: Session, patient_id: int, request_id: str) -> Event | None:
    """按请求标识查询已有事件（幂等判定：同一请求不重复产生事件）。"""
    statement = select(Event).where(Event.patient_id == patient_id, Event.request_id == request_id)
    return db.scalar(statement)
