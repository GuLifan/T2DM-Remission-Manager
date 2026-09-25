# HANDOVER.md — ETMMS V1.0 项目交接说明

> **这是给"接手这个项目的 AI Agent"看的文件**，不是给医生看的用户文档。
> **交接日期**：2026-09-24｜**交接人**：上一个 AI Agent（Codex/DeepSeek V4.1 Flash）
> **项目**：早期2型糖尿病缓解管理软件（ETMMS），工作区 `D:\LifanDataDeepSeek\ETMMS_V1.0`
> **协作人**：Lifan（项目负责人 / 代码学生）。**先读第 9 节"工作方式约定"，再动手**——他有一套明确的协作规则。

---

## 0. 接手后先做这 6 件事（按顺序）

```bash
# 1) 看状态：分支、未推送提交、工作区是否干净
cd D:\LifanDataDeepSeek\ETMMS_V1.0
git branch -vv && git status --short && git log --oneline -n 12

# 2) 通读规范（顺序很重要）
#    README.md → UI.md → _SPEC/README.md → _SPEC/01 → _SPEC/09 第五节 → _SPEC/06 第七节

# 3) 把服务跑起来（后端 8088 / 前端 5173）
#    测试账号需要全流程入口时，先在当前 PowerShell 设置：$env:ETMMS_TEST_MODE='true'
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8088   # 需要提权（见 5.6）
cd frontend && npm run dev                                              # 另一个终端

# 4) 跑一遍质量基线，确认环境正常
cd backend && uv run pytest -q -p no:warnings    # 期望 176 passed
cd frontend && npm test                          # 期望 30 passed / 9 files
python scripts\check_docs.py                     # 期望 4/4

# 5) 看数据里有什么
#    账号：admin（正式管理员兼测试账号，密码由 Lifan 保管）；doctor 已停用
#    患者：3 位演示患者（MRN-DEMO-001 / 002、ZY010000001）

# 6) M6-A/B/C/D 已完成；进入 M7 前核对已批准方案、36/36 候选及医学复核边界
git diff --stat
#    重点读 _SPEC/11 第十六节、_SPEC/07 第十六节、_DEV/依据索引表_待填写_v1.0.csv
```

---

## 1. 一句话认识这个项目

**给门诊医生的 2 型糖尿病（T2DM）缓解管理"导航仪"**：患者现在在哪一步 → 医生要判断什么 → 系统给提示和日期 → **医学结论由医生签**。

系统只做四件事：**算日期、给提醒、拦非法操作、记可追溯的事件流水**。
系统**明确不做**：不预测缓解概率、不用病程/BMI/HbA1c/胰岛素/C 肽做准入、不自动停药减药、不自动确认缓解。

**六个流程单元 + 九个状态**（`backend/app/domain/states.py`）：

| 单元 | 名称 | 状态 |
| --- | --- | --- |
| — | 常规糖尿病综合管理 | ST00 |
| 1 | 60秒缓解预评估 | ST10 |
| 2 | 完整评估并形成主动管理计划 | ST20 |
| 3 | 阶段复评与治疗调整 | ST31（血糖稳定）/ ST32（缓解诱导） |
| 4 | 缓解观察期 | ST40（**系统自动进入，无医生点击**） |
| 5 | 缓解判定 | ST50 |
| 6 | 缓解后复评 | ST60 |
| — | 关闭 T2DM 缓解路径 | ST99（终态） |

**技术栈**：后端 Python 3.14 + FastAPI + SQLAlchemy + SQLite（Alembic 迁移）；前端 React 19 + TypeScript + Vite；虚拟环境在 `backend/.venv`（**不改动全局 Python**）；打包用 PyInstaller（已实测可用）。

---

## 2. 临床红线（写代码前必读，越界即验收不通过）

1. **不新增医生临床节点**；状态、标签、自动规则不得伪装成新临床步骤。
2. **不得**把病程、BMI、HbA1c、胰岛素、C 肽、ABCD 工具转成刚性准入/排除条件。
3. 不得把"病程长 / BMI 正常 / 用胰岛素 / HbA1c 高 / C 肽缺失"自动判为不适合缓解。
4. 急性安全、分型存疑、资料缺失只是**暂缓原因**（可并存），不是与三类结论并列的永久状态。
5. **不自动停药减药**；不为获得缓解标签提示停用心肾/体重获益药物。
6. 不在多个页面重复收集病程、BMI、分型、C 肽、并发症（**一次录入，后续只更新变化**）。
7. **没有"停药确认页面"，没有"进入观察期"按钮**——停药后系统自动进入 ST40。
8. 不得把"治疗下血糖达非糖尿病范围"写成已缓解 / 缓解失败 / 必须停药。
9. 不自行设定指南未支持的医学阈值与固定时间；**存疑一律进 `_SPEC/06` 问题清单**。
10. 关键临床结论必须由医生确认；**前台只出现自然语言**，不出现状态代码（STxx）、规则 ID（E1-B01）、字段 ID（F001）。

