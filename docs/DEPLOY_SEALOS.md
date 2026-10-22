# Sealos 0.4.3 complete replacement / 完整替换

Use this guide for an **existing, stopped installation**. Existing accounts, cases, history, `.env`, signing key, Python virtual environment and evidence are retained. The archive is a complete current application, not a set of changed files. No database migration or account initialization is required.

适用于**已有且已停服的工程**。保留账号、病例、历史、`.env`、签名密钥、Python虚拟环境和依据。本包为完整当前应用，不是差异文件集合；无需数据库迁移或账号初始化。

## 1. Upload / 上传

Use Xftp to upload the ZIP and `SHA256SUMS.txt` to `/home/devbox/project/`, beside the old application. Do not drag new files over the old code tree: ordinary overwriting leaves obsolete files. Do not overwrite an existing extracted release directory.

用Xftp把ZIP和`SHA256SUMS.txt`上传到`/home/devbox/project/`，放在旧工程旁。不要把新文件直接拖进旧代码目录覆盖，这样会残留旧文件。不要覆盖已存在的解压目录。

```bash
cd /home/devbox/project
sha256sum -c SHA256SUMS.txt
unzip ETMMS-v0.4.3-sealos-full-20261022.zip
```

The extracted directory is `ETMMS-v0.4.3`. If that name is already the live project or is occupied, extract locally, rename the new directory to `ETMMS-v0.4.3-release`, then upload it beside the existing project and use that name below. Do not replace the live directory during extraction.

解压得到`ETMMS-v0.4.3`。若该名称已经是当前工程或被占用，先在本地解压，把新目录改名为`ETMMS-v0.4.3-release`后整体上传到原工程旁，并相应调整下面的release路径；解压阶段不覆盖当前工程。

## 2. Confirm paths and stop / 核对路径并停服

The existing path below is an example; use `pwd` in the old project to confirm yours. Keep the final live path unchanged, including the virtual environment's absolute path. Work from the parent directory while switching application folders.

下列旧工程路径需与你实际一致；可在原工程用`pwd`核对。最终运行路径保持不变，虚拟环境的绝对路径也保持。替换时终端停留在父目录。

```bash
cd /home/devbox/project
export ETMMS_PROJECT=/home/devbox/project/ETMMS-v0.4
export ETMMS_RELEASE=/home/devbox/project/ETMMS-v0.4.3
bash "$ETMMS_PROJECT/start.sh" stop
```

If you already stopped the service, the last command confirms its state. Only the old live path and new sibling release path are supplied; no SSH key or application password is needed.

已经停服也可执行最后一行确认状态。这里只填写旧运行目录和新的同级完整包目录，不需要SSH私钥或应用密码。

## 3. Check without modifying / 只读预检

```bash
"$ETMMS_PROJECT/backend/.venv/bin/python" \
  "$ETMMS_RELEASE/scripts/replace_deployment.py" check \
  --project "$ETMMS_PROJECT" --release "$ETMMS_RELEASE"
```

Expected: `Preflight passed / 预检通过`. The tool checks the complete release manifest/hashes, separate paths, stopped port8088, existing configuration/database/key, database headd04data001 and unchanged Python runtime dependencies. Missing data is an error, never permission to create a blank database. Resolve reported issues before continuing. Use `--port` on every operation only if your existing service intentionally uses another port.

预期“预检通过”。工具核对完整清单/哈希、目录互不包含、8088停服、原配置/数据库/密钥、结构d04data001及Python运行依赖一致。缺原数据会报错，不会创建空库。若报错，先核实再继续。仅现有服务确实使用其他端口时，各次操作都增加对应`--port`。

## 4. Full replacement / 完整替换

```bash
"$ETMMS_PROJECT/backend/.venv/bin/python" \
  "$ETMMS_RELEASE/scripts/replace_deployment.py" replace \
  --project "$ETMMS_PROJECT" --release "$ETMMS_RELEASE"
```

