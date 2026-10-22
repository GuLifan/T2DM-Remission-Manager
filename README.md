# T2DM Remission Manager / 早期2型糖尿病缓解管理软件

**ETMMS 0.4.3 — a public evaluation release deployed on Sealos Cloud in a Linux container environment similar to Docker.**

**ETMMS 0.4.3：部署于Sealos Cloud、运行在类似Docker的Linux容器环境中的公网验收版本。**

The clinician-led workflow covers pre-assessment, full assessment, phase review, observation/remission assessment and follow-up. Use simulated information only. This release does not establish medical validation or production readiness. No accounts, patients, private configuration, keys or medical originals are distributed through Git.

支持医生主导的预评估、完整评估、阶段复评、观察及缓解判定和后续随访。仅使用模拟资料，不代表已完成医学验证或正式生产就绪。Git不分发账号、病例、真实配置、密钥或医学原件。

## Source and complete deployment / 源码与完整部署

This repository includes current application source, regression tests, migration history and lockfiles. Compiled pages and complete ZIPs are build outputs, excluded from Git. A GitHub source archive must be built before deployment; an operator-prepared complete distribution already contains compiled pages.

仓库包含当前应用源码、回归测试、迁移链和锁文件。编译页面及完整ZIP是构建产物，不提交Git。GitHub源码压缩包须先构建；维护者制作的完整部署包已包含页面。

Supported topology: **one Linux instance, one Uvicorn worker, SQLite, port 8088, HTTPS at Sealos ingress**. Python 3.13 uses uv and `backend/.venv`; source rebuilding uses Node.js 22.12+ and Vite 8.3.3. No Docker image or Docker Compose verification is claimed.

支持 **Linux单实例、单Uvicorn worker、SQLite、8088端口、Sealos HTTPS入口**。Python 3.13通过uv使用`backend/.venv`；源码重建使用Node.js 22.12+及Vite 8.3.3。不提供Docker镜像，也不宣称完成Docker Compose验证。

- [Fresh installation from source / 从源码全新安装](docs/FRESH_INSTALL.md)
- [Complete replacement retaining existing data / 保留数据的完整替换](docs/DEPLOY_SEALOS.md)
- [Clinical operations / 业务操作](docs/USER_GUIDE.md)
- [Evidence configuration / 医学依据配置](docs/EVIDENCE.md)
- [Current specification / 当前约束](_SPEC/CURRENT_SPEC.md)
- [Validation / 验证范围](docs/VALIDATION.md)

Build a complete ZIP after installing dependencies and compiling the frontend:

完成依赖准备及前端编译后，在工程根生成完整ZIP：

```bash
cd frontend
npm ci
npm run build
cd ..
backend/.venv/bin/python scripts/build_release.py --output artifacts/release
```

The builder includes current source, compiled assets, migration files, lockfiles, release manifest and operating documentation. It excludes tests, dependencies, private originals and runtime data. Full replacement validates the manifest, prepares a clean tree, carries over current configuration/environment/data/evidence, backs up privately and switches at the existing application path. Rollback retains later records. Ordinary file overwriting is insufficient to remove obsolete files.

打包工具包含当前源码、编译资产、迁移、锁文件、发布清单及操作说明，排除测试、依赖、私有原件和运行资料。完整替换核验清单、准备新树、保留当前配置/环境/数据/依据，生成私有备份后切换至原路径；回退保留后续记录。普通同名覆盖不能清理旧文件。

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
bash start.sh stop
```

Existing installations must not initialize the administrator again. Devbox background startup is manual after restart; verify storage persistence on the actual platform.

现有环境不再次初始化管理员。Devbox重启后手工后台启动；存储持久化须在实际平台核验。

## Current behavior / 当前行为

Doctors register by administrator invitation and start with empty case lists. Administrators can adjust their own business date from the upper-left entry; doctors use the system date. Current-plan medication removal preserves history and requires renewed review; emptying a plan does not establish actual discontinuation. Past examinations remain recordable, E4 explains date eligibility, and centered validation notices preserve drafts and actionable results.

医生凭邀请码注册，病例从零创建。管理员可在左上入口调整自己的业务日期，医生使用系统日。移除本次方案药物保留历史并须重新核对，清空不等于实际停药。既往检查可记录，E4明确日期资格，居中提示保留草稿及待处理结果。

Application 0.4.3, clinical contract v0.3, input schema v0.4 and database head d04data001 are separate compatibility layers. Their identifiers, migration chain and valid regression cases remain current dependencies.

产品0.4.3、临床契约v0.3、输入v0.4和数据库head d04data001属于不同兼容层；其标识、迁移链及有效回归用例继续保留。

## Verification and publication / 验证与发布

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
cd ../backend
uv sync --frozen
uv run --no-sync pytest
```

Build the frontend before running backend service tests. Tests use temporary synthetic information. Local engineering results do not establish capacity, cloud restart persistence, regulatory compliance or clinician acceptance. See [security boundaries](SECURITY.md).

后端服务测试前先完成前端构建。测试使用临时模拟资料。本地工程结果不代表容量极限、云端重启持久化、监管合规或临床验收。详见[安全边界](SECURITY.md)。

Development publishes to **develop**. Every **main** update requires Lifan's explicit instruction. Preserve Git history; never publish local handover notes, credentials, databases or private originals. Git explanations are primarily English; introductions and deployment guides are bilingual.

开发发布到 **develop**；每次更新 **main** 均须Lifan明确指示。保留Git历史，不发布本地交接、凭据、数据库或私有原件。Git说明英语为主，介绍及部署文件中英双语。
