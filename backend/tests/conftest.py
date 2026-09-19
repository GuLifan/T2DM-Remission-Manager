"""
模块名称：conftest.py
所属层级：测试（tests）
功能说明：pytest 公共夹具。

关键设计：
    测试必须在**临时数据目录**中运行，绝不能碰开发数据库或任何真实数据。
    因此在导入应用代码之前先设置环境变量 ETMMS_DATA_DIR。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

# ===== 必须在导入 app.* 之前执行：把数据目录指向临时目录 =====
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="etmms-test-"))
os.environ["ETMMS_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["ETMMS_LOG_LEVEL"] = "WARNING"

# 保证 backend 目录在 sys.path 中（便于直接运行 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """提供带生命周期管理的测试客户端（启动时会自动执行迁移）。"""
    from app.main import app

    # with 语句会触发 lifespan：建目录 + 执行迁移
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    """提供数据库会话（用于直接校验表结构与数据）。"""
    from app.repository.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