> 这 10 条的权威出处是 `_SPEC/01` 第六节与《临床流程锁定稿》，遇到冲突**以锁定稿为准**。

---

## 3. 文档地图与"谁说了算"

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `README.md` | 项目说明：定位、目录、启动、打包、开发约定 | 工程总览 |
| `UI.md` | **UI 与代码注释的唯一真源**；Token 表在 §2，信息层级在 §1.3–1.9 | Lifan 已手工改过 4 处（年龄/科室、红色必填星号、底部状态栏、`MAPPING.md` 引用） |
| `_SPEC/01–05` | 临床内核：目标边界 / 功能需求 / 状态机 / 字段与模板 / 用户故事与 3 个锁定病例 | **医学内容不得改动** |
| `_SPEC/06` | 问题清单与裁决记录（含 Q001–Q007 实现约定）；第七节含第二轮裁决 | 存疑进这里 |
| `_SPEC/07` | 技术架构与数据模型；**第十六节是第二轮技术影响评估** | 改数据模型前必读 |
| `_SPEC/08` | 实施计划与交付验收；**第八节是三批实施建议与过门条件** | 排期看这里 |
| `_SPEC/09` | 前端体验审阅：**61 条问题**（第五节 17 条是 2026-09-23 新增；5.3 是已定稿的科室清单） | Lifan 已审定；第一、二批已回填 |
| `_SPEC/10` | UI 规范修订提案：UI-R1…UI-R10 | Lifan 已审定；第一批相关项已落地 |
| `MAPPING.md` | 临床规则 → 代码 → 测试映射清单（**全大写文件名**） | 改临床逻辑必须同步 |
| `ACCESS.md` | **Agent 高权限行为日志**（每次提权/写库/联网都要追加） | 非用户文档 |
| `_DEV/` | 甲方材料原件 + 医学依据 PDF + 历史参考 | **只读，不改** |

**权威顺序（冲突时）**：《临床流程锁定稿》＞ `_DEV/甲方材料/原件` ＞ `_SPEC` ＞ `UI.md`（UI 领域内 `UI.md` 最高）＞ 代码。

> ⚠️ **命名约定**：Lifan 要求**文件名全大写**（他手工把 `mapping.md` 改成了 `MAPPING.md`）。新建根目录文档请用大写名。

---

## 4. 当前进度与状态（2026-09-24 核实）

### 4.1 里程碑

| 里程碑 | 状态 | 内容 |
| --- | --- | --- |
| M0 规范基线 | ✅ | `_DEV` 材料归位、`UI.md` 重写为 Chrome/Material 3、`_SPEC` 01–08 |
| M1 工程基线 | ✅ | uv 工程、Alembic、`core/`、前端脚手架与 14 个组件、3 个脚本、Token 校准 |
| M2 数据与账号 | ✅ | scrypt 密码、HMAC 会话、登录防护、患者档案接口、审计日志 |
| M3 临床内核 | ✅ | 领域层单一数据源、6 个纯函数服务、3 病例端到端、锁定文案逐字冻结 |
| M4 接口层 | ✅ | 13 个流程端点 + 3 个领域端点、事件与审计同事务、幂等、入口守卫 |
| M5 前端成品 | ✅ | 登录/患者列表/工作台 + 6 个流程页面（**但体验问题见 `_SPEC/09`**） |
| 第二轮第一批 | ✅ | 安全测试模式、账号级模拟日期、测试患者全流程入口、TaskPanel、`MAPPING.md` 命名修正 |
| 第二轮第二批 | ✅ | 开放注册、患者档案扩展、69 科室、xlsx/csv 导入与完善门禁、结构化录入、BMI、日期/布局/页脚 |
| 第二轮第三批 | ✅ | 正式管理员、患者责任归属与转移、普通医生只读边界、阶段复评测量、患者搜索/到期排序；完整 Gate 与浏览器验收通过 |
| M6 依据检索库 | ✅ | 四来源 684 分块、接口/审计、真实前端抽屉及 36/36 条规则依据候选均完成；候选仍待医学复核 |
| M7 打包与交付 | 🟡 方案待审 | `_SPEC/12` 已完成约束核对与待审批方案；尚未授权实施 |

