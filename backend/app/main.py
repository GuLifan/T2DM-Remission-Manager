"""
模块名称：main.py
所属层级：应用装配层（app）
功能说明：创建 FastAPI 应用、注册异常处理器、启动时执行数据库迁移、暴露健康检查。
          路由按流程单元拆分在 app/api/ 下（M4 接入）；本文件保持"只装配、不写业务"。

主要对象：
    - app：FastAPI 应用实例。
    - lifespan()：启动/关闭钩子（建目录、跑迁移、写启动日志）。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import EtmmsError
from app.core.logging import configure_logging
from app.repository.migrations import run_migrations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子。

    启动时：配置日志 → 建数据目录 → 执行迁移（首次运行自动建库）。
    关闭时：仅记录日志（SQLite 连接由会话依赖自动归还）。
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    # 启动即迁移：保证便携版首次双击即可用，无需手工执行命令
    run_migrations()
    logger.info("ETMMS 后端启动完成：版本 %s，数据目录 %s", __version__, settings.data_dir)
    yield
    logger.info("ETMMS 后端已停止。")


app = FastAPI(
    title="早期2型糖尿病缓解管理软件（ETMMS）",
    version=__version__,
    description="门诊医生使用的 2 型糖尿病缓解管理流程工具：系统负责计算与提醒，医生负责医学决定。",
    lifespan=lifespan,
)

# 注册业务路由（账号、患者档案；临床流程接口在 M4 接入）
app.include_router(api_router)


@app.exception_handler(EtmmsError)
async def _handle_etmms_error(_request: Request, exc: EtmmsError) -> JSONResponse:
    """把业务异常转换为统一响应。

    为什么这样做：前台只应看到医生可读的自然语言（detail），
    错误码（code）只用于开发者排查。
    """
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.get("/api/health", tags=["系统"])
def health() -> dict[str, str]:
    """健康检查：供启动脚本与打包后的启动器探测后端是否就绪。"""
    return {"status": "ok", "version": __version__}


# ===== 前端静态资源（开发态 frontend/dist，打包态 app/static）=====
_STATIC_DIR = get_settings().frontend_dist_dir
if (_STATIC_DIR / "index.html").exists():
    # 构建产物中的静态资源（js/css）走 /assets 前缀
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """单页应用回退路由。

        为什么需要：前端使用 BrowserRouter，刷新任意前端路由（如 /patients/1）
        时请求会打到后端，必须返回 index.html 由前端接管路由。
        该路由注册在最后，因此 /api/** 与 /docs 等更具体的路由优先匹配。
        """
        return FileResponse(_STATIC_DIR / "index.html")
