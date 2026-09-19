"""
模块名称：router.py
所属层级：接口层（api）
功能说明：汇总注册全部业务路由（统一 /api 前缀）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现（账号、患者档案；临床流程接口在 M4 接入）
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, patients

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(patients.router)
