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

### 新增（M2：数据与账号）

- **密码与会话安全**（`core/security.py`，仅用标准库）：scrypt 加盐密码哈希（参数随哈希存储，便于日后提高强度）；HMAC-SHA256 签名会话令牌（含签发/过期时间，密钥首次运行生成并落盘，避免重启踢人）
- **登录防护**：连续失败 5 次锁定 15 分钟；账号不存在与密码错误返回**同一句提示**（避免账号枚举）；停用账号拒绝登录
- **账号接口**（`api/auth.py`）：首次运行引导创建医生账号（无默认密码）、登录、登出、当前账号查询
- **患者档案接口**（`api/patients.py`）：建档（病历号唯一预检）、列表、详情、事件流水分页查询
- **数据访问层**（`repository/`）：users / patients / events / audit 四个模块；**事务边界由接口层掌握**，仓储只 add+flush；事件模块刻意不提供更新与删除接口
- **系统保留账号**：`__system__`（不可登录），供系统自动事件记录操作者
- **数据库迁移** `375fb4767e0a`：新增 `users.failed_login_count` 与 `users.locked_until`
- **测试**：新增密码/令牌安全测试、账号接口测试、患者档案与审计测试；后端 pytest 由 3 项增至 **24 项**

### 新增（M3：临床内核）

- **领域层（单一数据源）**：`domain/states.py`（9 状态 + 6 流程单元）、`domain/enums.py`（字段取值）、`domain/templates.py`（30 条锁定文案 + 2 条 SYS 兜底）、`domain/branches.py`（阶段复评分支优先级表）、`domain/transitions.py`（合法转换表 + 校验 + 无出口检查）
- **6 个临床服务（纯函数）**：`pre_assessment` / `full_assessment` / `phase_review` / `observation` / `remission_judge` / `post_remission`；时间由调用方注入，返回前强制校验状态跳转
- **日期与默认值**：`utils/date_utils.py`（日历月加法月末钳位、最早可判定日期 MAX 规则）、`services/defaults.py`（12 周复评间隔与随访节奏的唯一来源）
- **分支优先级落地**：阶段复评按"明显失控 > 治疗下达标用获益药 > 停用最后一种药 > 常规动作"裁决；**被覆盖分支必须返回原因**，互斥分支同时为真直接报错（修复 V0.1"停药日期被静默丢弃"的缺陷）
- **测试**：状态机矩阵与无出口检查、日期边界、六个服务全分支、3 个锁定病例端到端、四条红线回归、锁定文案与甲方原件逐字比对；后端 pytest 由 24 项增至 **133 项**

### 新增（M4：接口层）

- **13 个流程端点 + 3 个领域端点**：6 个流程单元全部接入；新增"重新发起预评估"入口（ST00→ST10）
- **共享骨架** `api/flow_common.py`：患者取用与状态守卫、结果落库、**事件与审计同事务**、幂等守卫
- **幂等**：请求携带 `request_id`，重复提交返回 409 与自然语言提示，不产生重复事件
- **只读语义修正**：缓解判定拆分为 `check`（纯查询，可反复调用、不落库）/ `route`（落库）/ `confirm`（医生确认），修正 V0.1 报告中记为 L5 的"核对接口带副作用"问题
- **领域导出**：`/api/domain/states`、`/flow-units`、`/branches`——前端按后端返回的分支优先级渲染，禁止自行硬编码
- **修复 V0.1 的潜伏缺陷**：其"急性安全稳定化后快速建档"接口跳转 `ST10→ST31`，但该转换不在 V0.1 的状态矩阵中，接口一旦调用即抛非法跳转；V1.0 补齐转换并加测试覆盖
- **测试**：新增接口层测试（主链路、病例3、入口守卫、只读性、幂等、事件与审计同事务）；后端 pytest 由 133 项增至 **146 项**

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
