"""
模块名称：audit.py
所属层级：数据访问层（repository）
功能说明：系统审计日志写入（只增不改）。

覆盖动作：登录、登录失败、登出、建档、事件写入、依据检索、导出、管理操作。
隐私约束：detail 中**不得写入患者完整病历内容**（`_SPEC/07` 第十三节）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    operator_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict | None = None,
) -> AuditLog:
    """写入一条审计日志。

    参数:
        action (str): 动作标识，如 login / login_failed / patient_create / event_write。
        operator_id (int | None): 操作者；登录失败等未认证场景允许为空。
        target_type / target_id: 作用对象（如 patient / 12）。
        detail (dict | None): 附加上下文；禁止写入完整病历内容。
    """
    entry = AuditLog(
        operator_id=operator_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
    )
    db.add(entry)
    db.flush()
    return entry