### 4.2 质量基线（实测值，接手后请复跑确认）

| 项 | 命令 | 期望 |
| --- | --- | --- |
| 后端测试 | `cd backend; uv run pytest -q -p no:warnings` | **176 passed** |
| 后端静态检查 | `uv run ruff check .` | All checks passed |
| 前端测试 | `cd frontend; npm test` | **30 passed / 9 files** |
| 前端构建 | `npm run build` | tsc + vite 通过 |
| 前端 lint | `npm run lint` | 无告警 |
| 文档一致性 | `python scripts\check_docs.py` | **4/4**（61 个 Token 全部有使用点；36/36 候选保持待复核） |

### 4.3 Git 状态（**重要**）

```
develop  [origin/develop]             ← M6 方案与 M6-A/B/C/D 已按 Lifan 授权推送
main     1fc7286  [origin/main]      ← 按 Lifan 指示保持不动
```

- `develop` 已按 Lifan 批准推送；第二轮三批与 M6-A/B/C/D 均已在远程。最终提交号以实时 `git branch -vv` 为准。
- **当前禁止事项**：不要把 `develop` 合并到 `main`，直到 Lifan 另行明确批准。
- ⚠️ **本机 IP 在每天 19:00 之后无法连接 GitHub**——推送安排在 19:00 前，超时不要反复重试。

### 4.4 原有 Token 红灯已关闭

```bash
python scripts\check_docs.py
[PASS] Token 定义一致（61 个）
[PASS] Token 使用率（61 个）
[PASS] 输出模板计数
[PASS] 依据索引候选（36/36，统一待医学复核）
```

`TaskPanel` 已在第一批实现并实际使用 `--etmms-text-task-title`（18px 任务标题）；施工标记已归零。以后若再出现未使用 Token，按真实门禁失败处理，不再视为预期红灯。

### 4.5 运行环境现状

- **服务当前未运行**（8088 与 5173 都已停止），接手后按第 0 节启动。
- 端口约定：后端 **8088**（8080 已分配给 Lifan 的其他任务，**不要改回 8080**），前端 **5173**。
- 数据库：`data/runtime/etmms.db`（**已被 .gitignore 排除**；当前迁移头 `a1c9e7f2d4b8`；删掉即自动重建并跑迁移）。
- 账号：`admin` 为启用中的正式管理员且保留测试能力；密码由 Lifan 自行保管，文档不记录。旧 `doctor` 仍停用且密码作废（原因见 8.10）。第三批临时 QA 账号均已停用并使密码不可用。

---

## 5. 代码地图与关键机制

### 5.1 后端（`backend/app`，55 个 .py）

| 层 | 文件 | 职责 |
| --- | --- | --- |
| 领域层（**单一数据源**） | `domain/states.py` | 9 个状态 + 中文名 + 6 个流程单元 |
| | `domain/enums.py` | 字段允许值（与最小字段映射一致） |
| | `domain/templates.py` | **30 条锁定文案 + 3 条 SYS 提示**（改动必须走变更控制） |
| | `domain/branches.py` | **阶段复评分支优先级表**（失控 > 治疗下达标 > 停药 > 常规）+ 被忽略分支说明 |
| | `domain/transitions.py` | **合法状态转换表 + `validate_transition()` + `dead_end_states()`** |
| 服务层（**纯函数**） | `services/pre_assessment.py`、`full_assessment.py`、`phase_review.py`、`observation.py`、`remission_judge.py`、`post_remission.py` | 6 个流程单元的临床决策；**不读系统时间、不碰数据库** |
| | `services/defaults.py` | 12 周复评间隔、随访节奏（唯一来源） |
| 接口层 | `api/auth.py`、`patients.py`、`pre_assessment.py`…`post_remission.py`、`domain_data.py`、`test_support.py` | 路由、鉴权、**事务提交**；测试入口独立隔离 |
| | `api/flow_common.py` | **`get_patient_or_404` / `require_state` / `record_outcome`**：状态守卫 + 事件与审计**同事务** + 幂等 |
| 数据层 | `repository/users.py`、`patients.py`、`events.py`、`audit.py`、`database.py`、`migrations.py` | 只 `add`+`flush`，**不 commit**；`events` 模块**刻意不提供更新/删除** |
| 基础能力 | `core/security.py`（scrypt 密码 + HMAC 会话令牌）、`core/clock.py`（可注入时钟）、`core/test_mode.py`（三重守卫 + 有效日期）、`core/exceptions.py`、`core/logging.py` | |
| 工具 | `utils/date_utils.py` | 日历月加法（**月末钳位**）、最早可判定日期（取 MAX） |
| 迁移 | `migrations/versions/` | 3 个迁移：初始结构、账号加固、测试模式与模拟日期 |

