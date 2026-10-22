"""完整部署目录替换：新树、保留运行资料、工程外备份、同路径切换。

仅使用标准库。数据库/密钥不写入发布包；外部数据不搬迁，回退也不覆盖
更新后的数据库。所有目录重命名前验证绝对路径及所属目录，不递归删除。
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
import tomllib
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4


class ReplacementError(RuntimeError):
    """在修改前拒绝不安全或不相容的输入。"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def version(folder):
    module = ast.parse((folder / "backend/app/__init__.py").read_text(encoding="utf-8-sig"))
    return next(
        ast.literal_eval(n.value)
        for n in module.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in n.targets)
    )


def relative_path(name):
    value = PurePosixPath(name)
    if not name or "\\" in name or value.is_absolute() or any(p in {".", ".."} for p in value.parts):
        raise ReplacementError("路径无效 / Invalid relative path")
    return value


def checked_roots(project, release):
    if not project.is_absolute() or not release.is_absolute() or project.is_symlink() or release.is_symlink():
        raise ReplacementError("请使用真实绝对目录 / Use actual absolute directories")
    project, release = project.resolve(), release.resolve()
    if project == release or project.is_relative_to(release) or release.is_relative_to(project):
        raise ReplacementError("新旧目录不能相同或互相包含 / Separate release and project")
    if project.parent != release.parent or len(project.parts) < 3:
        raise ReplacementError("请把完整包解压在原工程旁 / Extract beside existing project")
    for folder in [project, release]:
        if not (folder / "backend/app/__init__.py").is_file() or not (folder / "start.sh").is_file():
            raise ReplacementError("不是有效ETMMS工程 / Invalid project structure")
    return project, release


def verify_release(release):
    manifest = json.loads((release / "release-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "0.4.3" or version(release) != "0.4.3":
        raise ReplacementError("发布包版本不匹配 / Release version mismatch")
    expected = set()
    for name, expected_hash in manifest["files"].items():
        parts = relative_path(name).parts
        if any(p in {".git", ".venv", "node_modules", "data", ".updates", ".env", "__pycache__"} for p in parts):
            raise ReplacementError("发布包含运行资料 / Runtime content in release")
        if parts[0] == "resources" and name not in {"resources/evidence/README.md", "resources/evidence/manifest.json"}:
            raise ReplacementError("发布包不应包含私有原件 / Private resource in release")
        path = release.joinpath(*parts)
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file() or digest(path) != expected_hash:
            raise ReplacementError(f"发布文件校验失败 / Release hash mismatch: {name}")
        expected.add(name)
    actual = {p.relative_to(release).as_posix() for p in release.rglob("*") if p.is_file()}
    if actual != expected | {"release-manifest.json"} or any(p.is_symlink() for p in release.rglob("*")):
        raise ReplacementError("解压目录含清单外文件 / Unexpected release files")
    return manifest


def require_stopped(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise ReplacementError(f"端口{port}仍在使用，请先停服 / Stop the service first")


def runtime_info(project):
    env = project / "backend/.env"
    if not env.is_file() or env.is_symlink():
        raise ReplacementError("找不到原backend/.env / Existing configuration missing")
    settings = {}
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"\s*(?:export\s+)?(ETMMS_DATA_DIR|ETMMS_DB_FILENAME)\s*=\s*(.*?)\s*$", line)
        if match:
            value = match[2]
            if value[:1] in {'"', "'"}:
                if len(value) < 2 or value[-1] != value[0]:
                    raise ReplacementError("数据配置引号不完整 / Invalid data setting")
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].strip()
            settings[match[1]] = value
    data_raw = os.environ.get("ETMMS_DATA_DIR", settings.get("ETMMS_DATA_DIR", str(project / "data/runtime")))
    data = Path(data_raw)
    if not data.is_absolute() or "$" in data_raw:
        raise ReplacementError("数据目录须为明确绝对路径 / Use an absolute data setting")
    filename = os.environ.get("ETMMS_DB_FILENAME", settings.get("ETMMS_DB_FILENAME", "etmms.db"))
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        raise ReplacementError("数据库文件名无效 / Invalid database filename")
    database, key = data / filename, data / "secret.key"
    if not database.is_file() or not key.is_file():
        raise ReplacementError("原数据库或密钥缺失，禁止创建空库 / Existing data or key missing")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ReplacementError("数据库完整性检查失败 / Database integrity failure")
        if db.execute("SELECT version_num FROM alembic_version").fetchall() != [("d04data001",)]:
            raise ReplacementError("数据库结构不相容，请先核实 / Incompatible schema")
    virtualenv = project / "backend/.venv"
    if (
        virtualenv.is_symlink()
        or not virtualenv.is_dir()
        or not any((virtualenv / n).exists() for n in ["bin/python", "Scripts/python.exe"])
    ):
        raise ReplacementError("原项目虚拟环境缺失 / Existing project virtualenv missing")
    # 相对项目内的数据目录必须精确保留，但不得覆盖应用文件所在目录。
    internal = []
    if data.is_relative_to(project):
        name = data.relative_to(project).as_posix()
        if not name or any((data / f).exists() for f in ["app", "start.sh", "pyproject.toml"]):
            raise ReplacementError("数据目录与代码目录重叠 / Data overlaps code")
        internal.append(name)
    return {
        "env": env,
        "data": data,
        "database": database,
        "key": key,
        "internal": internal,
        "hashes": {"env": digest(env), "database": digest(database), "key": digest(key)},
    }


def same_dependencies(project, release):
    def declarations(folder):
        data = tomllib.loads((folder / "backend/pyproject.toml").read_text(encoding="utf-8-sig"))["project"]
        return data["requires-python"], sorted(data["dependencies"])

    if declarations(project) != declarations(release):
        raise ReplacementError("Python运行依赖不同，不能直接沿用环境 / Runtime dependency mismatch")


def preserve_runtime(project, stage, info):
    shutil.copy2(info["env"], stage / "backend/.env")
    os.chmod(stage / "backend/.env", 0o600)
    folders = {"backend/.venv", *info["internal"]}
    if (project / "data").exists() or (project / "data").is_symlink():
        folders.add("data")
    # 已由更上层目录保留的子目录不重复复制。
    folders = {
        n for n in folders if not any(n != other and PurePosixPath(n).is_relative_to(other) for other in folders)
    }
    for name in folders:
        source, target = project / name, stage / name
        if target.exists():
            raise ReplacementError("运行目录与发布文件冲突 / Runtime directory collision")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source), target_is_directory=True)
        else:
            shutil.copytree(source, target, symlinks=True)
    resources = project / "resources"
    if resources.exists():
        for source in resources.rglob("*"):
            if source.is_symlink():
                raise ReplacementError("资源目录含链接，请先核实原件路径 / Resource symlink")
            if source.is_file():
                target = stage / source.relative_to(project)
                # 发布包的清单和说明保留当前版本，其他原件一字节不改。
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)


