"""
模块名称：run_app.py
所属层级：便携版启动器（backend 根目录）
功能说明：便携版打包后的入口。启动本地 FastAPI 服务，并自动打开浏览器。
          与开发态的区别只有两点：静态资源来自打包目录、数据库写在用户数据目录。

用法（打包后）：
    双击 release\\ETMMS\\ETMMS.exe

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import threading
import webbrowser

import uvicorn

from app.config import get_settings
from app.main import app


def _open_browser_later(url: str) -> None:
    """稍后打开浏览器：等服务真正开始监听，避免出现"无法访问"页面。"""
    timer = threading.Timer(2.0, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def main() -> None:
    """启动服务并打开浏览器（阻塞直到退出）。"""
    settings = get_settings()
    url = f"http://127.0.0.1:{settings.port}/"
    _open_browser_later(url)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
