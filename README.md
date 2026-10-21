# T2DM Remission Manager / 早期2型糖尿病缓解管理软件

**ETMMS 0.4.3 — public testing on Sealos Cloud in a Linux container environment similar to Docker.**

**ETMMS 0.4.3：部署于 Sealos Cloud、运行在类似 Docker 的 Linux 容器环境中的公网测试版本。**

ETMMS supports a clinician-led E1–E5 workflow: pre-assessment, full assessment, phase review, observation/remission assessment, and post-remission follow-up. This is a redeveloped evaluation build for simulated information only, not a medically validated production system. No accounts, patient records or default passwords are shipped.

ETMMS 支持医生主导的 E1—E5 流程：预评估、完整评估、阶段复评、观察及缓解判定、缓解后随访。本仓库为重新开发后的评估版本，仅使用模拟资料，不代表已完成医学验证的正式医疗系统。仓库不带账号、患者记录或默认密码。

## Changes / 本次修订

- Remove saved medication cards from the current plan with explicit review; preserve earlier plans. Removing cards does not establish actual discontinuation or start observation.
- Restore the administrator's date shortcut at the upper-left of the list and case workspace. Doctors remain read-only.
- Explain the selected examination date, current business date and E4 eligibility interval separately; past examinations remain recordable.
- Center validation and incomplete-assessment notices; preserve actionable results across form refresh and locate fields without discarding drafts.

- 允许从本次方案移除已保存药物卡，重新明确核对后保存新方案；历史保留。删除卡片不会认定已经停药或启动观察。
- 管理员在列表及病例工作台左上方直接调整日期，普通医生仍只读。
- 分别说明检测日、当前业务日和 E4 可采用日期范围；既往检查仍可保存。
- 校验及未通过结果居中提示，表单刷新后仍可查看处理原因，并支持定位字段、保留草稿。

## Deployment / 部署

Use Node.js 22.12+, Python 3.13, uv with a project-local virtual environment, FastAPI and a built React frontend. Supported topology: **one Linux instance, one Uvicorn worker, SQLite, port 8088**. Sealos provides HTTPS ingress. This repository does not supply a Docker image or claim Docker Compose validation.

使用 Node.js 22.12+、Python 3.13、uv 项目内虚拟环境、FastAPI 及编译后的 React 页面。支持部署方式为 **Linux 单实例、单 Uvicorn worker、SQLite、8088 端口**，由 Sealos 提供 HTTPS 入口。本仓库不提供 Docker 镜像，也不宣称完成 Docker Compose 验证。

- [Bilingual installation and upgrade guide / 双语安装及升级指南](docs/DEPLOY_SEALOS.md)
- [0.4.2 → 0.4.3 patch instructions / 更新补丁操作说明](docs/UPDATE_0.4.3.md)
- [Private evidence inputs / 私有依据配置](docs/EVIDENCE.md)
- [Chinese clinical UI guide / 中文业务操作说明](docs/使用说明_v0.4.3.md)

After initial setup / 完成首次安装后：

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
# Stop before maintenance / 维护前停服
bash start.sh stop
```

`start.sh` provides background operation in Devbox; run it again after a restart. Use `entrypoint.sh` for a managed foreground container process. Persistent storage must be verified in the actual platform. Existing upgrades retain the database, `.env` and signing key; never initialize the administrator again.

`start.sh` 用于 Devbox 后台运行；重启后手工再执行。受平台管理的容器前台进程使用 `entrypoint.sh`。请现场核验数据目录的持久化。既有环境升级须保留数据库、`.env` 和签名密钥，不重复初始化管理员。

## Accounts and dates / 账号与日期

Create the first administrator interactively, then issue invitations under **账号管理**. Doctors register into an empty personal case list. Ownership is checked by the backend. Administrator date changes affect that administrator only. Shared browser tabs share login; use separate browser profiles for separate users. Corrections append history; archive/new preserves previous rounds.

首次管理员通过终端交互创建，再到 **账号管理** 发放邀请码。医生注册后个人病例列表为空，病例归属由后端校验。管理员改日期只影响自己；同浏览器标签共享登录，独立用户应使用不同浏览器配置。资料补正追加历史；归档并新建保留旧轮次。

## Evidence and verification / 依据与验证

Medical PDFs and private stakeholder originals are not redistributed through Git. Supply the four hash-matched resources privately for complete evidence search and authenticated original downloads. Core workflow can start without them. Never expose the resource or runtime data directories as anonymous static content.

医学 PDF 和甲方私有原件不通过 Git 分发。完整检索及鉴权原件下载需要私下配置四份哈希匹配材料；核心流程可先启动。不得将原件目录或运行数据目录设为免登录静态资源。

```bash
cd backend
uv sync --frozen
uv run --no-sync pytest
cd ../frontend
npm ci
npm test
npm run lint
npm run build
```

Tests use isolated synthetic data, not deployment patients. See [validation](docs/VALIDATION.md) and [specifications](_SPEC/README.md). Clinical contract v0.3, input v0.4 and database head d04data001 remain unchanged. Local tests do not establish cloud persistence, medical acceptance or production readiness.

测试使用隔离模拟资料，不向部署环境导入病例。详见 [验证记录](docs/VALIDATION.md) 和 [SPEC](_SPEC/README.md)。临床契约 v0.3、输入 v0.4、数据库 head d04data001 保持。本地验证不等于云端持久化、医学验收或正式生产就绪。

## Branch policy / 分支规则

Development targets **develop**. Every **main** update requires Lifan's explicit instruction. Git explanatory text is primarily English; introduction/deployment documents are bilingual. Historical commits remain by the owner's request; current-tree cleanup is not a history purge. No redistribution license for third-party originals is implied. See [contribution rules](CONTRIBUTING.md) and [security](SECURITY.md).

开发版本走 **develop**；每次更新 **main** 均需 Lifan 明确指示。Git 说明以英语为主，介绍及部署文件中英双语。旧提交按要求保留，当前树清理不等于抹除历史；不据此授予第三方原件的再分发许可。详见 [协作规则](CONTRIBUTING.md) 和 [安全边界](SECURITY.md)。
