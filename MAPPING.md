# MAPPING.md — 临床规则 → 代码 → 测试 映射清单

> **版本**：v1.8｜**日期**：2026-09-24｜**状态**：M5 与第二轮三批完成；M6-A/B/C 已实施并通过验收
> **用途**：任一临床规则都能一路查到"锁定稿依据 → spec → 代码位置 → 输出模板 → 测试"。
> **维护规则**：修改任何临床逻辑时必须同步本表；Token 变更登记在 `UI.md` 附录 B，此处只登记"本版本 Token 变更事件"。

---

## 一、规则清单（临床含义 → 输出模板 → 服务层实现 → API → 测试）

> 服务层实现与测试已在 M3 回填；API 列待 M4（临床流程接口）接入后回填。

| 规则ID | 临床含义 | 输出模板 | 服务层实现 | API | 测试 |
| --- | --- | --- | --- | --- | --- |
| E1-B01 | 预评估：进入完整评估 | OUT-E1-ENTER | `services/pre_assessment.py::evaluate_pre_assessment` | 待 M4 | `tests/test_services_e1_e2.py` |
| E1-B02 | 预评估：急性安全暂缓（置顶） | OUT-E1-HOLD-ACUTE | 同上（暂缓优先级表 `_HOLD_PRIORITY`） | 待 M4 | 同上、`tests/test_locked_cases.py`（病例2） |
| E1-B03 | 预评估：分型存疑暂缓 | OUT-E1-HOLD-TYPE | 同上 | 待 M4 | 同上 |
| E1-B04 | 预评估：治疗背景不足暂缓 | OUT-E1-HOLD-DATA | 同上 | 待 M4 | 同上 |
| E1-B05 | 预评估：当前不启动 | OUT-E1-NOSTART | 同上（`_not_start`） | 待 M4 | 同上 |
| E2-B01 | 完整评估：启动＋血糖稳定 | OUT-E2-STABLE | `services/full_assessment.py` | 待 M4 | `tests/test_services_e1_e2.py` |
| E2-B02 | 完整评估：启动＋缓解诱导 | OUT-E2-INDUCTION | 同上 | 待 M4 | 同上 |
| E2-B03 | 完整评估：暂缓补充资料 | OUT-E2-HOLD | 同上 | 待 M4 | 同上 |
| E2-B04 | 完整评估：当前不启动 | OUT-E2-NOSTART | 同上 | 待 M4 | 同上 |
| E3-B01 | 复评：继续当前阶段 | OUT-E3-CONTINUE | `services/phase_review.py::_routine_action` | 待 M4 | `tests/test_services_e3_obs.py` |
| E3-B02 | 复评：调整方案或目标 | OUT-E3-ADJUST | 同上 | 待 M4 | 同上 |
| E3-B03/B04 | 复评：阶段互转（医生确认） | OUT-E3-SWITCH | 同上 | 待 M4 | 同上 |
| E3-B05 | 复评：结束主动管理 | OUT-E3-END | 同上 | 待 M4 | 同上 |
| E3-B06 | 复评：治疗下达标仍用获益药 | OUT-E3-ON-TREATMENT | `phase_review.py`（分支表 `domain/branches.py`） | 待 M4 | 同上、`test_locked_cases.py`（病例3） |
| E3-B07 | 复评：停最后一种药 → 自动观察期 | OUT-E3-OBS-ENTER | 同上 + `utils/date_utils.py::compute_earliest_judge_date` | 待 M4 | 同上、`test_locked_cases.py`（病例1） |
| E3-B08 | 复评：明显血糖失控 → 血糖稳定 | OUT-E3-ADJUST | 同上（优先级最高） | 待 M4 | 同上 |
| A1-B01 | 观察期：进入与最早判定日计算 | — | `services/observation.py`、`utils/date_utils.py` | 待 M4 | `tests/test_services_e3_obs.py`、`tests/test_date_utils.py` |
| A1-B02 | 观察期：未到期提示 | OUT-A1-WAIT | `observation.py::get_observation_status` | 待 M4 | 同上 |
| A1-B03 | 观察期：到期开放判定 | OUT-A1-DUE | 同上 | 待 M4 | 同上 |
| A1-B04 | 观察期：因高血糖退出 | OUT-A1-RESTART-HIGH | `observation.py::evaluate_medication_restart` | 待 M4 | 同上 |
| A1-B05 | 观察期：因获益用药退出 | OUT-A1-RESTART-BENEFIT | 同上 | 待 M4 | 同上 |
| E4-B01 | 判定：未到期阻断 | OUT-E4-NOT-DUE | `services/remission_judge.py::check_remission` | 待 M4 | `tests/test_services_e4_e5.py` |
| E4-B02 | 判定：仍用药阻断 | OUT-E4-ON-DRUG | 同上 | 待 M4 | 同上 |
| E4-B03 | 判定：客观条件核对 | OUT-E4-OBJECTIVE-MET | 同上（`_objective_conditions`） | 待 M4 | 同上、`test_locked_cases.py` |
| E4-B04 | 判定：医生确认缓解 | OUT-E4-CONFIRMED | `remission_judge.py::confirm_remission` | 待 M4 | 同上 |
| E4-B05 | 判定：暂不确认 → 定向复核 | OUT-E4-UNCERTAIN | 同上 | 待 M4 | 同上 |
| E4-B06 | 判定：未达标 → 返回事件3 | OUT-E4-NOT-MET | `check_remission` | 待 M4 | 同上 |
| E4-B07 | 判定：不可解释 → 复核（F041=否 返回 ST20） | OUT-E4-UNCERTAIN | `check_remission` | 待 M4 | 同上 |
| E5-B01 | 缓解后：维持 | OUT-E5-MAINTAIN | `services/post_remission.py` | 待 M4 | 同上 |
| E5-B02 | 缓解后：风险上升 | OUT-E5-RISK | 同上 | 待 M4 | 同上 |
| E5-B03 | 缓解后：获益用药不可评价 | OUT-E5-UNEVALUABLE | 同上 | 待 M4 | 同上 |
| E5-B04 | 缓解后：缓解终止 → 返回事件3 | OUT-E5-END | 同上 | 待 M4 | 同上 |
| E5-B05 | 缓解后：默认随访计划 | OUT-E5-FOLLOWUP | `services/defaults.py::next_followup_date` | 待 M4 | 同上、`tests/test_locked_cases.py` |
| SYS-E1-CLOSE | 兜底提示：分型复核为其他类型时关闭本路径（非锁定临床模板） | SYS-E1-CLOSE | `domain/transitions.py`（ST10→ST99） | 待 M4 | `tests/test_state_machine.py`、`test_locked_cases.py`（病例2） |
| SYS-E5-REVIEW | 兜底提示：缓解后血糖暂不能解释时保留观察（非锁定临床模板） | SYS-E5-REVIEW | `post_remission.py`、`domain/transitions.py`（ST60 自环） | 待 M4 | `tests/test_services_e4_e5.py` |
| SYS-ST00-REOPEN | 操作提示：从常规管理重新发起预评估（非临床结论） | SYS-ST00-REOPEN | `api/patients.py::reopen_pre_assessment` | `POST /api/patients/{id}/reopen` ✅ M4 | `tests/test_api_flow.py` |

