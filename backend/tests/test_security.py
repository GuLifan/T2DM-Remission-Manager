"""
模块名称：test_security.py
所属层级：测试（tests）
功能说明：验证密码哈希与会话令牌的正确行为与防御行为。

覆盖内容：
    1. 同一密码两次哈希不同（随机盐生效），但都能校验通过；
    2. 错误密码、被破坏的哈希格式一律拒绝；
    3. 令牌可签发与验证，篡改后失效，过期后失效。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from app.core import security


def test_password_hash_uses_salt_and_verifies() -> None:
    """密码必须加盐存储，且能正确校验。"""
    password = "Test-Passw0rd"
    first = security.hash_password(password)
    second = security.hash_password(password)

    # 随机盐：同密码两次哈希必须不同（否则可被彩虹表攻击）
    assert first != second
    # 哈希中不得出现明文
    assert password not in first
    # 两种哈希都能校验通过
    assert security.verify_password(password, first)
    assert security.verify_password(password, second)


def test_password_verify_rejects_wrong_or_broken_hash() -> None:
    """错误密码与损坏的哈希都必须返回 False（不抛异常）。"""
    stored = security.hash_password("Test-Passw0rd")
    assert not security.verify_password("wrong-password", stored)
    # 格式不合法（例如系统保留账号的占位哈希）
    assert not security.verify_password("anything", "!disabled")
    # 字段数量不对
    assert not security.verify_password("anything", "scrypt$1$2$3")


def test_session_token_round_trip(client) -> None:
    """令牌签发后应能验证出同一个用户主键。"""
    token, expires_at = security.create_session_token(42)
    assert expires_at > 0
    assert security.verify_session_token(token) == 42


def test_session_token_rejects_tampering(client) -> None:
    """篡改载荷或签名后，令牌必须失效。"""
    token, _ = security.create_session_token(42)
    prefix, payload, signature = token.split(".")

    # 改载荷（换一个 base64 内容）——签名不匹配
    tampered_payload = security._b64encode(b'{"uid":1,"exp":9999999999}')
    assert security.verify_session_token(f"{prefix}.{tampered_payload}.{signature}") is None
    # 改签名
    assert security.verify_session_token(f"{prefix}.{payload}.AAAA") is None
    # 结构不对
    assert security.verify_session_token("not-a-token") is None


def test_session_token_expires(client) -> None:
    """过期令牌必须失效。"""
    # 有效期为负数即表示"已过期"，用于验证过期分支
    token, _ = security.create_session_token(42, hours=-1)
    assert security.verify_session_token(token) is None
