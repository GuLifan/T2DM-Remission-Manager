"""
脚本名称：build.py
所属层级：辅助脚本（scripts）
功能说明：一键构建便携版（Windows 双击即用），流程：
    1. 前端构建（npm run build）→ frontend/dist
    2. 把 dist 复制到 backend/app/static（由后端同源托管，避免跨域）
    3. PyInstaller --onedir 打包 backend/run_app.py → release/ETMMS/
    4. 输出产物位置与体积

设计取舍（见 _SPEC/07 第十一节）：
    - 使用 --onedir 而非 --onefile：启动更快、便于排查问题。
    - 数据库与日志写到用户数据目录（%LOCALAPPDATA%\\ETMMS），不写程序目录。
    - 产物不含任何真实患者数据。

用法：
    python scripts\\build.py            # 完整构建
    python scripts\\build.py --skip-npm # 跳过前端构建（前端产物已是最新时）

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# 项目根目录（本脚本位于 <root>/scripts/build.py）
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
STATIC_DIR = BACKEND_DIR / "app" / "static"
RELEASE_DIR = ROOT / "release"
WORK_DIR = ROOT / "build" / "pyinstaller"
APP_NAME = "ETMMS"


def log(message: str) -> None:
    """统一输出构建日志（带时间戳）。"""
    print(f"[build.py {time.strftime('%H:%M:%S')}] {message}", flush=True)


def run(command: list[str], cwd: Path) -> None:
    """执行外部命令；失败时终止构建。"""
    log(f"执行：{' '.join(command)}（工作目录 {cwd}）")
    result = subprocess.run(command, cwd=str(cwd), check=False)
    if result.returncode != 0:
        log(f"命令失败（退出码 {result.returncode}），构建终止。")
        sys.exit(result.returncode)


def step_frontend(skip: bool) -> None:
    """步骤 1：构建前端。"""
    if skip:
        log("跳过前端构建（--skip-npm）。")
    else:
        if not (FRONTEND_DIR / "node_modules").exists():
            log("前端依赖未安装，先执行 npm install …")
            run(["npm", "install", "--no-fund", "--no-audit"], FRONTEND_DIR)
        run(["npm", "run", "build"], FRONTEND_DIR)
    if not FRONTEND_DIST.exists():
        log("未找到 frontend/dist，前端构建产物缺失，构建终止。")
        sys.exit(1)


def step_copy_static() -> None:
    """步骤 2：把前端产物复制进后端静态目录（同源托管）。"""
    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    shutil.copytree(FRONTEND_DIST, STATIC_DIR)
    log(f"已复制前端产物 → {STATIC_DIR}")


def step_pyinstaller() -> None:
    """步骤 3：PyInstaller 打包（onedir）。"""
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    run(
        [
            "uv",
            "run",
            "pyinstaller",
            "--noconfirm",
            "--onedir",
            "--name",
            APP_NAME,
            # 把前端静态资源一并打进包内
            "--add-data",
            f"{STATIC_DIR};app/static",
            "--distpath",
            str(RELEASE_DIR),
            "--workpath",
            str(WORK_DIR),
            "--specpath",
            str(WORK_DIR),
            str(BACKEND_DIR / "run_app.py"),
        ],
        BACKEND_DIR,
    )


def report() -> None:
    """步骤 4：报告产物。"""
    target = RELEASE_DIR / APP_NAME
    if not target.exists():
        log("未找到打包产物目录，请检查上方日志。")
        return
    size_mb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / (1024 * 1024)
    log(f"打包完成：{target}")
    log(f"产物体积：{size_mb:.1f} MB；双击 {target / (APP_NAME + '.exe')} 即可运行。")


def main() -> None:
    """构建主流程。"""
    parser = argparse.ArgumentParser(description="ETMMS 便携版构建")
    parser.add_argument("--skip-npm", action="store_true", help="跳过前端构建")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    log("开始构建便携版（前端构建 → 静态资源合并 → PyInstaller onedir）")
    step_frontend(args.skip_npm)
    step_copy_static()
    step_pyinstaller()
    report()


if __name__ == "__main__":
    main()