---

## 二、状态机（唯一真源）

| 项目 | 位置 | 说明 |
| --- | --- | --- |
| 状态与名称 | `backend/app/domain/states.py` ✅ M3 已建立 | 9 个状态，中文名称供前台使用；未知状态返回"未知状态"而非代码 |
| 合法转换表 | `backend/app/domain/transitions.py` ✅ M3 已建立 | 每笔转换含 rule_id、必需字段、副作用、模板 |
| 转换校验 | `transitions.validate_transition()` | 所有服务跳转均经过；非法跳转返回自然语言原因 |
| 无出口检查 | `transitions.dead_end_states()` | 测试断言除终态 ST99 外无死端（`test_state_machine.py`） |
| 矩阵一致性 | `_SPEC/03` 状态出口矩阵 | 与本表逐条对应 |

---

## 三、分支优先级（V1.0 新增，单一数据源）

| 位置 | 说明 |
| --- | --- |
| `backend/app/domain/branches.py` ✅ M3 已建立 | 阶段复评 4 条分支的显式优先级表（失控 > 治疗下达标 > 停药 > 常规） |
| `branches.resolve_branch()` ✅ M3 已建立 | 返回生效分支 + **被忽略分支与原因**；互斥冲突直接报错 |
| `GET /api/domain/branches`（M4 建立） | 前端按优先级渲染，禁止前后端各写一套 |

---

## 四、输出模板

| 项目 | 位置 | 说明 |
| --- | --- | --- |
| 模板正文 | `backend/app/domain/templates.py` ✅ M3 已建立 | 30 条锁定 `OUT-*` + 3 条 SYS 级提示（2 条兜底 + 1 条操作提示） |
| 模板冻结测试 | `backend/tests/test_templates_frozen.py` ✅ M3 已建立 | **与甲方原件逐字比对**：从 `_DEV/甲方材料/md派生/临床流程实现表_输出模板.md` 解析出 30 条正文，与代码逐字断言；任何改写立即失败 |
| 计数口径 | `_SPEC/04` 第三节 | V0.1 文档写"34 个"有误，V1.0 更正为 30 条锁定文案（SYS 级提示另计，见 `_SPEC/06` V1.0-Q-01） |

