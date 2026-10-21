"""维护命令：终端初始化管理员、SQLite 一致性备份；密码交互输入不进入命令历史。"""

from __future__ import annotations

import argparse
import getpass
import sqlite3
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.models.user import User
from app.repository.audit import write_audit
from app.repository.database import SessionLocal
from app.repository.migrations import run_migrations
from app.repository.users import create_user, system_user


def main() -> None:
    parser = argparse.ArgumentParser(description="ETMMS demo 维护工具")
    parser.add_argument("action", choices=["init-admin", "backup"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "backup":
        if not args.output or args.output.exists():
            parser.error("--output 必须是不存在的备份文件路径")
        if not get_settings().db_path.is_file():
            parser.error("运行数据库不存在，禁止创建空库冒充备份")
        # SQLite backup 包含 WAL 中已提交记录，不能直接复制正在使用的主文件。
        with (
            sqlite3.connect(get_settings().db_path.resolve().as_uri() + "?mode=ro", uri=True) as source,
            sqlite3.connect(args.output) as target,
        ):
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("备份完整性检查失败")
        print("备份完成；签名密钥请单独安全保存。")
        return
    run_migrations()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.role == "admin")):
            parser.error("管理员已初始化，请使用已有账号登录")
        username = input("管理员登录名（至少3字符）：").strip()
        password = getpass.getpass("密码（至少12位）：")
        confirm = getpass.getpass("再次输入密码：")
        if len(username) < 3 or len(username) > 64 or len(password) < 12 or len(password) > 128 or password != confirm:
            parser.error("登录名/密码长度或确认不符合要求")
        admin = create_user(db, username=username, display_name="系统管理员", password=password, role="admin")
        admin.is_test_account = True
        system_user(db)
        write_audit(db, action="demo_admin_init", operator_id=admin.id)
        db.commit()
    print("管理员已初始化，可登录后创建邀请码。")


if __name__ == "__main__":
    main()