### 5.2 前端（`frontend/src`，48 个 TS/TSX/CSS 源文件）

| 目录 | 内容 |
| --- | --- |
| `components/` | 原 14 个组件 + `DateControl` / `TaskPanel` / `TestToolsPanel`；测试入口只由后端能力与测试患者标记共同开放 |
| `pages/` | `LoginPage`（含首次创建账号）、`PatientListPage`、`PatientWorkspacePage`（壳层）、`flow/` 下 8 个流程页面、`KitchenSink`（组件自检页，路由 `/dev/kitchen-sink`） |
| `api/` | `client.ts`（15 秒超时、AbortSignal 取消、401 清会话、自动 `request_id`）、`endpoints.ts` |
| `styles/` | **`tokens.css`（Token 唯一来源，与 `UI.md` §2 逐字对应）**、`base.css`、`components.css`、`pages.css` |
| `hooks/` | `useAsync.ts`（加载/错误/取消统一处理） |

### 5.3 六个必须知道的设计机制（改动前先读）

1. **状态机是唯一真源**：任何跳转都要过 `validate_transition()`；未登记的转换一律拒绝（连服务层内部也会自查一遍）。
2. **分支优先级在后端**：前端通过 `GET /api/domain/branches` 拿分支表渲染，**不得在前端硬编码**；后端还会返回"被忽略的分支与原因"（禁止静默丢弃医生已填内容）。
3. **锁定文案有冻结测试**：`backend/tests/test_templates_frozen.py` 会把代码里的 30 条文案与 `_DEV/甲方材料/md派生/临床流程实现表_输出模板.md` **逐字比对**，改写文案测试立刻红。
4. **事件 + 审计同事务**：一律走 `api/flow_common.record_outcome()`；不要在别处单独 `db.commit()` 写临床事件。
5. **幂等**：写接口带 `request_id`，重复提交返回 409 且不产生第二条事件。
6. **时间靠注入**：服务层接收 `today` 参数；接口层统一通过 `effective_today_for_patient()` 取账号有效日期。模拟日期写真实患者时后端直接拒绝，事件同时保存 `simulated_date`，不得绕回 `system_clock.today()` 破坏该边界。

### 5.4 门禁脚本 `scripts/check_docs.py`

三项检查：① `UI.md` 与 `tokens.css` 的 Token **定义一致**；② **Token 使用率**（定义即须使用，未使用即失败）；③ 输出模板覆盖（以甲方原件为基准）。**合并前必须跑通**。

### 5.5 其他脚本

- `scripts/dev.py`：一键启动前后端（后端 8088 / 前端 5173），Ctrl+C 停止。
- `scripts/build.py`：前端构建 → 复制到 `backend/app/static` → PyInstaller `onedir` → `release/`。

### 5.6 关于提权（本机沙箱）

这份交接的会话里，**沙箱只允许写 `ETMMS_V0.1_dev_260818`，`V1.0` 是只读的**。要写 V1.0（改代码、提交 git、写数据库）都必须带 `require_escalated` 请求批准；`uv`、`npm`、`git` 的写操作也需要提权。接手后如果工作区可写，就不必每次提权。

---

## 6. 环境与命令速查

```bash
# 启动（两个终端）
cd backend   && uv run uvicorn app.main:app --host 127.0.0.1 --port 8088
cd frontend  && npm run dev                    # http://localhost:5173（/api 代理到 8088）

# 质量基线
cd backend   && uv run pytest -q -p no:warnings && uv run ruff check .
cd frontend  && npm test && npm run lint && npm run build
cd ..        && python scripts\check_docs.py

# 数据库
#   开发库：data/runtime/etmms.db（删掉即重建并自动迁移）
#   迁移：cd backend && uv run alembic revision --autogenerate -m "说明" && uv run alembic upgrade head

# 依赖（虚拟环境在项目内，绝不装到全局）
cd backend && uv sync
cd frontend && npm install

# 打包（M7 用）
python scripts\build.py
```

