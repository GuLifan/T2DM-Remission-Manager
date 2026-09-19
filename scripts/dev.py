"""
脚本名称：dev.py
所属层级：辅助脚本（scripts）
功能说明：一键启动开发态前后端服务。
    1. 幂等检查后端(8080)与前端(5173)是否在运行；
    2. 启动缺失的服务（后端 uv run uvicorn --reload；前端 npm run dev）；
    3. 等待后端健康检查通过；
    4. 按 Ctrl+C 一键停止由本脚本启动的全部子进程。

用法：
    python scripts\\dev.py                # 启动并等待 Ctrl+C
    python scripts\\dev.py --no-browser   # 不自动打开浏览器
    python scripts\\dev.py --dry-run      # 只打印计划

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# 项目根目录（本脚本位于 <root>/scripts/dev.py）
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
BACKEND_PORT = 8080
FRONTEND_PORT = 5173
APP_URL = f"http://localhost:{FRONTEND_PORT}"
HEALTH_URL = f"http://127.0.0.1:{BACKEND_PORT}/api/health"
BACKEND_READY_TIMEOUT = 90
FRONTEND_READY_TIMEOUT = 60


def log(message: str) -> None:
    """统一输出启动日志（带时间戳）。"""
    print(f"[dev.py {time.strftime('%H:%M:%S')}] {message}", flush=True)


def port_in_use(port: int) -> bool:
    """检查端口是否已被监听（同时探测 IPv4 与 IPv6 回环）。"""
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            try:
                if sock.connect_ex((host, port)) == 0:
                    return True
            except OSError:
                continue
    return False


def backend_healthy() -> bool:
    """探测后端健康检查接口。"""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for(predicate, timeout: int, what: str) -> bool:
    """轮询等待条件成立，超时返回 False。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(1)
    log(f"等待{what}超时（{timeout} 秒）。")
    return False


def stop_process_tree(proc: subprocess.Popen) -> None:
    """停止子进程及其进程树（uv/npm 会再拉起子进程）。"""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)


def find_command(name: str) -> str:
    """在 PATH 中定位命令（Windows 上 npm 实际为 npm.cmd）。"""
    path = shutil.which(name)
    if path is None:
        log(f"错误：未找到命令 {name}，请先安装并加入 PATH。")
        sys.exit(1)
    return path


def start_backend() -> subprocess.Popen | None:
    """启动后端（uvicorn --reload）；已在运行时返回 None。"""
    if port_in_use(BACKEND_PORT):
        if backend_healthy():
            log(f"后端已在运行（端口 {BACKEND_PORT}），跳过启动。")
            return None
        log(f"警告：端口 {BACKEND_PORT} 被占用但健康检查失败，仍尝试启动。")
    uv = find_command("uv")
    log("启动后端：uvicorn (127.0.0.1:8080, --reload) …")
    proc = subprocess.Popen(
        [uv, "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--reload"],
        cwd=str(BACKEND_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    if not wait_for(backend_healthy, BACKEND_READY_TIMEOUT, "后端就绪"):
        log("后端未能就绪，请查看上方输出排查。")
    return proc


def start_frontend() -> subprocess.Popen | None:
    """启动前端（vite dev）；已在运行时返回 None。"""
    if port_in_use(FRONTEND_PORT):
        log(f"前端已在运行（端口 {FRONTEND_PORT}），跳过启动。")
        return None
    npm = find_command("npm")
    log("启动前端：vite dev (http://localhost:5173) …")
    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    wait_for(lambda: port_in_use(FRONTEND_PORT), FRONTEND_READY_TIMEOUT, "前端就绪")
    return proc


def main() -> None:
    """一键启动主流程。"""
    parser = argparse.ArgumentParser(description="ETMMS 开发态一键启动")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--dry-run", action="store_true", help="只打印启动计划")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    log("早期2型糖尿病缓解管理软件（ETMMS v1.0）开发态启动")
    if args.dry_run:
        log(f"[计划] 后端：{BACKEND_DIR} → uvicorn :{BACKEND_PORT}（已运行={port_in_use(BACKEND_PORT)}）")
        log(f"[计划] 前端：{FRONTEND_DIR} → vite :{FRONTEND_PORT}（已运行={port_in_use(FRONTEND_PORT)}）")
        log(f"[计划] 浏览器：{APP_URL}")
        return

    backend_proc: subprocess.Popen | None = None
    frontend_proc: subprocess.Popen | None = None
    try:
        backend_proc = start_backend()
        frontend_proc = start_frontend()
        if not args.no_browser:
            log(f"打开浏览器：{APP_URL}")
            webbrowser.open(APP_URL)
        log("全部服务就绪。按 Ctrl+C 停止由本脚本启动的服务。")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("收到退出信号，正在停止服务…")
    finally:
        if frontend_proc is not None:
            stop_process_tree(frontend_proc)
        if backend_proc is not None:
            stop_process_tree(backend_proc)
        log("已退出。")


if __name__ == "__main__":
    main()