def code_snapshot(project, info):
    excluded = {
        ".git",
        ".venv",
        "node_modules",
        "data",
        "resources",
        ".updates",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
    }
    internal = [PurePosixPath(n) for n in info["internal"]]
    result = {}
    for base, dirs, files in os.walk(project, followlinks=False):
        relative = Path(base).relative_to(project)
        dirs[:] = [
            n
            for n in dirs
            if n not in excluded
            and not any(PurePosixPath((relative / n).as_posix()).is_relative_to(p) for p in internal)
        ]
        for name in files:
            path = Path(base) / name
            if name != ".env" and not path.is_symlink():
                result[path.relative_to(project).as_posix()] = digest(path)
    return result


def switch_tree(project, stage, info):
    parent = project.parent.resolve()
    backups = parent / ".etmms-backups"
    if backups.is_symlink():
        raise ReplacementError("备份目录不能是链接 / Invalid backup location")
    backup = backups / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8])
    backup.mkdir(parents=True)
    os.chmod(backups, 0o700)
    os.chmod(backup, 0o700)
    private = backup / "private"
    private.mkdir()
    os.chmod(private, 0o700)
    shutil.copy2(info["env"], private / "backend.env")
    shutil.copy2(info["key"], private / "secret.key")
    with (
        closing(sqlite3.connect(info["database"].resolve().as_uri() + "?mode=ro", uri=True)) as source,
        closing(sqlite3.connect(private / "database.sqlite3")) as target,
    ):
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ReplacementError("一致性备份失败 / Backup integrity failure")
    for path in private.iterdir():
        os.chmod(path, 0o600)
    state = {
        "project": str(project),
        "status": "prepared",
        "before_version": version(project),
        "after_version": version(stage),
        "before_code": code_snapshot(project, info),
    }
    write_json(backup / "state.json", state)
    # 最终重命名前再次明确核验绝对目标，全部位于用户指定工程的父目录内。
    old = backup / "project"
    if (
        project.parent != parent
        or stage.parent != parent
        or not old.resolve().is_relative_to(backups.resolve())
        or old.exists()
    ):
        raise ReplacementError("目录切换目标不安全 / Unsafe directory switch")
    if any(digest(info[n]) != info["hashes"][n] for n in ["env", "database", "key"]):
        raise ReplacementError("运行资料同时发生变化，请核实停服 / Runtime changed concurrently")
    project.rename(old)
    try:
        stage.rename(project)
        current = runtime_info(project)
        if current["hashes"] != info["hashes"]:
            raise ReplacementError("受保护内容不一致 / Protected content mismatch")
        state["after_code"] = code_snapshot(project, current)
    except Exception:
        # 失败的新树保留在原stage目录供核查，不删除任何资料。
        if project.exists():
            project.rename(stage)
        old.rename(project)
        state["status"] = "failed_original_restored"
        write_json(backup / "state.json", state)
        raise
    state["status"] = "replaced"
    write_json(backup / "state.json", state)
    print(f"完整替换完成 / Full replacement complete: {state['after_version']}")
    print(f"私有备份 / Private backup: {backup}")
    return backup


