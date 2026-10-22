# Fresh installation from source / 从源码全新安装

Use only for a genuinely new installation. Existing installations follow [complete replacement](DEPLOY_SEALOS.md) and retain their accounts/data; do not create a new administrator or data directory for an update.

仅适用于全新环境。已有环境按[完整替换](DEPLOY_SEALOS.md)保留账号和数据，更新不创建新管理员或新数据目录。

## Environment / 环境

Prepare Node.js 22.12+, uv and Python 3.13. uv must be on PATH. Python packages use the project virtual environment; do not modify global Python packages. Start with a checkout of the `develop` branch:

准备Node.js 22.12+、uv及Python 3.13，确保uv在PATH中。Python依赖使用项目环境，不修改全局包。从`develop`检出源码：

```bash
git clone --branch develop https://github.com/GuLifan/T2DM-Remission-Manager.git ETMMS
cd ETMMS
uv python install 3.13
cd backend
uv sync --frozen --python 3.13 --no-dev
cp .env.example .env
```

Edit `backend/.env` and set `ETMMS_DATA_DIR` to an absolute private persistent directory, for example `/home/devbox/etmms-data`. Keep `ETMMS_DEMO_MODE=true`; expose neither this data folder nor keys as static content. Confirm the Devbox volume/mount actually persists across restart.

编辑`backend/.env`，将`ETMMS_DATA_DIR`设为私有持久化绝对目录，例如`/home/devbox/etmms-data`。保留`ETMMS_DEMO_MODE=true`；不静态公开数据或密钥，并现场确认该目录确实持久化。

## Initialize and compile / 初始化与编译

```bash
uv run --no-sync python -m app.demo_cli init-admin
cd ../frontend
npm ci
npm run build
cd ..
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
```

Create the administrator interactively with your own credentials; none are supplied. Expected health version:0.4.3. Administrators then issue doctor invitations. New accounts have no clinical cases.

用自己的凭据交互创建管理员，仓库不提供默认密码。健康版本应为0.4.3。管理员随后创建医生邀请码，新账号没有临床病例。

## Sealos route and resources / Sealos路由与资源

Expose the application container port8088 with HTTPS in Sealos. Do not confuse the Node template port8080 with this application. Keep one instance/worker. `start.sh` runs in the background; `entrypoint.sh` is the foreground entry for platform management.

在Sealos将应用容器端口8088设为HTTPS公网入口；不要误用Node模板8080。保持单实例/worker。`start.sh`后台运行；`entrypoint.sh`用于平台管理的前台入口。

Configure approved originals privately following [evidence instructions](EVIDENCE.md). Core workflow can start without them, but full-text evidence is incomplete until configured. Never copy patients or runtime databases from a developer's machine.

依据按[说明](EVIDENCE.md)私下配置。没有原件时核心流程可启动，但全文依据不完整。不从开发者机器导入患者或运行数据库。

To prepare a complete operating distribution after compilation:

编译完成后制作完整运行分发：

```bash
backend/.venv/bin/python scripts/build_release.py --output artifacts/release
```

The output contains a ZIP and `SHA256SUMS.txt`. It excludes configuration, secrets, accounts, patients, private originals, dependency directories and regression fixtures. Use the complete replacement guide for an existing installation.

输出ZIP和`SHA256SUMS.txt`，排除配置、密钥、账号、病例、私有原件、依赖目录及回归夹具。现有环境使用完整替换指南。