**已知环境限制**

| 限制 | 说明 |
| --- | --- |
| GitHub 19:00 后不可达 | 推送安排在白天；超时别反复重试 |
| 本机 VPN 在 7890 端口（时开时关） | 抓取境外资料需要它；**境内站点也可能被 WAF 拦**（见 8.6） |
| httpx 会走系统代理 | **项目内脚本访问本机后端必须 `trust_env=False`**（见 8.4） |
| Windows 文件系统大小写不敏感 | 改名后脚本"看着还能跑"，但在 Linux/CI 会挂（见 8.5） |
| Alembic 读配置用系统编码（GBK） | `alembic.ini` **必须纯 ASCII**（见 8.1） |

---

## 7. 待办与优先级（接手后的工作清单）

### 7.1 当前状态：M6-A/B/C/D 已完成，M7 方案待 Lifan 审定

Lifan 已批准 `_SPEC/11` 的五项 M6 决议，并依次授权 M6-A/B/C/D。M6-A 已完成迁移 `a1c9e7f2d4b8`、四来源导入与 684 个分块；M6-B 已完成状态/检索接口、登录鉴权、完整性门禁和隐私审计；M6-C 已把 `EvidenceDrawer` 接到真实接口；M6-D 已生成 36/36 条可追溯候选并增加复核状态门禁。全部候选仍为“待 Lifan/医学负责人复核”，不是已确认医学依据。后端 176 项、前端 30 项、文档 4/4 及隔离副本真实浏览器 Gate 均通过。M7 的当前入口是 `_SPEC/12`：只完成了约束核对与实施方案，代码、打包和交付物均未启动。

### 7.2 三批实施计划（`_SPEC/08` 第八节）

| 批次 | 内容 | 目的 |
| --- | --- | --- |
| **第一批（测试可用性）** | ✅ UX-47 测试账号全流程测试能力 + UX-58 日期模拟 + UX-46 命名修正 + TaskPanel | 已完成（`3576ebd` 约束；`5ef8026` 实现） |
| **第二批（档案与录入）** | ✅ UX-48/49 患者信息字段与术语、UX-45 注册、UX-50 批量导入、UX-52 病程、UX-53 身高体重与 BMI、UX-54 数值与单位、UX-56 下拉与药物、UX-57 日期格式、**UX-61 内容居中** | 已完成（`d9c22f6` 约束；`c2f15df` 后端；`c89c8c5` 前端） |
| **第三批（流程与权限）** | ✅ UX-55 指标可更新、UX-59 列表搜索排序、UX-60 账号隔离 | 已完成（`d04da05` 后端；`40f03b5` 前端；`8ea608e` 浏览器修复；Gate 见 `_SPEC/08` 8.8） |

每批的过门条件见 `_SPEC/08` 8.2；**交付前必做**见 8.3（关闭测试能力但保留正式管理员、核验测试接口 403、清理测试数据）。

### 7.3 第三批已实现的边界

第三批 T3-01…T3-06 已由 Lifan 审定并实现：正式 `admin` 角色与测试标记分离；普通医生只写当前归属患者；只有管理员可转移归属；阶段复评更新身高/体重但不建趋势表；列表默认到期优先并支持五个字段双向排序。权威细节见 `_SPEC/06` 第八节、`_SPEC/07` 16.6 与 `_SPEC/08` 8.8。

### 7.4 医学复核与 M7

- **医学复核**：`_DEV/依据索引表_待填写_v1.0.csv` 已有 36/36 条候选，全部待 Lifan/医学负责人逐行复核；未经复核不得标记为确认依据。
- **M7 打包与交付**：`_SPEC/12` 已记录十项待审批决议。`scripts/build.py` 已写好但**未跑过完整流程**；现脚本还未显式打入 Alembic 资源，也没有托盘退出、正式文件日志或干净环境 Gate。PyInstaller 6.22.3 + Python 3.14.4 **已完成早期兼容性烟测**；交付物尚未生成。

### 7.5 一个待补的质量项