def replace(project, release, port=8088, *, dry_run=False):
    project, release = checked_roots(project, release)
    manifest = verify_release(release)
    require_stopped(port)
    info = runtime_info(project)
    same_dependencies(project, release)
    for internal in info["internal"]:
        if any(PurePosixPath(name).is_relative_to(internal) for name in manifest["files"]):
            raise ReplacementError("发布路径与数据目录冲突 / Release overlaps runtime")
    if dry_run:
        print("预检通过：完整发布文件、现有配置/数据库/密钥、依赖及停服状态 / Preflight passed")
        return None
    stage = project.parent / (".etmms-stage-" + uuid4().hex)
    shutil.copytree(release, stage)
    verify_release(stage)
    preserve_runtime(project, stage, info)
    return switch_tree(project, stage, info)


def rollback(project, backup, port=8088):
    if not project.is_absolute() or not backup.is_absolute() or project.is_symlink() or backup.is_symlink():
        raise ReplacementError("回退需要真实绝对目录 / Invalid rollback paths")
    project, backup = project.resolve(), backup.resolve()
    expected = project.parent / ".etmms-backups"
    if backup.parent != expected or expected.is_symlink():
        raise ReplacementError("备份不属于此工程 / Backup outside expected location")
    state = json.loads((backup / "state.json").read_text(encoding="utf-8"))
    if state["project"] != str(project) or state["status"] != "replaced" or version(project) != state["after_version"]:
        raise ReplacementError("回退状态不匹配 / Rollback state mismatch")
    require_stopped(port)
    info = runtime_info(project)
    if code_snapshot(project, info) != state["after_code"]:
        raise ReplacementError("替换后代码又有修改，拒绝覆盖 / Code changed since replacement")
    old = backup / "project"
    if code_snapshot(old, info) != state["before_code"]:
        raise ReplacementError("旧工程备份已修改 / Original code backup changed")
    stage = project.parent / (".etmms-stage-" + uuid4().hex)
    excluded = {
        ".git",
        ".venv",
        "node_modules",
        "data",
        "resources",
        ".updates",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".env",
    }
    internal = {str(old / n) for n in info["internal"]}

    def ignore(folder, names):
        return [n for n in names if n in excluded or str(Path(folder) / n) in internal]

    shutil.copytree(old, stage, ignore=ignore)
    # 当前资源清单及原件一起保留；当前运行数据而非旧库被带入回退树。
    preserve_runtime(project, stage, info)
    result = switch_tree(project, stage, info)
    state["status"] = "rolled_back"
    state["rollback_backup"] = str(result)
    write_json(backup / "state.json", state)
    print("回退完成，当前数据库、配置、密钥和后续记录保留 / Current runtime data retained")
    return result


def main():
    parser = argparse.ArgumentParser(description="ETMMS full deployment replacement")
    parser.add_argument("action", choices=["check", "replace", "rollback"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--release", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    try:
        if args.action == "rollback":
            if not args.backup:
                parser.error("rollback需要--backup")
            rollback(args.project, args.backup, args.port)
        else:
            replace(args.project, args.release, args.port, dry_run=args.action == "check")
    except (ReplacementError, OSError, ValueError, KeyError, StopIteration, sqlite3.Error) as exc:
        parser.exit(1, f"未完成 / Not completed: {exc}\n")


if __name__ == "__main__":
    main()
