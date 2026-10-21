#!/usr/bin/env bash
# Linux 准备脚本：不迁移 Windows 环境，不更改全局 Python。
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uv >/dev/null || { echo '请先在 Devbox 安装 uv'; exit 1; }
command -v node >/dev/null || { echo '请先准备 Node.js 22.12+ 或 24'; exit 1; }
cd "$PROJECT_DIR/backend"
uv sync --frozen --no-dev
cd "$PROJECT_DIR/frontend"
npm ci
npm run build
echo '依赖及页面准备完成。已有环境升级：保留原 .env/数据/密钥，不执行 init-admin；回根目录 bash start.sh。'
echo '仅全新环境无管理员时：在 backend 运行 uv run --no-sync python -m app.demo_cli init-admin，再回根目录启动。'
