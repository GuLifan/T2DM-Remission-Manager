"""Linux 后台服务管理：仅启动/检查/安全停止，不导入应用或触碰临床数据库。

进程身份由 PID、Linux 启动时刻、工作目录和完整 Uvicorn 参数共同核对。
停止使用 pidfd 将信号绑定到具体进程，避免 PID 复用误杀；不提供强杀操作。
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def process_identity(pid: int) -> dict | None:
    """读取 /proc 的进程实例身份；进程消失或成为僵尸都视为已停止。"""
    try:
        folder = Path("/proc") / str(pid)
        fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {
            "pid": pid,
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "start_ticks": fields[19],  # stat 第22列，拆去 pid/comm 后的第20项。
            "cwd": str((folder / "cwd").resolve(strict=True)),
            "argv": (folder / "cmdline").read_bytes().decode().rstrip("\0").split("\0"),
        }
    except (OSError, IndexError, UnicodeError):
        return None


def expected_command(port: int) -> list[str]:
    return ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port),
            "--workers", "1", "--no-proxy-headers"]


def is_our_process(identity: dict | None, port: int) -> bool:
    """不只凭进程名或端口识别；其他工程的 uvicorn 不属于本脚本。"""
    return bool(identity and identity["cwd"] == str(BACKEND)
                and identity["argv"][1:] == expected_command(port))


def record_matches(record: dict | None) -> bool:
    if not record or record.get("project") != str(ROOT):
        return False
    actual = process_identity(record["pid"])
    return bool(is_our_process(actual, record["port"])
                and actual["start_ticks"] == record["start_ticks"]
                and actual["boot_id"] == record.get("boot_id"))


def owns_listener(pid: int, port: int) -> bool:
    """健康响应必须来自记录的进程，不能将同时抢占端口的别的服务算为成功。"""
    try:
        inodes = set()
        for row in Path("/proc/net/tcp").read_text().splitlines()[1:]:
            columns = row.split()
            if columns[3] == "0A" and int(columns[1].split(":")[1], 16) == port:
                inodes.add(columns[9])
        for descriptor in (Path("/proc") / str(pid) / "fd").iterdir():
            try:
                target = os.readlink(descriptor)
            except OSError:
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                return True
    except (OSError, ValueError, IndexError):
        pass
    return False


def product_version() -> str:
    """只读当前代码的版本，不导入应用配置或初始化数据库。"""
    import ast
    module = ast.parse((Path(__file__).resolve().parents[1] / "backend/app/__init__.py").read_text(encoding="utf-8"))
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in statement.targets):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise RuntimeError("无法读取当前产品版本")


def healthy(port: int) -> bool:
    """绕过终端代理设置，只检查本机健康接口；不发送账号或邀请码。"""
    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            body = json.loads(response.read(4096))
            return response.status == 200 and body == {"status": "ok", "version": product_version()}
    except (OSError, ValueError):
        return False


def port_available(port: int) -> bool:
    # 检查所有 IPv4 地址；不根据某个公网地址或别的服务健康响应推断可启动。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("0.0.0.0", port))
            return True
        except OSError as error:
            if error.errno in (errno.EADDRINUSE, errno.EACCES):
                return False
            raise


@contextmanager
def service_lock(path: Path):
    """同一数据目录串行处理操作，防止两次点击同时启动；锁文件永不删除。"""
    import fcntl

    with path.open("a", encoding="utf-8") as lock:
        deadline = time.monotonic() + 40
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("另一次服务操作仍在进行，请稍后重试。") from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def load_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        valid = (type(record["pid"]) is int and record["pid"] > 1
                 and type(record["port"]) is int and 1 <= record["port"] <= 65535
                 and isinstance(record["start_ticks"], str) and record["start_ticks"].isdigit()
                 and isinstance(record.get("boot_id"), str) and bool(record["boot_id"]))
        if not valid or record.get("project") != str(ROOT):
            raise ValueError
        return record
    except (ValueError, KeyError, TypeError):
        raise RuntimeError(f"进程记录无法核对，请先检查 {path}；未启动或停止任何进程。") from None


def write_record(path: Path, record: dict) -> None:
    # 同目录原子替换，进程锁保护下不会出现半个 JSON。
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def start_service(port: int, record_path: Path, log_path: Path) -> int:
    record = load_record(record_path)
    if record_matches(record):
        print(f"已有本脚本管理的服务：PID {record['pid']}，端口 {record['port']}；未重复启动。")
        if record["port"] != port:
            print(f"当前请求端口 {port} 与运行端口不同，请先核对配置。")
            return 1
        if not owns_listener(record["pid"], port) or not healthy(port):
            print(f"进程存在但健康检查未通过，请查看日志：{log_path}")
            return 1
        print(f"健康检查通过。日志：{log_path}")
        return 0
    if not port_available(port):
        print(f"端口 {port} 已被占用，本脚本未管理该服务；未重复启动或停止任何进程。")
        print("若是之前手工启动的 ETMMS，请在原终端按 Ctrl+C 停止，然后再次执行 bash start.sh。")
        return 1
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("缺少页面构建产物，请先运行 bash scripts/setup.sh。")
    record_path.unlink(missing_ok=True)  # 只清理身份已失效的本脚本记录，不清理病例数据。
    environment = os.environ.copy()
    environment.update(PORT=str(port), ETMMS_DEMO_MODE="true", TZ="Asia/Shanghai")
    with log_path.open("ab", buffering=0) as log:
        log.write(("\n--- ETMMS 后台启动 " + time.strftime("%Y-%m-%d %H:%M:%S") + " ---\n").encode())
        # 独立会话 + 关闭标准输入 + 输出到文件，不依赖 SSH 终端或 shell 的存活。
        child = subprocess.Popen(["bash", str(ROOT / "entrypoint.sh")], cwd=ROOT,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 env=environment, start_new_session=True, close_fds=True)
    deadline = time.monotonic() + 30
    saved = False
    while time.monotonic() < deadline:
        if child.poll() is not None:
            record_path.unlink(missing_ok=True)
            raise RuntimeError(f"服务启动退出（代码 {child.returncode}），请查看日志：{log_path}")
        identity = process_identity(child.pid)
        if is_our_process(identity, port):
            if not saved:
                write_record(record_path, {"project": str(ROOT), "port": port,
                                           "pid": child.pid, "start_ticks": identity["start_ticks"],
                                           "boot_id": identity["boot_id"]})
                saved = True
            if owns_listener(child.pid, port) and healthy(port) and child.poll() is None:
                print(f"启动成功：PID {child.pid}，端口 {port}，健康检查通过。")
                print(f"日志：{log_path}\n现在可以关闭终端。查看状态：bash start.sh status")
                return 0
        time.sleep(0.2)
    # 该 child 未被回收，PID 不会复用。仅终止本次新建子进程，不动已有服务。
    child.terminate()
    try:
        child.wait(timeout=10)
        record_path.unlink(missing_ok=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"启动健康检查超时，停止也未完成；请查看日志：{log_path}。未强杀。") from None
    raise RuntimeError(f"30秒内健康检查未通过，本次新建服务已停止；请查看日志：{log_path}")


def status_service(port: int, record_path: Path, log_path: Path) -> int:
    record = load_record(record_path)
    if record_matches(record):
        ok = owns_listener(record["pid"], record["port"]) and healthy(record["port"])
        print(f"服务{'运行正常' if ok else '进程存在但健康检查失败'}：PID {record['pid']}，端口 {record['port']}。")
        print(f"日志：{log_path}")
        return 0 if ok else 1
    if not port_available(port):
        print(f"端口 {port} 被占用，但不属于本脚本管理的进程；不会接管或停止。")
        return 1
    print("本脚本管理的服务未运行；可执行 bash start.sh。")
    return 1


def stop_service(record_path: Path) -> int:
    record = load_record(record_path)
    if not record_matches(record):
        print("没有可安全核对的本脚本服务；未向任何进程发送信号。")
        return 0
    # pidfd 针对具体进程实例；打开后再次核对身份，防止两次 /proc 读取之间 PID 复用。
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("当前 Linux 不支持安全进程句柄，未停止进程；请人工核对。")
    try:
        handle = os.pidfd_open(record["pid"])
    except ProcessLookupError:
        record_path.unlink(missing_ok=True)
        print("服务已停止。")
        return 0
    try:
        if not record_matches(record):
            raise RuntimeError("进程身份发生变化，未发送停止信号。")
        with suppress(ProcessLookupError):
            signal.pidfd_send_signal(handle, signal.SIGTERM)
        # 在再次核对后自行退出，同样属于停止完成。
    finally:
        os.close(handle)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not record_matches(record):
            record_path.unlink(missing_ok=True)
            print("服务已正常停止；账号、病例、密钥与日志保留。")
            return 0
        time.sleep(0.2)
    raise RuntimeError("已发送正常停止信号，但15秒内未退出；请查看日志。未自动强杀。")


def main() -> int:
    parser = argparse.ArgumentParser(description="ETMMS Linux 后台服务；默认 start")
    parser.add_argument("action", nargs="?", default="start", choices=["start", "status", "stop"])
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("此脚本仅用于 Linux Devbox；Windows 本地启动请参阅 README。")
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    from app.config import get_settings

    try:
        port = int(os.environ.get("PORT", "8088"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        parser.error("PORT 必须为1—65535的整数。")
    try:
        # 只读取配置模型，不导入数据库或 FastAPI 应用，status/stop 不产生临床记录。
        data = get_settings().data_dir.resolve()
        data.mkdir(parents=True, exist_ok=True)
        record_path, log_path = data / "demo-service.json", data / "demo-service.log"
        with service_lock(data / ".demo-service.lock"):
            if args.action == "start":
                return start_service(port, record_path, log_path)
            if args.action == "status":
                return status_service(port, record_path, log_path)
            return stop_service(record_path)
    except (OSError, RuntimeError) as error:
        print(f"操作未完成：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