---

## 五、日期与时间

| 规则 | 位置 | 说明 |
| --- | --- | --- |
| 日历月加法 | `backend/app/utils/date_utils.py::add_months_clamped` ✅ M3 已建立 | 钳位到目标月最后一天（8月31日+3月=11月30日）；含闰年二月用例 |
| 最早可判定日期 F040 | `date_utils.py::compute_earliest_judge_date` ✅ M3 已建立 | MAX(停药+3 月；生活方式+6 月〔如适用〕；手术+3 月〔如适用〕)；空缺锚点不参与 |
| 复评默认间隔 | `services/defaults.py::REVIEW_INTERVAL_WEEKS = 12` ✅ M3 已建立 | 两阶段一致，唯一来源，禁止散落硬编码 |
| 随访节奏 | `defaults.py::next_followup_date` ✅ M3 已建立 | 第 6/12/18/24 个月，满 2 年后按年顺延 |
| 时间注入 | `core/clock.py` ✅ M1 已建立 | 服务层不读系统时间，`today` 由调用方注入 |

---

## 六、工程实现决定登记（非临床决定）

| 编号 | 决定 | 位置 |
| --- | --- | --- |
| IMP-1 | F001=否 → 预评估"当前不启动"；F001=待确认 → 分型存疑暂缓 | `services/pre_assessment.py` ✅ M3 |
| IMP-2 | E3-B06 由"录入血糖 + 医生确认已达非糖尿病范围 + F053/F054"触发，无自动阈值 | `services/phase_review.py` ✅ M3 |
| IMP-3 | 缓解确认守卫：确认前必须存在 E4-B03"客观满足"事件 | 接口层守卫，待 M4 |
| IMP-4 | 急性安全后快速建档入口：最近事件须为 E1-B02 才可用 | 接口层守卫，待 M4 |
| IMP-5 | 关闭路径入口：最近事件须为 E1-B03 才可用 | 接口层守卫，待 M4 |
| IMP-6 | 账号用于可追溯性，不作为安全边界（`_SPEC/06` V1.0-Q-03） | 账号模块 |
| IMP-7 | 提醒不做后台调度，登录与打开工作台时计算（`_SPEC/06` V1.0-Q-04） | 工作台接口 |
| IMP-8 | 依据检索只给出处、不给临床建议（`_SPEC/07` AD-07） | 依据模块 |

---

## 七、UI Token 变更登记

| 版本 | 变更 | 说明 |
| --- | --- | --- |
| v1.0 | **全量替换**：macOS 26 Liquid Glass 体系 → Google Chrome / Material Design 3 体系 | 完整 Token 表见根目录 `UI.md` 第 2 节；登记表见 `UI.md` 附录 B；使用率自查由 `scripts/check_docs.py` 执行，未使用 Token 数必须为 0 |

---

## 八、第二轮第一批需求映射

| 需求 | 约束来源 | 实现位置 | 测试 |
| --- | --- | --- | --- |
| FR-0-07 / UX-47 测试账号跳转 | `_SPEC/02` 第十节、`_SPEC/06` R2-05/R2-13、`_SPEC/07` 16.2 | `backend/app/core/test_mode.py`、`api/test_support.py::debug_jump_state`、迁移 `9c4a2f1b7e10`、`frontend/src/pages/PatientWorkspacePage.tsx`、`TestToolsPanel.tsx` | `backend/tests/test_test_support.py`；`PatientWorkspacePage.test.tsx` |
| FR-0-15 / UX-58 模拟日期 | `_SPEC/02` 第十节、`_SPEC/06` R2-06/R2-14、`UI.md` 4.2 | `core/test_mode.py`、六个流程 API 的有效日期注入、`api/test_support.py`、`DateControl.tsx` | `backend/tests/test_test_support.py`；`DateControl.test.tsx` |
| UX-46 文件名大小写 | `_SPEC/09` 5.2 | Git 索引文件名 `MAPPING.md`；`scripts/check_docs.py` 与有效文档/源码注释统一大写引用 | `python scripts/check_docs.py` 在当前工作区 3/3 通过 |
| `TaskPanel` UI 门禁 | `UI.md` 1.3–1.5、`_SPEC/08` 8.1 | `frontend/src/components/TaskPanel.tsx`，由 `PatientWorkspacePage.tsx` 统一覆盖当前流程页面 | Token 使用率归零；`PatientWorkspacePage.test.tsx` |

