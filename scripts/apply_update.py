"""白名单文件补丁：停服、核对、备份、替换和代码回退；不初始化/迁移运行数据。

只使用标准库，可用云端既有backend/.venv运行。更新包根目录应包含
manifest.json、payload和本脚本。备份含私有配置/密钥，必须留在私有目录。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


class PatchError(RuntimeError):
    """可解释的预检或回退拒绝，不能在检查失败后继续覆盖。"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if not relative or "\\" in relative or parts.is_absolute() or any(p in {"..", "."} for p in parts.parts):
        raise PatchError("补丁路径无效 / Invalid patch path")
    if parts.parts[0] in {".git", ".updates", "data", "resources"} or any(
        p in {".venv", "node_modules", "__pycache__"} or p == ".env" or p.endswith((".key", ".db", ".pem"))
        for p in parts.parts
    ):
        raise PatchError("拒绝覆盖受保护路径 / Protected path")
    result = root.joinpath(*parts.parts)
    # 逐层阻断目录/文件链接；不允许通过预置链接逃逸到工作区外。
    for parent in [result, *result.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise PatchError("目标路径含符号链接 / Symlink target")
    if not result.resolve().is_relative_to(root.resolve()):
        raise PatchError("目标越界 / Path escapes project")
    return result


def version(project: Path) -> str:
    try:
        module = ast.parse((project / "backend/app/__init__.py").read_text(encoding="utf-8-sig"))
        return next(
            ast.literal_eval(n.value)
            for n in module.body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in n.targets)
        )
    except (OSError, StopIteration, SyntaxError) as exc:
        raise PatchError("无法识别工程版本 / Cannot identify project version") from exc


def require_stopped(port: int):
    with socket.socket() as conn:
        conn.settimeout(1)
        if conn.connect_ex(("127.0.0.1", port)) == 0:
            raise PatchError(f"端口{port}仍在监听，请先用原start.sh stop停服；不会自动杀进程 / Stop service first")


def preflight(bundle: Path, project: Path):
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("from_version") != "0.4.2" or manifest.get("to_version") != "0.4.3":
        raise PatchError("不支持的补丁版本 / Unsupported patch")
    if version(project) != manifest["from_version"]:
        raise PatchError("此补丁仅适用0.4.2；已是0.4.3时不要重复应用 / Base version mismatch")
    seen = set()
    for entry in manifest["files"]:
        name = entry["path"]
        target, source = safe_path(project, name), safe_path(bundle / "payload", name)
        if name in seen:
            raise PatchError("补丁含重复路径 / Duplicate path")
        seen.add(name)
        if not source.is_file() or digest(source) != entry["sha256"]:
            raise PatchError(f"补丁文件校验失败 / Payload hash mismatch: {name}")
        if target.exists():
            if not target.is_file() or digest(target) not in [
                *entry["previous_sha256"],
                entry["sha256"],
            ]:
                raise PatchError(f"发现基线外修改，请先人工核对，不会覆盖 / Modified file: {name}")
        elif entry.get("required_in_base", bool(entry["previous_sha256"])):
            raise PatchError(f"原版本文件缺失 / Missing base file: {name}")
    for entry in manifest.get("remove", []):
        target = safe_path(project, entry["path"])
        if entry["path"] in seen:
            raise PatchError("新增与移除路径重复 / Conflicting paths")
        seen.add(entry["path"])
        if target.exists() and (not target.is_file() or digest(target) not in entry["previous_sha256"]):
            raise PatchError(f"旧构建文件已修改，不会清理 / Modified old asset: {entry['path']}")
    return manifest


def data_paths(project: Path):
    # 仅解析指定的两个路径配置；不输出.env内容，不展开任意shell语句。
    values = {}
    env_file = project / "backend/.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(
                r"\s*(?:export\s+)?(ETMMS_DATA_DIR|ETMMS_DB_FILENAME)\s*=\s*(.*?)\s*$",
                line,
            )
            if match:
                value = match[2]
                if value[:1] in {"'", '"'}:
                    if len(value) < 2 or value[-1] != value[0]:
                        raise PatchError("数据目录配置引号不完整 / Invalid data setting")
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].strip()
                values[match[1]] = value
    raw = os.environ.get("ETMMS_DATA_DIR", values.get("ETMMS_DATA_DIR"))
    if raw and ("$" in raw or "\n" in raw):
        raise PatchError("请将ETMMS_DATA_DIR写为明确绝对目录后再更新 / Use an absolute data directory")
    folder = Path(raw) if raw else project / "data/runtime"
    if not folder.is_absolute():
        raise PatchError("数据目录必须为绝对路径 / Data path must be absolute")
    filename = os.environ.get("ETMMS_DB_FILENAME", values.get("ETMMS_DB_FILENAME", "etmms.db"))
    if filename != Path(filename).name or "\\" in filename or "/" in filename:
        raise PatchError("数据库文件名无效 / Invalid database filename")
    folder = folder.resolve()
    if not (folder / filename).is_file() or not (folder / "secret.key").is_file():
        raise PatchError("原数据库或签名密钥缺失，请核实实际数据目录，禁止初始化空库 / Existing data/key missing")
    return env_file, folder / filename, folder / "secret.key"