**Playwright 自动化 E2E 没有做**（当时网络下载浏览器内核失败）。M5 用的是"真实浏览器人工走查 + Vitest 页面级测试"替代。若条件允许，建议补上（`_SPEC/08` M5 有说明）。

---

## 8. 坑与教训（我踩过的，逐条记录，别重复踩）

### 8.1 `alembic.ini` 必须纯 ASCII

Alembic 用**系统 locale 编码**（这台机器是 GBK）读配置文件，中文注释会导致 `UnicodeDecodeError`。已改为英文注释并在文件头注明原因。

### 8.2 `migrations/script.py.mako` 不要写模块文档字符串

模板里的文档字符串会被写进生成的迁移文件开头，导致 `from __future__` 不在最前 → `SyntaxError`。现已改用 mako 注释（`##`）。

### 8.3 `git filter-branch` 会删掉工作区文件（**我造成过一次数据丢失**）

为把甲方材料从历史中移除，我用了 `git filter-branch --index-filter`。重写后**工作区里那 6 个文件被同时删除**（我事先没预料到）。因为源文件在 Lifan 桌面还在，我全部恢复了（6/6 校验通过），并记进 `ACCESS.md` 第 31 条。
**教训：任何历史重写前先备份工作区。**

### 8.4 httpx 会走 Windows 系统代理 → 访问本机后端返回 502

我一度误判"密码被改过"，实际是请求根本没到后端。**项目内脚本访问 `127.0.0.1` 一律加 `trust_env=False`**。

### 8.5 Windows 大小写不敏感会掩盖问题

`mapping.md` 改名 `MAPPING.md` 后，`check_docs.py`（写的仍是小写）**在本机照常通过**，但在 Linux/CI 上会找不到文件。UX-46 要改的就是这个。

### 8.6 该院官网对非浏览器请求极不友好

抓科室清单时：官网 HTTP 返回 **412**（WAF）、HTTPS **证书名不匹配**、百度百科 **403**、Bing 无论怎么限定关键词都返回无关缓存页、百度要滑块验证。
**结论：科室清单最后是 Lifan 手工提供官网导航原文、我整理成 69 条（`_SPEC/09` 5.3）。以后需要该院资料，直接请他给原文最省事。**

### 8.7 原生日期控件的显示格式改不了

`<input type="date">` 在中文 Chrome 下显示"年/月/日"，**由浏览器 locale 决定，CSS 改不了**。要 `yyyy/mm/dd` 只能改成文本输入 + 校验（`_SPEC/09` UX-57 已记录取舍）。

### 8.8 V0.1 的一个潜伏缺陷（已修）

V0.1 的"急性安全稳定化后快速建档"跳 `ST10→ST31`，但**该转换不在它的状态矩阵里**，接口一调用就抛非法跳转（且无测试覆盖）。V1.0 已补齐 `E1-B02-STABILIZED` 并有接口测试。

### 8.9 V0.1 的状态漂移缺陷（已修，别改回去）

V0.1 只在"有药"时写 `has_glucose_lowering_drug=True`，停药后旧值残留 → 缓解判定被陈旧状态**错误阻断**。V1.0 在**每次复评都无条件刷新**用药状态（`api/phase_review.py`），改动这里要格外小心。

### 8.10 账号**不能物理删除**

`events.operator_id` 有外键指向 `users.id`，事件流水是临床可追溯性的基础。Lifan 要求"删除 doctor 账号"时，我采用**停用 + 作废密码**（`is_active=0`、`password_hash='!revoked'`），并在 `ACCESS.md` 说明原因。**新账号要删也只能这样处理**——除非连整个开发库一起重建。

### 8.11 迁移新增非空列会打挂既有测试

给 `users` 加 `failed_login_count NOT NULL` 后，M1 用裸 SQL 插账号的冒烟测试直接完整性错误。加非空列要给默认值或同步改测试。

### 8.12 测试会话的身份缓存

接口层用**另一个数据库会话**，测试里读接口写入的新状态前必须 `db_session.expire_all()`，否则拿到过期快照（我因此误判过一次布局问题）。

### 8.13 JavaScript 日期转 ISO 的时区回退

在中国时区把本地零点 `Date` 直接调用 `toISOString()`，日期可能回退到前一天。`DateControl` 已改为用 `Date.UTC(year, month - 1, day)` 生成提交值，并有前端测试覆盖。后续日期控件不要恢复为本地零点转 ISO 的写法。

---

## 9. 工作方式约定（**与 Lifan 协作的规则，务必遵守**）

