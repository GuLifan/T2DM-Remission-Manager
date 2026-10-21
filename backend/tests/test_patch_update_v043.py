"""补丁应用/回退真实文件测试，使用独立伪工程和SQLite，不操作开发或云端服务。"""

import importlib.util
import json
import socket
import sqlite3
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "etmms_patch", Path(__file__).resolve().parents[2] / "scripts/apply_update.py"
)
patch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(patch)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.delenv("ETMMS_DATA_DIR", raising=False)
    monkeypatch.delenv("ETMMS_DB_FILENAME", raising=False)
    project, bundle, data = tmp_path / "project", tmp_path / "bundle", tmp_path / "private-data"
    data.mkdir()
    (project / "backend/app").mkdir(parents=True)
    (project / "frontend/dist/assets").mkdir(parents=True)
    (project / "resources/evidence").mkdir(parents=True)
    (project / "resources/evidence/private.md").write_text("Private original must remain", encoding="utf-8")
    (project / "backend/.env").write_text(f"ETMMS_DATA_DIR={data.as_posix()}\nETMMS_DEMO_MODE=true\n", encoding="utf-8")
    (data / "secret.key").write_bytes(b"isolated-fixture-key-not-a-live-key")
    with sqlite3.connect(data / "etmms.db") as db:
        db.execute("CREATE TABLE patients(id INTEGER PRIMARY KEY,name TEXT)")
        db.execute("INSERT INTO patients VALUES(1,'synthetic')")
    (project / "backend/app/__init__.py").write_text('__version__ = "0.4.2"\n', encoding="utf-8")
    (project / "README.md").write_text("Old readme", encoding="utf-8")
    (project / "frontend/dist/assets/old.js").write_text("old build", encoding="utf-8")
    entries = []
    for name, content in {
        "backend/app/__init__.py": '__version__ = "0.4.3"\n',
        "README.md": "New readme",
        "frontend/dist/assets/new.js": "new build",
    }.items():
        source = bundle / "payload" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(content, encoding="utf-8")
        old = project / name
        entries.append(
            {
                "path": name,
                "sha256": patch.digest(source),
                "previous_sha256": [patch.digest(old)] if old.exists() else [],
            }
        )
    manifest = {
        "from_version": "0.4.2",
        "to_version": "0.4.3",
        "files": entries,
        "remove": [
            {
                "path": "frontend/dist/assets/old.js",
                "previous_sha256": [patch.digest(project / "frontend/dist/assets/old.js")],
            }
        ],
    }
    patch.write_json(bundle / "manifest.json", manifest)
    return project, bundle, data, manifest


def test_optional_public_document_can_be_absent_from_official_private_zip(tree):
    project, bundle, _data, manifest = tree
    document = bundle / "payload/AGENTS.md"
    document.write_text("Public instructions", encoding="utf-8")
    manifest["files"].append(
        {
            "path": "AGENTS.md",
            "sha256": patch.digest(document),
            "previous_sha256": ["a" * 64],
            "required_in_base": False,
        }
    )
    patch.write_json(bundle / "manifest.json", manifest)
    assert patch.apply(bundle, project, dry_run=True) is None
    manifest["files"][-1]["required_in_base"] = True
    patch.write_json(bundle / "manifest.json", manifest)
    with pytest.raises(patch.PatchError, match="Missing base file"):
        patch.apply(bundle, project, dry_run=True)


def test_apply_preserves_configuration_key_data_sources_and_rollback_preserves_new_records(tree):
    project, bundle, data, _ = tree
    before = [
        (p, p.read_bytes())
        for p in [
            project / "backend/.env",
            data / "etmms.db",
            data / "secret.key",
            project / "resources/evidence/private.md",
        ]
    ]
    assert patch.apply(bundle, project, dry_run=True) is None
    assert not (project / ".updates").exists()
    backup = patch.apply(bundle, project, port=0)
    assert patch.version(project) == "0.4.3"
    assert not (project / "frontend/dist/assets/old.js").exists()
    assert (project / "frontend/dist/assets/new.js").exists()
    assert all(p.read_bytes() == b for p, b in before)
    with pytest.raises(patch.PatchError, match="Base version mismatch"):
        patch.apply(bundle, project, port=0)
    # 发布后新产生的临床资料不能因为代码回退而被备份库覆盖。
    with sqlite3.connect(data / "etmms.db") as db:
        db.execute("INSERT INTO patients VALUES(2,'new synthetic')")
    patch.rollback(project, backup, port=0)
    assert patch.version(project) == "0.4.2"
    assert (project / "frontend/dist/assets/old.js").read_text() == "old build"
    assert not (project / "frontend/dist/assets/new.js").exists()
    with sqlite3.connect(data / "etmms.db") as db:
        assert db.execute("SELECT count(*) FROM patients").fetchone()[0] == 2
    assert (backup / "private/secret.key").read_bytes() == (data / "secret.key").read_bytes()


def test_modified_base_rejected_before_backup_or_mutation(tree):
    project, bundle, _, _ = tree
    (project / "README.md").write_text("manual change")
    with pytest.raises(patch.PatchError, match="Modified file"):
        patch.apply(bundle, project, port=0)
    assert patch.version(project) == "0.4.2" and not (project / ".updates").exists()


def test_changed_payload_rejected(tree):
    project, bundle, _, _ = tree
    (bundle / "payload/README.md").write_text("tampered")
    with pytest.raises(patch.PatchError, match="Payload hash mismatch"):
        patch.apply(bundle, project, port=0)
    assert (project / "README.md").read_text() == "Old readme"


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/tmp/escape",
        "backend/.env",
        "data/runtime/x",
        "resources/evidence/private.md",
        "backend/.venv/x",
        "private.key",
    ],
)
def test_protected_or_escaping_paths_rejected(tree, name):
    project, _, _, _ = tree
    with pytest.raises(patch.PatchError):
        patch.safe_path(project, name)


def test_listening_service_blocks_application(tree):
    project, bundle, _, _ = tree
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with pytest.raises(patch.PatchError, match="Stop service first"):
            patch.apply(bundle, project, listener.getsockname()[1])
    assert not (project / ".updates").exists()


def test_interrupted_replacement_restores_all_touched_files(tree, monkeypatch):
    project, bundle, data, _ = tree
    original = patch.os.replace
    calls = 0

    def interrupt(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected interrupted copy")
        return original(source, target)

    monkeypatch.setattr(patch.os, "replace", interrupt)
    with pytest.raises(OSError, match="injected"):
        patch.apply(bundle, project, port=0)
    assert patch.version(project) == "0.4.2"
    assert (project / "README.md").read_text() == "Old readme"
    assert not (project / "frontend/dist/assets/new.js").exists()
    assert (project / "frontend/dist/assets/old.js").exists()
    with sqlite3.connect(data / "etmms.db") as db:
        assert db.execute("SELECT count(*) FROM patients").fetchone()[0] == 1


def test_rollback_refuses_later_manual_changes(tree):
    project, bundle, _, _ = tree
    backup = patch.apply(bundle, project, port=0)
    (project / "README.md").write_text("new manual change")
    with pytest.raises(patch.PatchError, match="Modified after update"):
        patch.rollback(project, backup, port=0)
    assert patch.version(project) == "0.4.3"
    assert json.loads((backup / "state.json").read_text(encoding="utf-8"))["status"] == "applied"