def private_copy(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    os.chmod(target, 0o600)


def apply(bundle: Path, project: Path, port: int = 8088, *, dry_run: bool = False) -> Path | None:
    project, bundle = project.resolve(), bundle.resolve()
    manifest = preflight(bundle, project)
    env_file, database, key = data_paths(project)
    if dry_run:
        print(
            f"预检通过 / Preflight passed: {len(manifest['files'])} files, {manifest['from_version']} -> {manifest['to_version']}"
        )
        return None
    require_stopped(port)
    backups = project / ".updates"
    if backups.is_symlink():
        raise PatchError("备份目录不能是链接 / Invalid backup directory")
    backup = backups / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    os.chmod(backups, 0o700)
    os.chmod(backup, 0o700)
    for name in ["files", "private", "stage"]:
        (backup / name).mkdir()
        os.chmod(backup / name, 0o700)
    if env_file.exists():
        private_copy(env_file, backup / "private/backend.env")
    private_copy(key, backup / "private/secret.key")
    with (
        sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source,
        sqlite3.connect(backup / "private/database.db") as target,
    ):
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise PatchError("SQLite备份校验失败 / Backup integrity failure")
    os.chmod(backup / "private/database.db", 0o600)
    entries = []
    for entry in [*manifest["files"], *manifest.get("remove", [])]:
        name = entry["path"]
        original = safe_path(project, name)
        old_hash = digest(original) if original.is_file() else None
        entries.append(
            {
                "path": name,
                "before_sha256": old_hash,
                "after_sha256": entry.get("sha256"),
            }
        )
        if original.exists():
            private_copy(original, safe_path(backup / "files", name))
    state = {
        "project": str(project),
        "from_version": manifest["from_version"],
        "to_version": manifest["to_version"],
        "files": entries,
        "status": "prepared",
        "database_sha256": digest(database),
        "key_sha256": digest(key),
    }
    write_json(backup / "state.json", state)
    # 先完整暂存，再逐文件原子替换。版本标记最后更换，异常自动回退已触碰文件。
    ordered = sorted(manifest["files"], key=lambda e: e["path"] == "backend/app/__init__.py")
    touched = []
    try:
        for entry in ordered:
            name = entry["path"]
            stage = safe_path(backup / "stage", name)
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(bundle / "payload", name), stage)
        for entry in ordered:
            name = entry["path"]
            target = safe_path(project, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            touched.append(name)
            os.replace(safe_path(backup / "stage", name), target)
        for entry in manifest.get("remove", []):
            target = safe_path(project, entry["path"])
            if target.exists():
                touched.append(entry["path"])
                target.unlink()  # 仅经哈希校验且已备份的单个旧构建文件，不递归删除。
        if digest(database) != state["database_sha256"] or digest(key) != state["key_sha256"]:
            raise PatchError("检测到数据库/密钥同时变化；停止启动并检查其他进程 / Runtime data changed concurrently")
    except Exception:
        restore_files(project, backup, [e for e in entries if e["path"] in touched])
        state["status"] = "failed_code_restored"
        write_json(backup / "state.json", state)
        raise
    state["status"] = "applied"
    write_json(backup / "state.json", state)
    print(f"更新完成 / Applied 0.4.3. 私有备份 / Private backup: {backup}")
    print("请运行 bash start.sh 并核对/api/health；不需要重新初始化管理员。")
    return backup


def restore_files(project, backup, entries):
    for entry in entries:
        target = safe_path(project, entry["path"])
        saved = safe_path(backup / "files", entry["path"])
        if entry["before_sha256"] is None:
            if target.exists():
                target.unlink()
        else:
            if not saved.is_file() or digest(saved) != entry["before_sha256"]:
                raise PatchError("代码备份哈希不符，拒绝回退 / Corrupt code backup")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(saved, target)


def rollback(project: Path, backup: Path, port: int = 8088):
    project, backup = project.resolve(), backup.resolve()
    if not backup.is_relative_to(project / ".updates") or backup.is_symlink():
        raise PatchError("回退备份必须位于此工程.updates目录 / Invalid rollback directory")
    state = json.loads((backup / "state.json").read_text(encoding="utf-8"))
    if state["project"] != str(project) or state["status"] != "applied" or version(project) != state["to_version"]:
        raise PatchError("版本或回退状态不匹配 / Rollback state mismatch")
    require_stopped(port)
    for entry in state["files"]:
        target = safe_path(project, entry["path"])
        actual = digest(target) if target.is_file() else None
        if actual != entry["after_sha256"]:
            raise PatchError(f"更新后文件已有其他修改，拒绝覆盖 / Modified after update: {entry['path']}")
        if entry["before_sha256"] is not None:
            saved = safe_path(backup / "files", entry["path"])
            if not saved.is_file() or digest(saved) != entry["before_sha256"]:
                raise PatchError("代码备份损坏 / Corrupt code backup")
    restore_files(project, backup, state["files"])
    state["status"] = "rolled_back_code_only"
    write_json(backup / "state.json", state)
    print("代码已回退；现有数据库、配置和密钥未替换 / Code restored; runtime data preserved.")


def main():
    parser = argparse.ArgumentParser(description="ETMMS 0.4.2 -> 0.4.3 safe file patch")
    parser.add_argument("action", choices=["check", "apply", "rollback"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    try:
        if args.action == "rollback":
            if args.backup is None:
                parser.error("rollback需要--backup / --backup required")
            rollback(args.project, args.backup, args.port)
        else:
            apply(args.bundle, args.project, args.port, dry_run=args.action == "check")
    except (PatchError, OSError, ValueError) as exc:
        parser.exit(1, f"未完成 / Not completed: {exc}\n")


if __name__ == "__main__":
    main()
