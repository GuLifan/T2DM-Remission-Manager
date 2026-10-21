"""后台管理安全检查：Windows 只验证逻辑，Linux 另外验证真实锁与进程会话。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_service", ROOT / "scripts/demo_service.py")
svc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(svc)


def record():
    return {"project": str(svc.ROOT), "pid": 1234, "start_ticks": "4567", "port": 8088, "boot_id": "boot-a"}


def identity(**overrides):
    return {"pid": 1234, "start_ticks": "4567", "boot_id": "boot-a", "cwd": str(svc.BACKEND),
            "argv": ["python", *svc.expected_command(8088)], **overrides}


@pytest.mark.parametrize("change", [
    {"start_ticks": "9999"}, {"boot_id": "boot-b"}, {"cwd": "/another/project/backend"},
    {"argv": ["python", *svc.expected_command(9090)]}, {"argv": ["python", "-m", "another_app"]},
])
def test_pid_reuse_reboot_wrong_project_or_command_is_never_managed(monkeypatch, change):
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity(**change))
    assert not svc.record_matches(record())


def test_valid_identity_matches(monkeypatch):
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    assert svc.record_matches(record())


def test_duplicate_start_never_spawns(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    monkeypatch.setattr(svc, "owns_listener", lambda pid, port: True)
    monkeypatch.setattr(svc, "healthy", lambda port: True)
    spawn = Mock(side_effect=AssertionError("不能重复启动"))
    monkeypatch.setattr(svc.subprocess, "Popen", spawn)
    assert svc.start_service(8088, p, tmp_path / "log") == 0
    spawn.assert_not_called()


def test_foreign_listener_is_not_started_or_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "port_available", lambda port: False)
    spawn = Mock(side_effect=AssertionError("端口已占用"))
    monkeypatch.setattr(svc.subprocess, "Popen", spawn)
    assert svc.start_service(8088, tmp_path / "process.json", tmp_path / "log") == 1
    spawn.assert_not_called()


def test_unhealthy_existing_process_is_not_duplicated(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    monkeypatch.setattr(svc, "owns_listener", lambda pid, port: False)
    monkeypatch.setattr(svc, "healthy", lambda port: True)  # 别的服务健康，也不能算本实例成功。
    spawn = Mock(side_effect=AssertionError("不能重复启动"))
    monkeypatch.setattr(svc.subprocess, "Popen", spawn)
    assert svc.start_service(8088, p, tmp_path / "log") == 1
    assert svc.status_service(8088, p, tmp_path / "log") == 1
    spawn.assert_not_called()


def test_port_change_does_not_start_another_worker(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    assert svc.start_service(9090, p, tmp_path / "log") == 1


@pytest.mark.parametrize("content", ["{", "[]", json.dumps({"pid": 1}),
                                     json.dumps({**record(), "project": "/other/project"})])
def test_invalid_records_fail_closed(tmp_path, content):
    p = tmp_path / "process.json"
    p.write_text(content)
    with pytest.raises(RuntimeError, match="无法核对"):
        svc.load_record(p)
    assert p.read_text() == content


def test_reused_pid_is_not_signalled(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity(start_ticks="8888"))
    handle = Mock(side_effect=AssertionError("不能打开其他进程"))
    monkeypatch.setattr(svc.os, "pidfd_open", handle, raising=False)
    assert svc.stop_service(p) == 0
    handle.assert_not_called()


def test_identity_rechecked_after_opening_handle(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    monkeypatch.setattr(svc, "record_matches", Mock(side_effect=[True, False]))
    monkeypatch.setattr(svc.os, "pidfd_open", lambda pid: 333, raising=False)
    close = Mock()
    send = Mock()
    monkeypatch.setattr(svc.os, "close", close)
    monkeypatch.setattr(svc.signal, "pidfd_send_signal", send, raising=False)
    with pytest.raises(RuntimeError, match="身份发生变化"):
        svc.stop_service(p)
    send.assert_not_called()
    close.assert_called_once_with(333)


def test_successful_stop_uses_process_handle_and_preserves_other_files(tmp_path, monkeypatch):
    p = tmp_path / "process.json"
    svc.write_record(p, record())
    db = tmp_path / "etmms.db"
    db.write_bytes(b"do-not-change")
    monkeypatch.setattr(svc, "record_matches", Mock(side_effect=[True, True, False]))
    monkeypatch.setattr(svc.os, "pidfd_open", lambda pid: 333, raising=False)
    monkeypatch.setattr(svc.os, "close", Mock())
    send = Mock()
    monkeypatch.setattr(svc.signal, "pidfd_send_signal", send, raising=False)
    assert svc.stop_service(p) == 0
    send.assert_called_once_with(333, svc.signal.SIGTERM)
    assert not p.exists()
    assert db.read_bytes() == b"do-not-change"


def test_child_exits_during_start_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "port_available", lambda port: True)
    child = Mock(returncode=1)
    child.poll.return_value = 1
    monkeypatch.setattr(svc.subprocess, "Popen", Mock(return_value=child))
    with pytest.raises(RuntimeError, match="启动退出"):
        svc.start_service(8088, tmp_path / "process.json", tmp_path / "log")
    assert not (tmp_path / "process.json").exists()


def test_new_child_is_detached_and_healthy_before_success(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "port_available", lambda port: True)
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    monkeypatch.setattr(svc, "owns_listener", lambda pid, port: True)
    monkeypatch.setattr(svc, "healthy", lambda port: True)
    child = Mock(pid=1234)
    child.poll.return_value = None
    spawn = Mock(return_value=child)
    monkeypatch.setattr(svc.subprocess, "Popen", spawn)
    p = tmp_path / "process.json"
    assert svc.start_service(8088, p, tmp_path / "log") == 0
    kwargs = spawn.call_args.kwargs
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == svc.subprocess.DEVNULL
    assert kwargs["close_fds"] is True
    assert kwargs["env"]["PORT"] == "8088"
    assert kwargs["stdout"] is kwargs["stderr"]
    assert svc.load_record(p) == record()


def test_lock_waits_for_other_operation_and_releases(tmp_path, monkeypatch):
    lock = Mock(side_effect=[BlockingIOError, None, None])
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=lock, LOCK_EX=2, LOCK_NB=4, LOCK_UN=8))
    sleep = Mock()
    monkeypatch.setattr(svc.time, "sleep", sleep)
    with svc.service_lock(tmp_path / "lock"):
        assert lock.call_count == 2  # 首次争用不能执行操作，等获取锁后才能进入。
    assert lock.call_count == 3
    assert lock.call_args.args[1] == 8
    sleep.assert_called_once_with(0.2)


def test_start_timeout_stops_only_the_new_child(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "port_available", lambda port: True)
    monkeypatch.setattr(svc, "process_identity", lambda pid: identity())
    monkeypatch.setattr(svc, "owns_listener", lambda pid, port: False)
    monkeypatch.setattr(svc, "healthy", lambda port: True)
    monkeypatch.setattr(svc.time, "monotonic", Mock(side_effect=[0, 0, 31]))
    monkeypatch.setattr(svc.time, "sleep", Mock())
    child = Mock(pid=1234)
    child.poll.return_value = None
    monkeypatch.setattr(svc.subprocess, "Popen", Mock(return_value=child))
    p = tmp_path / "process.json"
    with pytest.raises(RuntimeError, match="本次新建服务已停止"):
        svc.start_service(8088, p, tmp_path / "log")
    child.terminate.assert_called_once()
    child.wait.assert_called_once_with(timeout=10)
    assert not p.exists()


def test_lock_released_even_when_operation_fails(tmp_path, monkeypatch):
    lock = Mock()
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=lock, LOCK_EX=2, LOCK_NB=4, LOCK_UN=8))
    with pytest.raises(RuntimeError, match="模拟失败"), svc.service_lock(tmp_path / "lock"):
        raise RuntimeError("模拟失败")
    assert lock.call_args.args[1] == 8