The tool prepares a clean sibling tree, carries over `.env`, `.venv`, project-internal runtime data and evidence originals, and leaves external data where configured. It creates a private `.etmms-backups/<time-id>/` beside the application, containing the original application and an integrity-checked SQLite/configuration/key backup. It then switches directories at the original live path. A failed final switch restores the original application. It never recursively deletes the old project, runtime data or backups.

工具准备干净同级目录，带入原`.env`、`.venv`、项目内运行数据及依据原件；外部数据仍留在原配置位置。在工程旁生成私有`.etmms-backups/<时间标识>/`，含旧工程和已核验的一致性SQLite/配置/密钥备份，再切换到原运行路径。最终切换失败会恢复旧工程，不递归删除工程、数据或备份。

**Wait for “Full replacement complete / 完整替换完成”.** Keep the printed private backup path; do not upload/share backups. A failed preparation may leave a hidden staging directory for inspection. Do not manually start it or copy it over the application.

**看到“完整替换完成”后再启动。** 记下输出的私有备份路径，不上传或分享。准备失败可能保留隐藏暂存目录供核查，不手工运行它或覆盖当前工程。

## 5. Start and inspect / 启动核验

```bash
cd "$ETMMS_PROJECT"
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
```

Expected: `{"status":"ok","version":"0.4.3"}`. Keep the same Sealos public port8088 and HTTPS route. Force-refresh the browser (Ctrl+F5), use the original accounts and confirm existing cases/history and evidence, administrator date entry upper-left, doctor read-only date, current-plan medication removal and centered validation results.

预期`{"status":"ok","version":"0.4.3"}`。Sealos公网8088端口和HTTPS路由保持。浏览器Ctrl+F5刷新，以原账号登录，核对旧病例/历史/依据、管理员左上日期入口、医生只读日期、本次药物移除及居中提示。

No `init-admin`, evidence reimport, `npm ci`, frontend build or `uv sync` is required for this replacement: compatible installed Python dependencies and the compiled frontend are retained/provided. If you intentionally rebuild the source later, use the included lockfiles. Do not copy a Windows virtual environment to Linux.

本次替换不需要`init-admin`、重新导入依据、`npm ci`、前端构建或`uv sync`：沿用相容的已安装Python依赖，页面已编译。以后主动重建源码时使用包内锁文件；不把Windows虚拟环境复制到Linux。

## 6. Rollback if necessary / 必要时回退

Stop the service and substitute the exact backup path printed during replacement. Run from the parent directory; the extracted new release remains available as the maintenance tool.

先停服，使用替换时输出的准确备份路径。在父目录执行；解压的新完整包仍可作为维护工具。

```bash
cd /home/devbox/project
bash "$ETMMS_PROJECT/start.sh" stop
"$ETMMS_PROJECT/backend/.venv/bin/python" \
  "$ETMMS_RELEASE/scripts/replace_deployment.py" rollback \
  --project "$ETMMS_PROJECT" \
  --backup /home/devbox/project/.etmms-backups/REPLACE_WITH_PRINTED_DIRECTORY
```

After “rollback complete”, return to the live project and start it. Rollback restores prior code but carries over the **current** configuration, environment, data/key and evidence, including records created after replacement. It does not automatically restore an older database. Modified current code or a modified backup is rejected. Another private application backup is kept; do not delete it until acceptance and a separate backup-retention decision.

看到“回退完成”后回运行工程启动。回退恢复旧代码，带入**当前**配置、环境、数据/密钥和依据，包括替换后新增记录，不自动恢复旧数据库。当前代码或旧代码备份被修改时拒绝覆盖，并保留另一份私有工程备份。验收及明确备份保留策略前不删除备份。

Local isolated verification does not replace Sealos/Linux on-site startup, gateway, Devbox restart persistence or clinician acceptance. This procedure does not install automatic boot tasks or alter remote Git branches.

本地隔离验证不代替Sealos/Linux现场启动、网关、Devbox重启持久化或医生验收。本流程不安装开机任务，不改变远端Git分支。
