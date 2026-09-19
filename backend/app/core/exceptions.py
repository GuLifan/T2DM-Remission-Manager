"""
模块名称：exceptions.py
所属层级：基础能力层（core）
功能说明：定义业务异常体系。业务异常携带"医生可读的自然语言说明"，
          由 main.py 注册的异常处理器转换成统一响应，禁止把工程堆栈暴露到前台。

主要对象：
    - EtmmsError：所有业务异常基类（含 code 与 message）。
    - BusinessRuleError：违反临床流程或业务规则（HTTP 422）。
    - NotFoundError：对象不存在（HTTP 404）。
    - AuthError：未登录或凭据无效（HTTP 401）。
    - ConflictError：状态冲突或重复提交（HTTP 409）。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations


class EtmmsError(Exception):
    """业务异常基类。

    属性:
        code (str): 内部错误码，仅用于日志与排查，不展示给医生。
        message (str): 医生可读的中文说明，直接展示在前台。
        status_code (int): 对应的 HTTP 状态码。
    """

    status_code: int = 400

    def __init__(self, message: str, code: str = "ETMMS_ERROR") -> None:
        # 交给 Exception 保存原始信息，便于日志输出
        super().__init__(message)
        self.message = message
        self.code = code

    def to_payload(self) -> dict[str, str]:
        """转换为响应体：前台只使用 detail（自然语言）。"""
        return {"detail": self.message, "code": self.code}


class BusinessRuleError(EtmmsError):
    """违反临床流程或业务规则时抛出（不可跳过的状态、缺少必需输入等）。"""

    status_code = 422

    def __init__(self, message: str, code: str = "BUSINESS_RULE") -> None:
        super().__init__(message, code)


class NotFoundError(EtmmsError):
    """请求的对象不存在。"""

    status_code = 404

    def __init__(self, message: str = "未找到对应的记录。", code: str = "NOT_FOUND") -> None:
        super().__init__(message, code)


class AuthError(EtmmsError):
    """未登录、会话过期或凭据无效。"""

    status_code = 401

    def __init__(self, message: str = "登录状态已失效，请重新登录。", code: str = "UNAUTHORIZED") -> None:
        super().__init__(message, code)


class ConflictError(EtmmsError):
    """状态冲突、重复提交或并发修改。"""

    status_code = 409

    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(message, code)
