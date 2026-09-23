"""
模块名称：test_mode.py
所属层级：基础能力层（core）
功能说明：集中实现测试模式、测试账号、测试患者三重守卫，以及账号级有效日期。

安全约束：
    - ETMMS_TEST_MODE 默认关闭；
    - 测试能力必须同时满足“测试模式 + 测试账号 + 测试患者”；
    - 模拟日期下不得读取或写入真实患者的日期相关临床流程；
    - 本模块不修改领域状态机，测试跳转由专用接口显式处理。

修改历史：
    - 2026-09-24  v1.0  第一批测试可用性实现
"""

from __future__ import annotations

from datetime import date

from app.config import get_settings
from app.core.clock import system_clock
from app.core.exceptions import ForbiddenError
from app.models.patient import Patient
from app.models.user import User


def test_capability_enabled(user: User) -> bool:
    """判断当前账号是否同时满足测试模式与测试账号双条件。"""
    return get_settings().test_mode and user.is_test_account


def require_test_account(user: User) -> None:
    """要求测试模式已开启且当前账号为测试账号。"""
    if not get_settings().test_mode:
        raise ForbiddenError("测试模式未开启，当前操作已被阻止。", code="TEST_MODE_DISABLED")
    if not user.is_test_account:
        raise ForbiddenError("当前账号不是测试账号，无法使用测试功能。", code="TEST_ACCOUNT_REQUIRED")


def require_test_patient(patient: Patient) -> None:
    """要求目标患者已被明确标记为测试患者。"""
    if not patient.is_test_patient:
        raise ForbiddenError(
            "该患者不是测试患者，禁止使用测试跳转或模拟日期。",
            code="TEST_PATIENT_REQUIRED",
        )


def effective_today(user: User) -> date:
    """返回该账号的有效日期；测试能力未开启时始终使用真实日期。"""
    if test_capability_enabled(user) and user.simulated_date is not None:
        return user.simulated_date
    return system_clock.today()


def effective_today_for_patient(user: User, patient: Patient) -> date:
    """返回患者流程使用的有效日期，并阻断模拟日期作用于真实患者。"""
    today = effective_today(user)
    if test_capability_enabled(user) and user.simulated_date is not None:
        require_test_patient(patient)
    return today


def simulated_date_for_event(user: User, patient: Patient) -> date | None:
    """返回事件应记录的模拟日期；同时执行真实患者硬阻断。"""
    if not (test_capability_enabled(user) and user.simulated_date is not None):
        return None
    require_test_patient(patient)
    return user.simulated_date
