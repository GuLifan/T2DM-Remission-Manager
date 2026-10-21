"""公网统一门禁：患者所有子路径先验归属，关闭旧接口和任意测试跳转。"""

from __future__ import annotations

import re
import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.core.exceptions import EtmmsError
from app.models.patient import Patient
from app.repository.database import SessionLocal

_attempts: OrderedDict[str, deque] = OrderedDict()
_lock = Lock()


def limited(key: str) -> bool:
    """单实例每来源一分钟20次认证请求；只信任连接来源，不读取伪造转发头。"""
    now = time.monotonic()
    with _lock:
        values = _attempts.setdefault(key, deque())
        _attempts.move_to_end(key)
        while values and values[0] <= now - 60:
            values.popleft()
        if len(_attempts) > 512:
            _attempts.popitem(last=False)
        if len(values) >= 20:
            return True
        values.append(now)
        return False


def patient_guard(request: Request, patient_id: int) -> tuple[int, str] | None:
    """线程池中核对权限，404 不暴露他人病例是否存在；归档可读不可写。"""
    with SessionLocal() as db:
        try:
            user = get_current_user(request.headers.get("authorization"), db)
        except EtmmsError as exc:
            return exc.status_code, str(exc.message)
        patient = db.get(Patient, patient_id)
        if not patient or (user.role != "admin" and patient.owner_id != user.id):
            return 404, "未找到该病例。"
        if not patient.is_test_patient:
            return 403, "该记录不在当前环境允许的管理范围内。"
        if patient.archived and request.method not in {"GET", "HEAD"}:
            return 403, "此病例已归档，请在当前病例中继续。"
    return None


async def guard(request: Request, call_next):
    """所有患者路由统一防护，包括只读观察和事件列表，不依赖前端隐藏。"""
    path = request.url.path
    if get_settings().demo_mode:
        if path in {"/api/auth/login", "/api/auth/register"} and limited(
            request.client.host if request.client else "unknown"
        ):
            return JSONResponse(
                status_code=429, content={"detail": "操作过于频繁，请一分钟后重试。"}, headers={"Retry-After": "60"}
            )
        match = re.fullmatch(r"/api/patients/(\d+)(?:/(.*))?/?", path)
        if match:
            error = await run_in_threadpool(patient_guard, request, int(match[1]))
            if error:
                return JSONResponse(status_code=error[0], content={"detail": error[1]})
            suffix = match[2] or ""
            # 旧临床入口、资料导入和患者转移在此 demo 关闭，避免绕过新契约。
            if suffix and suffix not in {"events", "height", "reset"} and not suffix.startswith(("clinical-v03/", "clinical-v04/")):
                return JSONResponse(status_code=403, content={"detail": "该操作不在当前开放的临床流程范围内。"})
        if path in {"/api/patients/import", "/api/auth/bootstrap", "/api/auth/assignable-doctors"}:
            return JSONResponse(status_code=403, content={"detail": "当前环境未开放此入口。"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
