#!/usr/bin/env bash
# 只启动：安装和构建由 scripts/setup.sh 完成。Sealos 只开放此服务端口。
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TZ=Asia/Shanghai
export ETMMS_DEMO_MODE=true
test -f "$PROJECT_DIR/frontend/dist/index.html" || { echo '请先运行 bash scripts/setup.sh'; exit 1; }
test -x "$PROJECT_DIR/backend/.venv/bin/python" || { echo '缺少 Linux 项目虚拟环境，请先安装依赖'; exit 1; }
cd "$PROJECT_DIR/backend"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8088}" --workers 1 --no-proxy-headers