---

## 九、第二轮第二批需求映射（已实现）

| 需求 | 约束来源 | 实际实现位置 | 验证 |
| --- | --- | --- | --- |
| FR-0-06 / UX-45 开放注册 | `_SPEC/02` FR-0-06、R2-12 | `users.department`、`api/auth.py::register`、`LoginPage.tsx` | `test_auth_api.py`、`LoginPage.test.tsx` |
| FR-0-08 / UX-48/49 患者档案 | R2-01/R2-04、`_SPEC/09` 5.3 | 迁移 `4f8e1c2d9a70`、`Department` / `Patient`、患者接口、`YearMonthInput`、`PatientProfileForm` | `test_patients_api.py`；页面构建与浏览器走查 |
| FR-0-09 / UX-50 批量导入 | R2-07/R2-08、UI-R8 | `api/patients.py::import_patients`、`services/patient_import.py`、`ImportDialog` | csv/xlsx、重复跳过、逐行结果与完善门禁测试 |
| FR-0-10/11 / UX-53/54 | `_SPEC/04` F006/F018/F019、UI-R1 | 患者最新测量字段、`utils/measurements.py`、`NumericInput`、预评估/完整评估 | BMI 持久化、范围与成对输入测试；`StructuredInputs.test.tsx` |
| FR-0-12 / UX-56 | R2-02/R2-03、UI-R3 | `/api/reference`、`domain/enums.py`、`SelectWithOther` / `MultiSelectWithOther` | 69 科室与诊断/药物字典测试；前端构建 |
| FR-0-16 / UX-51/52/57/61 | UI-R2/R7/R10 | `DateInput`、病程年/月双框、常规管理计数、1120px 居中布局、`FooterBar` | `StructuredInputs.test.tsx` + 浏览器走查 |

---

## 十、第二轮第三批需求映射（已实现）

| 需求 | 约束来源 | 实际实现位置 | 验证 |
| --- | --- | --- | --- |
| FR-0-14 / UX-60 正式角色与患者责任归属 | `_SPEC/06` T3-01/02/05/06、`_SPEC/07` 16.6 | 迁移 `6b7e2d4f9c10`；`flow_common.py` 统一写守卫；`auth.py::assignable_doctors`；`patients.py::transfer_patient_owner`；`PermissionNotice` / `OwnershipTransferDialog` | `test_patient_permissions.py`、`test_auth_api.py`、`test_smoke.py`；管理员 + 两位医生浏览器走查 |
| FR-0-10 / UX-55 阶段复评测量 | `_SPEC/06` T3-03、`_SPEC/07` 16.6.3 | `PhaseReviewInput`、`api/phase_review.py`、`PhaseReviewPage.tsx`；患者保存最新值，事件保存有效快照 | `test_api_flow.py::test_phase_review_updates_measurements_and_keeps_effective_snapshot`；`PhaseReviewPage.test.tsx`；浏览器 71kg/175cm/BMI23.2 |
| FR-0-13 / UX-21/22/59 患者搜索排序 | `_SPEC/06` T3-04、`_SPEC/07` 16.6.4、`UI.md` 3.6 | `PatientListPage.tsx`：姓名/住院号搜索、有效今天、默认到期优先、五字段双向排序、到期色与只读/责任医生展示 | `PatientListPage.test.tsx`；浏览器验证搜索、默认顺序、手工排序与日期即时刷新 |

---

## 十一、M6-A 依据数据与导入映射（已实现）

| 能力 | 约束来源 | 实际实现位置 | 验证 |
| --- | --- | --- | --- |
| 四来源与材料基线 | `_SPEC/11` M6-D01/D02、第二节 | `services/evidence_import.py::DEFAULT_EVIDENCE_SOURCES`；三份 PDF + 锁定稿的 SHA-256、页数/章节数门禁 | 真实材料 152/152 页 + 15/15 章节；哈希异常与页/章异常测试 |
| 依据模型与迁移 | `_SPEC/07` 4.5、`_SPEC/11` 第四节 | `models/evidence.py`；迁移 `a1c9e7f2d4b8`；FTS 虚拟表及同步触发器 | 临时库升级→降级→再升级；普通分块/FTS 均 684 行；外键检查通过 |
| 原子、幂等导入 | `_SPEC/11` 第五节 | `services/evidence_import.py`、`repository/evidence.py::replace_evidence`、`scripts/import_evidence.py` | 重复导入跳过；失败保留旧索引；空 PDF 与路径越界测试 |
| 中文与英文检索底座 | `_SPEC/11` 2.3/6.2 | `repository/evidence.py::search_chunks`：FTS5 trigram + 2 字/不可用时 LIKE | `test_evidence_import.py`；缓解/停药时间/HbA1c/remission/特殊字符真实库核验 |

