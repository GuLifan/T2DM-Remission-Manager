"""
模块名称：test_smoke.py
所属层级：测试（tests）
功能说明：M1 工程基线冒烟测试——服务可用、数据库结构就位、约束生效。

覆盖内容：
    1. 健康检查接口可用；
    2. 五张核心表已由迁移创建；
    3. SQLite 外键约束已启用（事件必须挂在真实患者与账号上）。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

# 迁移必须创建的核心表
EXPECTED_TABLES = {"users", "patients", "events", "audit_log", "app_meta", "alembic_version"}


def test_health_ok(client) -> None:
    """健康检查返回 ok 与版本号。"""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"].startswith("1.")


def test_schema_created_by_migration(client, db_session) -> None:
    """迁移已创建全部核心表。"""
    inspector = inspect(db_session.get_bind())
    table_names = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - table_names
    assert not missing, f"缺少表：{missing}"
    patient_columns = {column["name"] for column in inspector.get_columns("patients")}
    patient_indexes = {index["name"] for index in inspector.get_indexes("patients")}
    assert "owner_id" in patient_columns
    assert "ix_patients_owner_id" in patient_indexes


def test_sqlite_foreign_keys_enabled(client, db_session) -> None:
    """外键约束已启用：插入指向不存在患者的事件必须失败。

    为什么必须测：SQLite 默认关闭外键；若关闭，事件可以挂在幽灵患者上，
    临床可追溯性会被破坏。
    """
    # 先准备一条账号记录作为操作者
    db_session.execute(
        text(
            # failed_login_count 为 NOT NULL，必须给出；locked_until 允许为空
            "INSERT INTO users (username, display_name, password_hash, role, is_active, "
            "failed_login_count, created_at) "
            "VALUES ('t_doctor', '测试医生', 'x', 'doctor', 1, 0, '2026-09-20 09:00:00')"
        )
    )
    db_session.commit()
    operator_id = db_session.execute(text("SELECT id FROM users WHERE username = 't_doctor'")).scalar_one()
    # 明确断言完整性约束错误，而不是笼统的 Exception
    with pytest.raises(IntegrityError):
        # patient_id=999 不存在，外键约束应当拒绝
        db_session.execute(
            text(
                "INSERT INTO events (patient_id, operator_id, source, rule_id, source_state, target_state, output_text, created_at) "
                "VALUES (999, :op, 'doctor', 'E1-B01', 'ST10', 'ST20', '测试', '2026-09-20 09:00:00')"
            ),
            {"op": operator_id},
        )
        db_session.commit()
    db_session.rollback()
