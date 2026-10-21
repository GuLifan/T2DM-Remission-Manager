"""迁移前SQLite一致性备份，保留临床记录；不用简单复制忽略WAL。"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

V03_REVISION = "b2d03f7a610c"


def backup_before_v03(db_path: Path) -> Path | None:
    """仅已有数据库且未升级时备份；失败阻断升级，不覆盖已有备份。"""
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    # mode=ro避免误建库；SQLite backup API纳入已提交WAL数据。
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        table = source.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()
        versions = [r[0] for r in source.execute("SELECT version_num FROM alembic_version")] if table else []
        # demo 迁移是 v0.3 的后继，Alembic 只保存当前 head，不应每次重启重复备份。
        if any(v in {V03_REVISION, "d03demo001", "d04data001"} for v in versions):
            return None
        folder = db_path.parent / "migration_backups"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = folder / f"pre-v03-{stamp}-{uuid4().hex}.db"
        # 文件名含UUID且仍以排他创建防止覆盖。
        with target.open("xb"):
            pass
        with sqlite3.connect(target) as destination:
            source.backup(destination)
            check = destination.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError("升级前数据库备份完整性检查失败，已停止迁移")
        metadata = {"source": str(db_path.resolve()), "backup": str(target.resolve()), "versions": versions, "integrity_check": check}
        target.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return target


def backup_before_v04(db_path: Path) -> Path | None:
    """v0.4只在升级前备份一次；任何失败阻止迁移，保留原库和密钥。"""
    if not db_path.exists() or not db_path.stat().st_size:
        return None
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        exists = source.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()
        if not exists:
            return None
        versions = [r[0] for r in source.execute("SELECT version_num FROM alembic_version")]
        if "d04data001" in versions:
            return None
        folder = db_path.parent / "migration_backups"
        folder.mkdir(exist_ok=True)
        target = folder / f"pre-v04-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}.db"
        with target.open("xb"):
            pass
        with sqlite3.connect(target) as destination:
            source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("v0.4升级备份完整性失败，迁移已阻止")
        target.with_suffix(".json").write_text(json.dumps({"source": str(db_path), "backup": str(target), "versions": versions, "integrity_check": "ok"}, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
