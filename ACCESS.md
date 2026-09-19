# ACCESS.md — Agent 高权限行为日志（开发者审计）

> **用途**：记录 AI Agent 在本项目开发过程中发生的**全部高权限行为**（读取工作区外路径、写入、复制、批量操作、联网、提权执行、安装依赖等），供开发者随时核查"Agent 到底做过什么"。
>
> **这不是给使用者看的文档**，也不进入临床软件界面。
>
> **记录规则**：行为发生后立即追加一行；凡属"工作区外读取""提权执行""联网""批量写入/复制"的行为必须记录，只读工作区内文件可合并记录。
>
> **维护者**：AI Agent（Lifan 授权）｜**建立日期**：2026-09-19

---

## 一、行为日志

| 序号 | 时间 | 行为 | 对象 | 权限模式 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-09-19 | 通读 V0.1 全库（只读） | `ETMMS_V0.1_dev_260818`：README/CHANGELOG/ACCESS/mapping、`_DEV` 三份命令文件与 7 份甲方 markdown、`_SPEC` 01–08、`backend` 全量源码与测试、`frontend` 全部源文件、`交付物` 三份 | 只读 | V1.0 方案的需求与缺陷分析基础；未修改任何文件。 |
| 2 | 2026-09-19 | 提权启动开发服务（查看真实界面） | V0.1 后端 uvicorn 127.0.0.1:8080、前端 vite localhost:5173；浏览器截图 3 张 | require_escalated（沙箱内 uv/vite 子进程被拦） | 仅启动与截图，未修改代码；服务已停止，未残留进程。 |
| 3 | 2026-09-19 | 提权运行后端测试（核实基线） | `backend`：`uv run pytest -q` | require_escalated | 结果 104 passed，1 warning（httpx 弃用提示）；只读性质。 |
| 4 | 2026-09-19 | 工作区外只读检索（定位甲方材料） | `C:\Users\lifan\`、`D:\`（限深度）、`C:\Users\lifan\Desktop\CGM`、`D:\LifanDataClaudeCode\ETMMS260806` | 只读 | 用途：确认甲方原件与医学依据材料位置；未复制、未修改。 |
| 5 | 2026-09-19 | 联网查询（失败，未取得内容） | 尝试检索 Chrome / Material 3 Web 调色板 Token | 只读（网络） | 检索站点未返回可用内容；UI.md 的 Token 取值改用已知的 Google Material 3 调色板，并在 M1 阶段用本机 Chrome 做视觉比对校准。 |
| 6 | 2026-09-19 | 创建 V1.0 目录骨架 | `ETMMS_V1.0`：`_DEV`（甲方材料/医学依据/历史参考）、`_SPEC`、`backend`、`frontend`、`data/evidence`、`scripts`、`交付物` | workspace-write | V1.0 为空目录，未覆盖任何既有内容。 |
| 7 | 2026-09-19 | 复制甲方材料与医学依据（读工作区外 + 写 V1.0） | 自 `C:\Users\lifan\Desktop\CGM\` 与 `C:\Users\lifan\Desktop\` 复制 3 份原件（锁定稿 docx、任务书 docx、实现表 xlsx）与 3 份依据 PDF 至 `_DEV\`；自 V0.1 `_DEV\早期T2DM缓解管理软件_markdown\` 复制 7 份 md 派生版；复制 PRINCIPLE.md；历史版本 COMPASS 与 macOS 版 UI 规范归入 `_DEV\历史参考\` | 只读外部 + workspace-write | **纯复制，未删除也未修改任何 V0.1 文件与任何外部文件**；来源仍保留在原位置。 |
| 8 | 2026-09-19 | 写入工程基础文件 | `ETMMS_V1.0\.gitignore`、`.gitattributes` | workspace-write | 约定：Python 虚拟环境建在项目内、患者数据库与依据索引不入库、`_DEV` 甲方材料随仓库版本化。 |
| 9 | 2026-09-19 | 写入根目录文档 | `README.md`、`CHANGELOG.md`、`mapping.md`、`_DEV\README.md` | workspace-write | `README.md` 含项目定位、目录结构、依据优先级、10 条医学红线、开发与打包约定；`mapping.md` 为临床规则→代码→测试映射清单。 |
| 10 | 2026-09-19 | 写入 `UI.md`（全量重写） | `ETMMS_V1.0\UI.md`（33 KB，691 行） | workspace-write | 由 macOS Liquid Glass 体系整体替换为 Google Chrome / Material Design 3 体系；新增"分支互斥规范""Token 使用率自查机制""前端工程规范""无障碍规范"。 |
| 11 | 2026-09-19 | 生成 `_SPEC/01–05`（继承 + 修订） | `_SPEC\01…05_v1.0.md` | workspace-write | 从 V0.1 复制后执行 20 项精确字符串替换（一次性脚本 `scripts/_m0_spec_edits.py`，命中 32/33，1 项因引号形态不同改由人工修正）；脚本已删除。 |
| 12 | 2026-09-19 | 写入 `_SPEC` 目录说明与 06–08 | `_SPEC\README.md`、`06_问题清单与裁决记录`、`07_技术架构与数据模型`、`08_实施计划与交付验收` | workspace-write | 06 合并 V0.1 的 06+08 并新增 6 条 V1.0 问题；07 定义分层架构、数据模型、迁移、账号与审计、依据检索、打包路线；08 以"成品交付"重排 M0–M7。 |
| 13 | 2026-09-19 | 数据核对（只读） | V0.1 `backend\app\services\outputs.py`、`backend\app\models\schemas.py`、`_DEV\...\临床流程实现表_最小字段映射.md` | 只读 | 实测得到 30 个 `OUT-*` + 2 个 `SYS-*`（文档原写"34 个"有误），字段集确为 F001–F056 共 56 个。据此更正 `_SPEC/02`、`_SPEC/04`、`CHANGELOG.md`，并登记问题 `V1.0-Q-01`。 |
| 14 | 2026-09-19 | **提权**初始化 Git 仓库并提交基线 | `ETMMS_V1.0\.git`；提交 `784da79`（docs: M0 规范基线）；分支 `main` | require_escalated（沙箱将 `.git` 设为只读，`git add` 被拒） | 提交内容：`.gitignore`、`.gitattributes`、`ACCESS.md`、`CHANGELOG.md`、`README.md`、`UI.md`、`mapping.md`、`_DEV/**`、`_SPEC/**`，共 32 个文件（含 7.0 MB 甲方原件与依据 PDF）。 |
| 15 | 2026-09-19 | 只读完整性核对 | V0.1 工作区 `git status`；V1.0 文件清单 | 只读 | V0.1 仅存在本次工作**之前**已存在的 1 项未提交改动（`交付物\风险代码检查报告_v0.1.md`）；本次工作未删除、未修改 V0.1 任何内容。 |
| 16 | 2026-09-19 | 写入与提交 ACCESS 补记（本次） | `ACCESS.md` | workspace-write + git | 补记序号 9–15 的行为；随后提交为 M0 收尾提交。 |
| 17 | 2026-09-19 | **提权**创建开发分支 | `ETMMS_V1.0`：`git checkout -b develop`；查询 uv 可用 Python 版本 | require_escalated | 分支策略 `main`（基线）/ `develop`（日常开发）已就位。 |
| 18 | 2026-09-19 | 写入后端工程与核心骨架 | `backend/pyproject.toml`、`README.md`、`app/{config,main}.py`、`app/core/{clock,logging,exceptions}.py`、`app/models/*`、`app/repository/{database,migrations}.py` | workspace-write | 分层与职责遵循 `_SPEC/07`；全部注释为简体中文。 |
| 19 | 2026-09-19 | **提权**安装后端依赖（uv） | `uv sync --python 3.14` → `backend/.venv`（fastapi / uvicorn / sqlalchemy / alembic / pydantic / pypdf / pytest / ruff / pyinstaller 等 40+ 包） | require_escalated（网络 + uv 缓存在沙箱外） | 虚拟环境建在项目内，**未改动全局 Python**。耗时约 20 分钟（首次下载）。 |
| 20 | 2026-09-19 | **提权**PyInstaller 兼容性实测 | 生成 `build/pyinstaller_smoke/`（临时冒烟工程，已被 .gitignore 排除），打包并运行成功 | require_escalated | 结论：PyInstaller 6.22.3 在 Python 3.14.4 上可用（含 sqlite3）；据此**锁定 Python 3.14**。 |
| 21 | 2026-09-19 | **提权**生成并执行数据库迁移 | `migrations/`（env.py、script.py.mako）、`alembic.ini`、首个迁移 `7d4fbd959d06`；`uv run alembic upgrade head` | require_escalated | 过程中修正三处问题：`alembic.ini` 需纯 ASCII（GBK 读取）、env.py 需先建目录、mako 模板不能输出模块文档字符串。 |
| 22 | 2026-09-19 | **提权**安装前端依赖（npm） | `frontend/node_modules`（React 19 / Vite / TypeScript / oxlint / vitest / testing-library / jsdom，共 110+ 包） | require_escalated（网络） | `package.json` 为手写（非脚手架生成），依赖版本经 npm 解析。 |
| 23 | 2026-09-19 | 写入前端工程与组件库 | `frontend/`：配置文件、`src/styles/*`、`src/components/*`（14 个组件）、`src/pages/KitchenSink.tsx`（组件库自检页）、组件测试 2 份 | workspace-write | 零 inline style；全部样式取自 `tokens.css`。 |
| 24 | 2026-09-19 | 写入工程脚本 | `scripts/dev.py`、`scripts/build.py`、`scripts/check_docs.py` | workspace-write | `check_docs.py` 为 Token 使用率与模板覆盖的自查门禁。 |
| 25 | 2026-09-19 | **提权**联网获取 Chrome 配色权威来源 | 自 jsDelivr 镜像获取 Chromium 源码 `ui/color/ref_color_mixer.cc`（18.5 KB）至系统临时目录 | require_escalated（网络） | 用于校准 UI Token；`chromium.googlesource.com` 与 GitHub raw 在此网络不可达，gitee 镜像返回 403，最终 jsDelivr 可用。**仅为读取，未写入项目外任何位置。** |
| 26 | 2026-09-19 | 运行检查与构建（提权） | 后端 `ruff check`（全绿）、`pytest`（3 passed）；前端 `npm run build`（通过）、`npm test`（5 passed）、`npm run lint`（无告警）；`python scripts/check_docs.py`（3/3 通过） | require_escalated | 自查过程中发现并删除零使用 Token `--etmms-font-mono`。 |
| 27 | 2026-09-19 | **提权**启动后端服务并截图验证 | 后端 127.0.0.1:8080；浏览器截图 3 张（M1 界面） | require_escalated | 验证 Chrome/Material 3 视觉落地；截图过程发现"行式设置项控件列被裁切"缺陷并已修正；服务已停止，端口已释放。 |
| 28 | 2026-09-19 | 更新文档并提交 M1 | `UI.md`（校准记录 + 附录 B）、`_SPEC/08`（M1 过门结果）、`CHANGELOG.md`、本文件 | workspace-write + git | M1 收尾提交见 git log。 |
| 29 | 2026-09-20 | GitHub 推送前置核查（只读 + 联网） | 本地 git 远程/分支/账号配置、`gh` 可用性、代理配置与端口、仓库体积；联网探测 `github.com` / `api.github.com` / `gitee.com` | 只读 + require_escalated（联网探测） | 结果：无远程、无 gh、无代理配置；`github.com` 可达（HTTP 200，约 8.7 秒）、本机 7890 端口有代理在监听；仓库 `.git` 6.8 MB（其中甲方材料约 7 MB）。 |
| 30 | 2026-09-20 | **提权重写 Git 历史，移除甲方材料与医学依据** | `git filter-branch --index-filter`（按路径清单移除 `_DEV/甲方材料/原件`、`_DEV/医学依据`）+ `git gc --prune=now` | require_escalated | 按 Lifan 决策（仓库不含甲方材料与指南 PDF）。**副作用：filter-branch 重写后工作区中这 6 个文件被一并删除**；清理后已确认历史中不再包含任何材料文件，仓库体积由 6.8 MB 降至 **0.3 MB**。 |
| 31 | 2026-09-20 | 从原始位置恢复被删除的材料（读工作区外 + 写工作区） | 自 `C:\Users\lifan\Desktop\CGM\` 与 `C:\Users\lifan\Desktop\` 复制 3 份甲方原件与 3 份依据 PDF 回 `_DEV/` | 只读外部 + workspace-write | 6 个文件全部恢复并逐一核对大小（0.04–5.90 MB）；桌面源文件保持原样未动。**这是一次由我引发的意外删除，已完整恢复，无数据丢失。** |
| 32 | 2026-09-20 | 更新忽略规则与目录说明 | `.gitignore`（新增 `_DEV/甲方材料/原件/`、`_DEV/医学依据/`）、`_DEV/README.md`（材料本地保留、新环境获取方式） | workspace-write | 已用 `git check-ignore -v` 验证两条规则生效。 |
| 33 | 2026-09-20 | 设置中文文件名显示 | `git config core.quotepath false`（仅本仓库） | 本地配置 | 改善 `git status`/`git log` 中中文文件名的可读性。 |

> **提交哈希变更说明（2026-09-20）**：序号 14、15、28 中记录的提交哈希（`784da79` / `a31783c` / `96dce58`）
> 因序号 30 的历史重写而失效。重写后的等价提交为：M0 基线 `e217f46`、ACCESS 补记 `3932167`、M1 工程基线 `52d1902`。
> 三笔提交的**内容**与重写前一致，仅去掉了甲方材料与依据 PDF。

---

## 二、当前授权范围（Lifan 授予，2026-09-19）

| 授权项 | 范围 | 约束 |
| --- | --- | --- |
| 文件写入 | `D:\LifanDataDeepSeek\ETMMS_V1.0` 全部读写 | 全部新产出落在 V1.0 内 |
| 只读访问 | V0.1 工作区、桌面甲方材料 | **不得删除、不得修改 V0.1 任何成分** |
| 联网 | 允许 | 用于查阅 Chrome/Material 3 视觉规范、依赖安装等 |
| Skill 安装 | 允许（需逐次确认） | 正式安装技能前告知 Lifan |
| 提权执行 | 逐次审批 | 沙箱内无法完成的操作（uv、vite、打包）走提权审批 |

---

## 三、修订记录

| 版本 | 日期 | 修订内容 |
| --- | --- | --- |
| v1.0 | 2026-09-19 | 建立 V1.0 行为日志，补记本次会话已完成的行为（序号 1–8）；后续行为继续追加 |
