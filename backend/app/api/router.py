"""
模块名称：router.py
所属层级：接口层（api）
功能说明：汇总注册全部业务路由（统一 /api 前缀）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现（账号、患者档案；临床流程接口在 M4 接入）
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    auth,
    domain_data,
    evidence,
    full_assessment,
    observation,
    patients,
    phase_review,
    post_remission,
    pre_assessment,
    reference_data,
    remission_judge,
    test_support,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
# 登录前注册页也要读取科室字典，因此参考数据接口不要求登录
api_router.include_router(reference_data.router)
api_router.include_router(patients.router)
# 领域数据：状态、流程单元、分支优先级（供前端渲染，避免前后端各写一套）
api_router.include_router(domain_data.router)
# 医学依据：全局只读资料，要求登录但不受患者责任归属限制
api_router.include_router(evidence.router)
# 测试支持：默认关闭，后端内部执行测试模式/账号/患者三重守卫
api_router.include_router(test_support.router)
# 临床流程单元 1–6
api_router.include_router(pre_assessment.router)
api_router.include_router(full_assessment.router)
api_router.include_router(phase_review.router)
api_router.include_router(observation.router)
api_router.include_router(remission_judge.router)
api_router.include_router(post_remission.router)