---

## 十二、M6-B 接口与审计映射（已实现）

| 能力 | 约束来源 | 实际实现位置 | 验证 |
| --- | --- | --- | --- |
| 依据库状态 | `_SPEC/11` 6.1 | `api/evidence.py::_status`、`GET /api/evidence/status` | `test_evidence_api.py`：未导入/完整就绪、来源元数据不一致 |
| 全文检索接口 | `_SPEC/11` 6.2 | `GET /api/evidence/search`、`models/schemas.py::EvidenceSearchOut` | 查询长度、limit、总数、短词/长词模式、PDF 页码/章节、纯文本响应测试 |
| 全局登录权限 | `_SPEC/11` M6-D04 | `api/dependencies.py::get_current_user`；依据路由不调用患者归属守卫 | 匿名 401；启用普通医生可查阅全局依据 |
| 隐私审计 | `_SPEC/11` M6-D04、6.2 | `api/evidence.py::search_evidence` → `write_audit(action='evidence_search')` | 审计只含 query_chars/search_mode/result_count/returned_count；不含查询词与正文 |

---

## 十三、M6-C 前端依据抽屉映射（已实现）

| 能力 | 约束来源 | 实际实现位置 | 验证 |
| --- | --- | --- | --- |
| 状态与真实检索 | `_SPEC/11` 第七节/M6-C | `api/endpoints.ts::evidenceApi`、`EvidenceDrawer.tsx`、`PatientWorkspacePage.tsx` | 未输入/加载/未导入/无结果/错误/成功六类状态；工作台唯一入口页面测试 |
| 延迟与取消 | `_SPEC/11` 7.4/7.5 | `EvidenceDrawer.tsx`：300 ms 计时器 + `AbortController` | 快速连续输入只发送最后一个稳定查询；少于 2 字不请求 |
| 纯文本与出处 | `_SPEC/11` 7.7–7.9 | React 文本节点；`formatSource` 输出 PDF 页码或锁定稿章节；固定免责声明 | HTML 字符串不执行；同页多命中稳定渲染；真实材料页章浏览器核对 |
| 焦点与键盘 | `_SPEC/11` 7.10、`UI.md` 8.2 | `EvidenceDrawer.tsx` 焦点保存/约束/恢复 | 打开聚焦、Tab/Shift+Tab 循环、Esc 关闭、焦点回原触发按钮的 Vitest 与浏览器验证 |

---

## 十四、修订记录

| 版本 | 日期 | 修订内容 |
| --- | --- | --- |
| v1.0 | 2026-09-19 | 自 V0.1 继承规则清单并更正模板计数（34 → 32 条）；新增分支优先级、账号定位、依据检索三项登记；实现位置列待 M3/M4 回填 |
| v1.0.1 | 2026-09-20 | M3 完成回填：32 条规则全部指向服务层实现与测试文件；新增"模板与甲方原件逐字比对"说明；状态机、分支优先级、日期计算、IMP-1/IMP-2 标记为已落地；API 列仍待 M4 |
| v1.1 | 2026-09-24 | 文件名标题统一为 `MAPPING.md`；登记第二轮第一批测试能力与 `TaskPanel` 的约束、计划实现位置和测试范围 |
| v1.2 | 2026-09-24 | 回填第二轮第一批实际代码与测试位置；确认迁移、三重守卫、模拟日期、测试跳转与任务面板均已通过 Gate |
| v1.3 | 2026-09-24 | 登记第二轮第二批约束、计划代码位置与验收范围；待实现后回填实际位置 |
| v1.4 | 2026-09-24 | 回填第二轮第二批实际实现、迁移、测试与浏览器验收位置 |
| v1.5 | 2026-09-24 | 回填第三批正式角色、当前责任归属、阶段复评测量、患者搜索排序、权限翻转及浏览器验收位置 |
| v1.6 | 2026-09-24 | 回填 M6-A 四来源基线、依据模型/迁移、原子幂等导入、FTS5/LIKE 检索底座与真实材料验收位置 |
| v1.7 | 2026-09-24 | 回填 M6-B 状态/检索接口、完整性门禁、全局登录权限、纯文本出处与隐私审计测试位置 |
| v1.8 | 2026-09-24 | 回填 M6-C 真实接口抽屉、六类状态、延迟/取消、页章出处、免责声明、唯一列表键与焦点管理验证位置 |
