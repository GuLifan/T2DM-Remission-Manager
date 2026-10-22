# Validation — 0.4.3 / 验证范围

## Clean-workspace verification — 2026-10-22 / 全新工作区验证

The current source was installed from its lockfiles in a new project-local Python environment and a fresh frontend dependency directory. **466 backend tests passed** (two upstream deprecation warnings); **61 frontend tests across 19 files passed**. Frontend lint, TypeScript/production build and Python lock consistency passed. The complete-replacement helper, builder and replacement tests passed Ruff checks.

当前源码按锁文件在全新的项目Python环境和前端依赖目录安装。**466项后端测试通过**（两条上游弃用提示），**19个文件、61项前端测试通过**；前端检查、TypeScript/生产构建、Python锁一致性通过。完整替换工具、打包工具及替换测试通过Ruff检查。

The backend total is the previous 452 cases minus 14 cases dedicated to the retired incremental updater, plus 28 complete-replacement cases. All other prior clinical, ownership, concurrency, service and component regressions remain. Application files under `backend/app` and `frontend/src` are byte-identical to the reviewed 0.4.3 source baseline `9d669d9`. A frozen JSON fixture was normalized from CRLF to LF by Git without changing its content. These are current totals, not sums of historical runs.

后端总数为此前452项，减去随增量工具退役的14项专用测试，加上28项完整替换测试。其他既有临床、归属、并发、服务和组件回归保留。`backend/app`与`frontend/src`逐字节保持已审查0.4.3基线`9d669d9`；一份冻结JSON夹具仅由Git规范换行，内容不变。这里是本次总数，不与历史次数累加。

The frontend lockfile referred to a nonexistent `@testing-library/dom` 10.4.3 tarball. It now pins the available 10.4.2 tarball whose integrity matches the existing lockfile entry. A fresh `npm ci` and the checks above passed. This changes a test dependency, not clinical application code or runtime dependencies.

前端锁文件原来指向不存在的`@testing-library/dom` 10.4.3压缩包，现改为与原integrity一致且可下载的10.4.2。全新`npm ci`及以上检查通过；只修正测试依赖，不修改临床源码或运行依赖。

## Coverage and limits / 覆盖及边界

Regression coverage includes historical clinical-source contracts, E1–E5 transitions, ownership and session isolation, conflicting saves, role-dependent dates, current-plan removal without inferring discontinuation, examination date boundaries, persistent centered notices, draft preservation and background-service guards. Public source/evidence tests use minimal frozen baselines and synthetic files; they do not require private originals or silently skip their absence. These checks validate engineering consistency rather than independently revalidating every medical claim.

覆盖包括历史临床来源契约、E1—E5转移、归属与会话隔离、竞争保存、按角色使用日期、本次移除药物但不推断停药、检查日期边界、持续居中提示、草稿保留及后台服务门禁。公开来源/依据测试使用最小冻结基线和合成文件，不依赖私有原件，也不因缺失而跳过。这验证工程一致性，不等于逐条重新验证全部医学论断。

The 28 replacement cases exercise separate internal/external data layouts, preflight refusal, manifests, protected runtime material, clean-tree replacement, failure recovery and rollback preserving later records. The earlier complete-delivery run additionally exercised three actual archive baselines over nine local API phases; that historical run is separate and is not added to this suite's totals.

28项完整替换用例覆盖内部/外部数据、预检拒绝、清单、运行资料保护、干净目录替换、失败恢复及保留后续记录的回退。此前完整交付另对三种真实压缩包基线做过九个本地API阶段检查；这是独立历史记录，不计入本次测试总数。

Lifan reports that 0.4.3 currently runs normally on Sealos. This migration/publication did not change the running cloud service or database. Windows-local tests do not independently establish Linux process behavior, gateway capacity, Devbox restart persistence, comprehensive device coverage or clinician acceptance.

Lifan已确认0.4.3当前在Sealos正常运行。本轮迁移和Git发布未修改云端服务或数据库。Windows本地验证不能独立证明Linux进程行为、网关容量、Devbox重启持久化、全部设备兼容或临床医师验收。

## Reproduce / 复现

Build the frontend before the backend suite: background-service tests intentionally require the compiled page. Tests use temporary synthetic information, separate from deployment data.

先构建前端，再运行后端全套：后台服务测试确实要求编译页面存在。测试使用临时模拟资料，与部署数据分离。

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
cd ../backend
uv sync --frozen
uv run --no-sync pytest
uv run --no-sync ruff check ../scripts/replace_deployment.py ../scripts/build_release.py tests/test_complete_deployment.py
```

The release builder uses an explicit operating-document list and excludes private configuration, keys, runtime databases, dependency directories, test fixtures and evidence originals. Private originals and handover records are Git-ignored. Limited candidate-file key/token/local-path pattern scans are useful checks, not a guarantee of exhaustive secret detection or a fresh audit of all retained Git history.

打包工具明确列出运行说明，排除私有配置、密钥、运行库、依赖目录、测试夹具及依据原件。私有原件和交接记录受Git忽略保护。候选文件的有限密钥/token/本机路径模式扫描属于辅助检查，不保证识别一切秘密，也不代表本轮重新审计全部保留的Git历史。