1. **称呼他 Lifan**。
2. **回答前先问问题**：一次只问一个或一组问题，根据回答继续追问，**直到有 95% 把握理解他的真实需求**；然后给方案，**经他批准才能执行**。
3. **SPEC 先行**：先改规范（`_SPEC`／`UI.md`），再改代码；实现与规范不一致时**二者取一**，并把差异记入 `_SPEC/06`。UI 领域内 `UI.md` 是唯一真源，且**每个 Token 都必须有实际使用点**（`check_docs.py` 会查）。
4. **临床规则原样冻结**：锁定稿是唯一临床主依据；**不得自行改动医学内容**，存疑写进 `_SPEC/06` 问题清单，由他裁决。
5. **代码注释用简体中文**，遵循 `UI.md` 第三部分的文件头/函数块/逐行注释模板。
6. **每个高权限行为记入 `ACCESS.md`**（提权、写库、联网、批量写入、安装依赖…），行为发生后立即追加。
7. **每日节奏**：当天工作提交到 `develop` → **次日**经他审阅后快进 `main` 并推送两个分支；**19:00 前推送**（之后 GitHub 不可达）。
8. **文件名大写**（他 2026-09-24 明确要求）；根目录文档用 `README.md` / `UI.md` / `MAPPING.md` / `ACCESS.md` / `CHANGELOG.md` 这类命名。
9. **Python 依赖装进项目内虚拟环境**（`backend/.venv`），**绝不改他的全局环境**。
10. **接手的这份文件也要维护**：如果你做了重大结构变更，回来更新它。

---

## 10. 交接清单

### 10.1 已定稿、**不要改**

- `_SPEC/01–05` 的**医学内容**（继承自 V0.1 的锁定内核）；
- `backend/app/domain/templates.py` 的 **30 条锁定文案**（有冻结测试盯着）；
- `domain/transitions.py` 的**合法转换矩阵**（改必须同步 `_SPEC/03` + 测试）；
- `_SPEC/09` 5.3 的**科室清单 69 条**（已按"排除医技+去重+拼音排序"定稿，默认选中「内分泌科」）；
- `UI.md` 1.3–1.9（信息层级与视觉焦点）与 D1–D5 决议（正文 16px / 主标题 24px / 任务面板常驻 / 时间线降级 / 必填硬约束）。

### 10.2 下一批开始前核对

- `_SPEC/09` 第五节（UX-45…UX-61）的“你的修改”与第一批处理结论；
- `_SPEC/06` 第七节（R2-01…R2-14）的最新裁决状态；
- `_SPEC/10` 第八节（UI-R1…UI-R10）的已审定约束。

### 10.3 明确未完成的事

| 项 | 状态 |
| --- | --- |
| M6 依据检索库 | ✅ M6-A/B/C/D 工程收口完成；36/36 条候选待医学复核 |
| M7 便携版打包 | `_SPEC/12` 方案待审；脚本已写，未跑完整流程 |
| 交付物 xlsx（实现表 / 病例走查） | 未生成 |
| Playwright E2E | 未做（用人工走查 + Vitest 替代） |
| 第二批“档案与录入” | ✅ 已完成；Gate 见 `_SPEC/08` 8.6 |
| 第三批“流程与权限” | ✅ 已完成；迁移、自动化、浏览器验收与走查修复见 `_SPEC/08` 8.8 |

### 10.4 交付前的安全项（**别忘了**）

1. **关闭测试能力但保留正式管理员**：分发环境关闭测试模式，并清除正式管理员的 `is_test_account` 标记或停用独立测试账号；不得停用唯一 `role=admin`；
2. 确认测试后门接口（跳转任意状态 / 模拟日期）在关闭状态下返回 403；
3. 清理测试数据（演示患者、`source='debug'` 的事件）。

---

## 11. 交接备注

- 本项目从 V0.1（`D:\LifanDataDeepSeek\ETMMS_V0.1_dev_260818`，**只读参考，不得修改**）重写而来；V0.1 的缺陷清单、风险报告仍可作为背景材料。
- **不要参考** `D:\LifanDataClaudeCode\ETMMS260806`（更早的支线，Lifan 明确说"效果不佳，脱离它的干扰"）。
- 如果遇到与本文不符的地方：**以代码、`git log` 与 `ACCESS.md` 的实际记录为准**，并更新本文。

> 交接完毕。祝顺利。——上一个 Agent
