# 变更记录（CHANGELOG）

本项目版本号遵循 `vX.Y.Z`：X 为大版本（结构级变更），Y 为功能版本，Z 为修订版本。
V0.1 为历史版本（工作区 `ETMMS_V0.1_dev_260818`，只读保留，不再演进）；V1.0 为当前唯一在研版本。

## [Unreleased] — v1.0.0 开发中

### 新增（M1：工程基线）

- **后端工程**：`backend/` 使用 uv 管理项目内虚拟环境（`.venv`，不改动全局 Python）；Python 版本经实测锁定 **3.14**
- **配置与基础能力**：`config.py`（数据目录/数据库路径/端口/会话时长，便携版写用户数据目录）、`core/clock.py`（时钟注入，保证日期边界可测）、`core/logging.py`（结构化日志）、`core/exceptions.py`（业务异常 → 医生可读自然语言）
- **数据层**：SQLAlchemy 模型（`users` / `patients` / `events` / `audit_log` / `app_meta`）+ **Alembic 迁移**（首个迁移 `7d4fbd959d06`），启动时自动升级；SQLite 启用 WAL 与外键约束
- **事件与审计**：`events` 记录操作者、来源（医生/系统）、源与目标状态、规则 ID、输出文案、输入快照；`audit_log` 记录登录与全部写操作
- **前端工程**：React + TypeScript + Vite 脚手架；`styles/tokens.css` 与 `UI.md` 逐字一致；`styles/components.css` 以 BEM 类名实现全部组件样式
- **组件库（14 个）**：`PageHeader` / `ActionBar` / `SettingsRow` / `FieldRow` / `ChoiceGroup`（互斥分支：单选 + 优先级 + 禁用原因）/ `CheckboxGroup` / `ResultBanner` / `StatusBadge` / `SideNav` / `EvidenceDrawer` / `ConfirmDialog` / `EmptyState` / `ErrorBanner` / `LoadingBlock`
- **工程脚本**：`scripts/dev.py`（一键启动）、`scripts/build.py`（便携版打包流水线）、`scripts/check_docs.py`（Token 定义一致 / Token 使用率 / 模板覆盖自查）
- **测试基线**：后端 pytest 3/3（含外键约束验证）、前端 vitest 5/5（含互斥分支禁用原因）

### 新增（M0：规范基线）

- 建立 V1.0 工程骨架：`_DEV`（项目描述与甲方依据）、`_SPEC`（纲领性文件）、`backend`、`frontend`、`data`、`scripts`、`交付物`
- 归位甲方材料原件（临床流程锁定稿、学生首轮任务与联合交付要求、临床流程实现表）与医学依据材料（2 型糖尿病缓解中国专家共识、国际缓解共识、中国糖尿病防治指南 2024 版）
- 重写根目录 `UI.md`：以 Google Chrome 现行视觉体系（Material Design 3）取代原 macOS Liquid Glass 规范，并引入"Token 使用率自查"作为强制约束
- 建立根目录 `ACCESS.md`：记录 Agent 全部高权限行为，供开发者审计
- 编写 `_SPEC` 纲领：01 项目概述与目标边界 / 02 功能需求 / 03 业务规则与状态机 / 04 字段与输出模板 / 05 用户故事与验收标准 / 06 问题清单与裁决记录 / 07 技术架构与数据模型 / 08 实施计划与交付验收

### 变更

- 临床内核（9 状态、32 条规则、56 个字段、30 个 `OUT-*` + 2 个 `SYS-*` 锁定文案）自 V0.1 原样继承，医学内容不作任何改动
- 交付形态由"可点击低保真原型"升级为"完整成品"：便携版打包纳入验收项
- 依据来源以 `_DEV\甲方材料\原件` 与 `_DEV\医学依据` 为准（原件可信度高于工作区 md 派生版）
- UI 体系由 macOS Liquid Glass 改为 Google Chrome / Material Design 3；颜色 Token 已对照 Chromium 源码 GM3 参考调色板校准（15/18 逐字节一致）
- 删除零使用的 Token `--etmms-font-mono`（Token 使用率自查结果：60 个 Token 全部有使用点）

### 已知缺口

- 《规则映射表 v0.4》《原交接稿》未获取；依据核对以锁定稿 + 三份共识/指南 PDF 为准（记入 `_SPEC/06`）
- ~~打包工具对 Python 3.14 的支持需在 M1 实测~~ → M1 已实测通过（PyInstaller 6.22.3）

## [v0.1.0] — 2026-08-23（历史版本，已冻结）

见 `D:\LifanDataDeepSeek\ETMMS_V0.1_dev_260818\CHANGELOG.md`。
