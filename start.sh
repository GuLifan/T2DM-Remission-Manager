#!/usr/bin/env bash
# Devbox 手工一键启动：后台模式可关闭终端，重复执行不会启动第二个实例。
# 发布到 Sealos 应用管理时仍使用前台 entrypoint.sh，不用本脚本作容器入口。
set -euo pipefail
test "$#" -le 1 || { echo '用法：bash start.sh [start|status|stop]'; exit 2; }
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
test -x "$PYTHON" || { echo '缺少 Linux 项目虚拟环境，请先运行 bash scripts/setup.sh'; exit 1; }
export TZ=Asia/Shanghai
export ETMMS_DEMO_MODE=true
# Node模板可能遗留PORT=8080，因此后台入口采用本项目专属覆盖变量。
export PORT="${ETMMS_START_PORT:-8088}"
cd "$PROJECT_DIR/backend"
exec "$PYTHON" "$PROJECT_DIR/scripts/demo_service.py" "${1:-start}"
