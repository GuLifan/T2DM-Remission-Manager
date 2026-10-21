# Sealos 0.4.2 → 0.4.3 patch / 更新补丁

Applies to the official 0.4.2 Sealos package. Contains changed runtime/source/docs and prebuilt frontend files; no database, `.env`, signing/SSH/API key, account, patient, dependencies or private evidence originals. No database schema change. The updater preserves existing evidence and runtime data. This guide does not authorize a main push or automatically access your cloud.

适用于此前交付的0.4.2 Sealos部署包。只带变更代码/说明和已编译前端，不带数据库、真实配置、签名/SSH/API密钥、账号、病例、依赖或私有原件。数据库结构不变，更新保留原依据和运行数据。本指南不会自动操作云端或授权推送main。

## 1. Upload and verify / 上传校验

With Xftp, upload the patch ZIP and `SHA256SUMS.txt` to `/home/devbox/project/`, **beside** the existing project, not inside its data directory. Verify the hash, then extract to a new patch directory. Do not overwrite an earlier extracted patch directory.

用Xftp把补丁ZIP和`SHA256SUMS.txt`上传到`/home/devbox/project/`，放在原工程旁边，不要放到数据目录。先核对校验值，再解压到新的补丁目录，不覆盖旧补丁目录。

```bash
cd /home/devbox/project
sha256sum -c SHA256SUMS.txt
unzip ETMMS-0.4.2-to-0.4.3-sealos-patch-20261021.zip
```

The extracted folder is `ETMMS-0.4.2-to-0.4.3-patch`. These are examples of paths; set the project variable to the actual existing project. `pwd` in the old project's terminal identifies it.

解压目录为`ETMMS-0.4.2-to-0.4.3-patch`。以下工程路径需与你实际部署一致，可在原工程终端用`pwd`核对。

```bash
export ETMMS_PROJECT=/home/devbox/project/ETMMS-v0.4
export ETMMS_PATCH=/home/devbox/project/ETMMS-0.4.2-to-0.4.3-patch
"$ETMMS_PROJECT/backend/.venv/bin/python" "$ETMMS_PATCH/apply_update.py" check --project "$ETMMS_PROJECT"
```

Preflight checks version, paths, old-file hashes, payload hashes and the configured existing database/key. A failure changes no project files. If a manual edit is reported, preserve it and reconcile the named file; do not bypass hashes or delete the data directory. An already upgraded 0.4.3 installation is rejected rather than patched twice.

预检核对版本、路径、旧文件/补丁哈希和原数据库/密钥配置。失败不改工程文件。若报告手工修改，先保留并核对所列文件，不绕过哈希或删除数据目录。已是0.4.3时拒绝重复应用。

## 2. Stop, back up and apply / 停服、备份、应用

```bash
cd "$ETMMS_PROJECT"
bash start.sh stop
"$ETMMS_PROJECT/backend/.venv/bin/python" "$ETMMS_PATCH/apply_update.py" apply --project "$ETMMS_PROJECT"
```

The updater refuses if port 8088 is still listening; it never kills a process. Use `--port` only if your existing service intentionally uses another port. The updater creates a timestamped private `.updates/` backup containing original changed files, an integrity-checked SQLite backup, key and `.env`. Keep the printed backup path. Do not upload/share that directory. It is excluded from Git.

若8088仍在监听，更新拒绝继续，不会杀进程；仅原服务确实使用其他端口时才传`--port`。更新会在工程`.updates/`下生成带时间戳的私有备份，包含原变更文件、SQLite一致性备份、密钥和配置。记下输出的备份路径，不上传或分享该目录；它已被Git忽略。

After all checks and backups, files are replaced; known superseded frontend assets are removed only after hash verification and backup. Unexpected replacement errors restore touched code. Existing `.env`, runtime data, keys and evidence are not overwritten. The version marker changes last. If any error is reported, do not start a partially updated installation; retain the error/backup and inspect its state.

完成全部检查和备份后才替换文件；只清理哈希匹配且已备份的旧前端构建文件。替换异常时恢复已触碰代码。原配置、运行数据、密钥和依据不覆盖，版本标记最后更新。若出现错误，不要启动不明状态的工程；保留错误和备份先核对。

## 3. Start and validate / 启动核验

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
```

Expected / 预期：`{"status":"ok","version":"0.4.3"}`.

This patch uses installed Python dependencies and includes compiled pages: no `npm ci`, frontend build, `uv sync`, evidence reimport or `init-admin` is required for this update. If you later rebuild from source, use the supplied lockfiles, including patched Vite 8.3.3.

本次补丁沿用已安装Python依赖并包含编译页面，无需重新安装依赖、构建前端、导入依据或初始化管理员。以后从源码构建时，使用本次锁文件（含Vite8.3.3修补版本）。

Force-refresh the browser (Ctrl+F5), log in with the original accounts and verify: previous cases/history remain; the administrator can see the date shortcut upper-left; a doctor cannot edit dates; medication removal requires renewed review, preserves history and does not start observation; past examinations save while future facts explain the dates; E4 incomplete results remain visible after form refresh.

浏览器Ctrl+F5刷新，以原账号登录，核对：原病例/历史仍在；管理员左上有日期入口、医生无日期编辑；移除药物后须重新确认且历史保留，不自动启动观察；既往检查能保存、未来事实提示明确日期；E4未通过原因在表单刷新后仍可见。

## 4. Code rollback / 代码回退

If rollback is needed, stop the service and use the exact backup path printed during application:

需要回退时先停服，再使用应用补丁时输出的准确备份目录：

```bash
cd "$ETMMS_PROJECT"
bash start.sh stop
"$ETMMS_PROJECT/backend/.venv/bin/python" "$ETMMS_PATCH/apply_update.py" rollback --project "$ETMMS_PROJECT" --backup "$ETMMS_PROJECT/.updates/REPLACE_WITH_THE_PRINTED_DIRECTORY"
bash start.sh
curl --fail http://127.0.0.1:8088/api/health
```

Rollback verifies that code has not been manually changed since application, restores the original code/assets and removes newly introduced code files. It **preserves the current database, configuration and key**, including records created after the patch; it does not automatically restore the older database backup. The unchanged schema makes code-only rollback possible. Disaster database restoration requires a separate deliberate decision to avoid losing later records.

回退先核对代码未被再次手工修改，再恢复原代码/构建文件并移除补丁新增代码。它**保留当前数据库、配置及密钥**，包括更新后新增记录，不自动用旧库覆盖。由于数据库结构未改变，可仅回退代码。灾难性数据库恢复须另行明确决定，避免丢失后续记录。

Cloud installation/restart persistence and clinician acceptance remain on-site checks. The patch does not install boot tasks, change the public port or touch main.

云端安装、重启持久化和医师验收仍须现场核对。补丁不安装开机任务、不改变公网端口，也不更新main。
