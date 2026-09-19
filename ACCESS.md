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
