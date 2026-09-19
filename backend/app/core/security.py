"""
模块名称：security.py
所属层级：基础能力层（core）
功能说明：账号相关的密码学原语——密码哈希与校验、会话令牌签发与验证、签名密钥管理。

重要定位（`_SPEC/06` V1.0-Q-03）：
    本模块提供的是**可追溯性与责任绑定**所需的基础防护（密码不可逆存储、令牌防篡改、会话超时），
    **不是**完整的安全边界。软件面向单机/内网运行，正式权限体系与合规加固不在本版本范围。

实现取舍：只使用 Python 标准库（hashlib.scrypt + hmac + secrets），不引入第三方加密依赖，
减少打包体积与供应链风险。

主要函数：
    - hash_password()：生成密码哈希（scrypt 加盐）。
    - verify_password()：校验明文密码是否匹配哈希。
    - create_session_token() / verify_session_token()：签发与验证会话令牌。
    - get_secret_key()：读取或首次生成签名密钥。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

# scrypt 参数：n=2^14 在普通笔记本上约几十毫秒，兼顾防护强度与登录体验
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

# 令牌前缀：便于将来平滑更换令牌格式
TOKEN_PREFIX = "v1"


def _b64encode(raw: bytes) -> str:
    """URL 安全 base64 编码（去掉填充符，便于放进 HTTP 头）。"""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    """URL 安全 base64 解码（自动补齐填充符）。"""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    """生成密码哈希。

    返回格式：`scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`
    ——把参数一并存入，便于日后提高强度时仍能校验旧密码。

    参数:
        password (str): 医生设置的明文密码。

    返回:
        str: 可直接写入数据库的哈希字符串。
    """
    if not password:
        raise ValueError("密码不能为空。")
    # 每个账号使用独立随机盐，防止彩虹表与同密码同哈希
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """校验明文密码是否与存储的哈希匹配。

    为什么用 compare_digest：逐字节比较会泄漏时间信息，必须使用恒定时间比较。

    参数:
        password (str): 医生输入的明文密码。
        stored_hash (str): 数据库中保存的哈希字符串。

    返回:
        bool: 匹配返回 True；格式不合法或参数不支持时返回 False（不抛异常，避免登录接口泄漏内部细节）。
    """
    try:
        scheme, n_text, r_text, p_text, salt_text, hash_text = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = _b64decode(salt_text)
        expected = _b64decode(hash_text)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_text),
            r=int(r_text),
            p=int(p_text),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        # 哈希被破坏或格式不识别，一律视为校验失败
        return False
    return hmac.compare_digest(derived, expected)


@lru_cache(maxsize=1)
def get_secret_key() -> bytes:
    """读取签名密钥；首次运行时生成并落盘。

    为什么要落盘而不是每次启动随机生成：否则服务重启后所有会话立即失效，
    医生在网络抖动或服务重启后会被强制退出。

    位置：数据目录下的 `secret.key`（开发态在 data/runtime，便携版在用户数据目录）。
    """
    settings = get_settings()
    settings.ensure_dirs()
    key_path: Path = settings.data_dir / "secret.key"
    if key_path.exists():
        return key_path.read_bytes()
    # 48 字节远超 HMAC-SHA256 所需的密钥长度
    key = secrets.token_bytes(48)
    key_path.write_bytes(key)
    return key


def create_session_token(user_id: int, hours: int | None = None) -> tuple[str, int]:
    """签发会话令牌。

    令牌结构：`v1.<payload_b64>.<signature_b64>`，其中 payload 为 JSON（含用户与过期时间）。
    签名使用 HMAC-SHA256，任何字段被篡改都会导致校验失败。

    参数:
        user_id (int): 账号主键。
        hours (int | None): 有效期小时数，默认取配置中的会话时长。

    返回:
        tuple[str, int]: 令牌字符串、过期时间戳（Unix 秒，供前端提示）。
    """
    settings = get_settings()
    valid_hours = hours if hours is not None else settings.session_hours
    expires_at = int(time.time()) + valid_hours * 3600
    payload = {"uid": user_id, "iat": int(time.time()), "exp": expires_at}
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_text = _b64encode(payload_bytes)
    signature = hmac.new(get_secret_key(), payload_text.encode("ascii"), hashlib.sha256).digest()
    return f"{TOKEN_PREFIX}.{payload_text}.{_b64encode(signature)}", expires_at


def verify_session_token(token: str) -> int | None:
    """验证会话令牌并返回用户主键。

    参数:
        token (str): 前端携带的令牌。

    返回:
        int | None: 校验通过且未过期时返回用户主键；否则返回 None。
    """
    try:
        prefix, payload_text, signature_text = token.split(".")
        if prefix != TOKEN_PREFIX:
            return None
        expected = hmac.new(get_secret_key(), payload_text.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_text)):
            return None
        payload = json.loads(_b64decode(payload_text).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return int(payload["uid"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        # 任何解析失败都视为无效令牌，不向调用方暴露细节
        return None
