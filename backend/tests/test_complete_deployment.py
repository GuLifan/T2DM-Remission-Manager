"""完整目录替换测试：独立SQLite与伪环境，不操作真实服务/资料。"""

import importlib.util
import json
import socket
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "full_replace", Path(__file__).resolve().parents[2] / "scripts/replace_deployment.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def manifest(release):
    tool.write_json(
        release / "release-manifest.json",
        {
            "version": "0.4.3",
            "files": {
                p.relative_to(release).as_posix(): tool.digest(p)
                for p in release.rglob("*")
                if p.is_file() and p.name != "release-manifest.json"
            },
        },
    )


@pytest.fixture(params=[False, True], ids=["internal-data", "external-data"])
def tree(tmp_path, request, monkeypatch):
    monkeypatch.delenv("ETMMS_DATA_DIR", raising=False)
    monkeypatch.delenv("ETMMS_DB_FILENAME", raising=False)
    old, release = tmp_path / "ETMMS-live", tmp_path / "ETMMS-v0.4.3"
    for folder, version in [(old, "0.4.2"), (release, "0.4.3")]:
        (folder / "backend/app").mkdir(parents=True)
        (folder / "backend/app/__init__.py").write_text(f'__version__="{version}"\n')
        (folder / "backend/pyproject.toml").write_text('[project]\nrequires-python=">=3.13"\ndependencies=[]\n')
        (folder / "start.sh").write_text("#!/bin/bash\n")
        (folder / "frontend/dist").mkdir(parents=True)
        (folder / "frontend/dist/index.html").write_text(version)
        (folder / "resources/evidence").mkdir(parents=True)
        (folder / "resources/evidence/README.md").write_text(version)
    (old / "frontend/dist/obsolete.js").write_text("obsolete asset")
    (old / "old-update.md").write_text("old release guide")
    (old / "resources/evidence/original.pdf").write_bytes(b"private-original")
    (old / "backend/.venv/bin").mkdir(parents=True)
    (old / "backend/.venv/bin/python").write_text("installed environment sentinel")
    data = tmp_path / "external-data" if request.param else old / "data/runtime"
    data.mkdir(parents=True)
    (data / "secret.key").write_bytes(b"isolated-verification-key")
    with sqlite3.connect(data / "etmms.db") as db:
        db.execute("CREATE TABLE alembic_version(version_num TEXT)")
        db.execute("INSERT INTO alembic_version VALUES('d04data001')")
        db.execute("CREATE TABLE facts(value TEXT)")
        db.execute("INSERT INTO facts VALUES('before')")
    db.close()
    (old / "backend/.env").write_text(f"ETMMS_DATA_DIR={data.as_posix()}\nETMMS_DEMO_MODE=true\n")
    manifest(release)
    return old, release, data


def test_full_replacement_removes_old_files_and_preserves_runtime_and_later_records_on_rollback(tree):
    old, release, data = tree
    original = tool.runtime_info(old)["hashes"]
    assert tool.replace(old, release, port=0, dry_run=True) is None
    assert not (old.parent / ".etmms-backups").exists()
    backup = tool.replace(old, release, port=0)
    assert tool.version(old) == "0.4.3"
    assert not (old / "old-update.md").exists() and not (old / "frontend/dist/obsolete.js").exists()
    assert (old / "resources/evidence/README.md").read_text() == "0.4.3"
    assert (old / "resources/evidence/original.pdf").read_bytes() == b"private-original"
    assert tool.runtime_info(old)["hashes"] == original
    assert (old / "backend/.venv/bin/python").read_text() == "installed environment sentinel"
    with sqlite3.connect(data / "etmms.db") as db:
        db.execute("INSERT INTO facts VALUES('after')")
    db.close()
    current = tool.runtime_info(old)["hashes"]
    tool.rollback(old, backup, port=0)
    assert tool.version(old) == "0.4.2" and (old / "old-update.md").exists()
    assert tool.runtime_info(old)["hashes"] == current
    with sqlite3.connect(data / "etmms.db") as db:
        assert db.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 2
    db.close()


def test_tampered_release_rejected(tree):
    old, release, _ = tree
    (release / "start.sh").write_text("changed")
    with pytest.raises(tool.ReplacementError, match="hash mismatch"):
        tool.replace(old, release, port=0)
    assert tool.version(old) == "0.4.2"


def test_extra_release_file_rejected(tree):
    old, release, _ = tree
    (release / "unlisted.txt").write_text("extra")
    with pytest.raises(tool.ReplacementError, match="Unexpected"):
        tool.replace(old, release, port=0)


def test_contained_release_rejected(tree):
    old, _release, _ = tree
    with pytest.raises(tool.ReplacementError, match="Separate"):
        tool.checked_roots(old, old / "new")


def test_dependency_change_rejected(tree):
    old, release, _ = tree
    (release / "backend/pyproject.toml").write_text(
        '[project]\nrequires-python=">=3.13"\ndependencies=["new-library"]\n'
    )
    manifest(release)
    with pytest.raises(tool.ReplacementError, match="dependency mismatch"):
        tool.replace(old, release, port=0)


def test_missing_key_rejected(tree):
    old, release, data = tree
    (data / "secret.key").unlink()
    with pytest.raises(tool.ReplacementError, match="Existing data or key missing"):
        tool.replace(old, release, port=0)


def test_wrong_schema_rejected(tree):
    old, release, data = tree
    with sqlite3.connect(data / "etmms.db") as db:
        db.execute("UPDATE alembic_version SET version_num='unknown'")
    db.close()
    with pytest.raises(tool.ReplacementError, match="Incompatible schema"):
        tool.replace(old, release, port=0)


def test_listening_port_rejected(tree):
    old, release, _ = tree
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(tool.ReplacementError, match="Stop the service"):
            tool.replace(old, release, port=listener.getsockname()[1])


def test_switch_failure_restores_original_directory(tree, monkeypatch):
    old, release, _ = tree
    original = Path.rename

    def fail_switch(path, target):
        if path.name.startswith(".etmms-stage-") and target == old:
            raise OSError("injected switch failure")
        return original(path, target)

    monkeypatch.setattr(Path, "rename", fail_switch)
    with pytest.raises(OSError, match="injected"):
        tool.replace(old, release, port=0)
    assert tool.version(old) == "0.4.2" and (old / "old-update.md").exists()


def test_modified_current_code_blocks_rollback(tree):
    old, release, _ = tree
    backup = tool.replace(old, release, port=0)
    (old / "start.sh").write_text("manual change")
    with pytest.raises(tool.ReplacementError, match="Code changed"):
        tool.rollback(old, backup, port=0)


@pytest.mark.parametrize("bad", ["../outside", "/absolute", ".env", "backend/.venv/key"])
def test_manifest_protected_or_traversal_paths(tree, bad):
    old, release, _ = tree
    data = json.loads((release / "release-manifest.json").read_text())
    data["files"][bad] = "a" * 64
    tool.write_json(release / "release-manifest.json", data)
    with pytest.raises(tool.ReplacementError):
        tool.replace(old, release, port=0)
