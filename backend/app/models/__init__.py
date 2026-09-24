"""
包名称：models
所属层级：数据模型层
功能说明：ORM 模型与请求/响应模式（Pydantic）。
          表结构定义见 `_SPEC/07_技术架构与数据模型_v1.0.md` 第四节。

导出内容：
    - Base：ORM 基类。
    - User / Patient / Event / AuditLog / AppMeta：全部 ORM 模型。
"""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.department import Department
from app.models.event import Event
from app.models.meta import AppMeta
from app.models.patient import Patient
from app.models.user import User

__all__ = ["Base", "User", "Patient", "Event", "AuditLog", "AppMeta", "Department"]
