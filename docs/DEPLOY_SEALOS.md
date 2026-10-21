# Sealos deployment / Sealos 部署 — 0.4.3

Public testing in a Linux container environment similar to Docker; simulated information only. Use one instance, one Uvicorn worker and SQLite. No Docker image is provided.

这是在类似 Docker 的 Linux 容器中运行的公网测试版本，仅使用模拟资料。采用单实例、单 Uvicorn worker 和 SQLite，不提供 Docker 镜像。

## Existing 0.4.2 installation / 已有0.4.2环境

Use the [0.4.3 patch guide](UPDATE_0.4.3.md) for the officially supplied 0.4.2 Sealos package. It includes prebuilt pages, checks the base files, backs up private data and preserves `.env`, keys and evidence. Do not run administrator initialization again.

此前通过官方0.4.2 Sealos部署包安装的环境，请使用[0.4.3补丁指南](UPDATE_0.4.3.md)。补丁带编译页面，检查基线并备份私有资料，保留`.env`、密钥和依据原件；不要重复初始化管理员。

## Fresh Node.js 22 Devbox / 全新Node.js 22 Devbox

1. Create a Node.js 22 Devbox; verify Node is at least 22.12. Install uv in the Devbox user's tool directory and Python 3.13. Project dependencies stay in `backend/.venv`.

1. 创建Node.js 22 Devbox，确认Node至少22.12。将uv安装在Devbox用户工具目录，并安装Python3.13；项目依赖只安装在`backend/.venv`。

```bash
node --version
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/etmms-uv-install.sh
sh /tmp/etmms-uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.13
uv python find 3.13
```

2. Obtain the development release from `develop` (the owner has not promoted 0.4.3 to main). Record the commit SHA. Downloading a source ZIP is also possible; dependencies and build output are not included.

2. 从`develop`获取此次开发版本（0.4.3未获授权发布到main），记录提交SHA。也可使用源码ZIP，但不含依赖和构建产物。

```bash
cd /home/devbox/project
git clone --branch develop --single-branch https://github.com/GuLifan/T2DM-Remission-Manager.git
cd T2DM-Remission-Manager
git rev-parse HEAD
```

3. Choose an actual persistent directory outside the source tree. The path below is an example: verify its Sealos mount, rather than assuming it survives recreation. Copy the example configuration and edit the real `.env` privately.

3. 在源码之外选择真实持久化目录。下方路径只是示例，须核实Sealos挂载，不能假定重建后仍在。复制配置样例后，私下编辑真实`.env`。

```bash
mkdir -p /home/devbox/etmms-v04-data
chmod 700 /home/devbox/etmms-v04-data
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Configuration / 配置：

```dotenv
ETMMS_DEMO_MODE=true
ETMMS_DATA_DIR=/home/devbox/etmms-v04-data
ETMMS_SESSION_HOURS=8
ETMMS_LOG_LEVEL=INFO
```

Keep the randomly created signing key with the database and backups. Never copy a developer's database, key, `.venv` or `node_modules` into a fresh installation.

随机生成的签名密钥须与数据库和备份一起保存。新装时不要导入开发者数据库、密钥、Windows虚拟环境或依赖目录。

4. Install from lockfiles, build the frontend, then create the **first** administrator interactively. Choose your own unique password of at least 12 characters. The patient list starts empty.

4. 按锁文件安装并编译前端，再交互创建**首个**管理员。使用自己设置的至少12位独立密码；患者列表初始为空。

```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_PYTHON=3.13
bash scripts/setup.sh
cd backend
uv run --no-sync python -m app.demo_cli init-admin
cd ..
```

5. For complete evidence search, privately configure the four approved originals following [EVIDENCE.md](EVIDENCE.md). Core workflow can start without them; do not claim an empty evidence index is complete.

5. 若需完整依据检索，按[EVIDENCE.md](EVIDENCE.md)私下配置四份已批准原件。核心流程可先启动，但空依据索引不等于已完整配置。

```bash
# Only after private resources are configured / 仅在原件配置完成后
cd backend
uv run --no-sync python -m app.evidence_cli
cd ..
```

6. Start and expose **8088** via Sealos public HTTPS. Do not expose a Vite dev server or static aliases to data/resources. `start.sh` runs in the background; `entrypoint.sh` is the alternative foreground entrypoint. Do not run both at once.

6. 启动，并在Sealos网络设置将容器**8088**端口开放为HTTPS公网访问。不要公开Vite开发服务器或数据/原件静态目录。`start.sh`后台运行；`entrypoint.sh`是另一种前台入口，两者不要同时运行。

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
```

Expected / 预期：`{"status":"ok","version":"0.4.3"}`.

The background script defaults to 8088 (`ETMMS_START_PORT` override); the foreground script uses `${PORT:-8088}`. After a Devbox restart run `bash start.sh` again; no boot task is installed. Test terminal-close behavior, persistence and backups in the actual environment.

后台脚本默认8088，可用`ETMMS_START_PORT`覆盖；前台脚本使用`${PORT:-8088}`。Devbox重启后再执行一次`bash start.sh`，没有配置开机自动任务。请现场验证关闭终端、重启持久化和备份。

7. Log in, issue an invitation under **账号管理**, and register a doctor in another browser profile. Confirm empty starting lists, ownership isolation and doctor read-only dates. Administrator date controls are visible at the upper-left of the list/case workspace and remain available in account management.

7. 登录管理员，到**账号管理**发放邀请码，在另一浏览器配置中注册医生。确认初始列表为空、病例隔离、医生日期只读。管理员在列表/病例工作台左上方可直接调整日期，账号管理中也保留入口。

## Upgrading a Git checkout / Git源码部署升级

Stop the old service and make an integrity-checked SQLite backup plus private copies of `.env` and the signing key. Preserve the old checkout. Put the requested new commit in a separate directory, retain the existing external data directory/key, run setup and start the new source. Do not blindly pull/reset a checkout that has received a file patch or manual modifications. Never reinitialize the administrator or delete migration records.

先停旧服务，完成SQLite一致性备份，并私下备份`.env`和签名密钥，保留旧工程。把指定新提交放在另一目录，沿用外部数据目录和密钥，准备依赖后启动。收到文件补丁或有手工修改的Git工作树，不要直接pull/reset覆盖。不要重新初始化管理员或删除迁移记录。

Reference / 参考：[uv installation](https://docs.astral.sh/uv/getting-started/installation/), [Python management](https://docs.astral.sh/uv/guides/install-python/), [Sealos Devbox](https://sealos.io/docs/guides/devbox/).
