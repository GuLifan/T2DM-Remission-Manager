"""
模块名称：clock.py
所属层级：基础能力层（core）
功能说明：提供"当前日期/时间"的可注入时钟。

为什么必须注入而不是直接调用 date.today()：
    临床流程大量依赖日期边界（停药满 3 个日历月、观察期到期、随访节奏），
    直接读系统时间会让这些边界无法测试。服务层一律接收 today 参数，
    由调用方（接口层或测试）决定"今天是哪天"。

主要对象：
    - Clock：时钟协议。
    - SystemClock：真实时钟。
    - FrozenClock：测试用冻结时钟。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """时钟协议：任何提供 today()/now() 的对象都可以作为时钟使用。"""

    def today(self) -> date:
        """返回"今天"的日期。"""
        ...

    def now(self) -> datetime:
        """返回当前时刻。"""
        ...


class SystemClock:
    """真实时钟：读取本机时间（生产运行使用）。"""

    def today(self) -> date:
        """返回系统当前日期。"""
        return date.today()

    def now(self) -> datetime:
        """返回系统当前时间。"""
        return datetime.now()


class FrozenClock:
    """冻结时钟：时间由外部指定，保证日期边界测试可复现。"""

    def __init__(self, current: date) -> None:
        # 冻结的日期基准
        self._current = current

    def today(self) -> date:
        """返回冻结日期。"""
        return self._current

    def now(self) -> datetime:
        """返回冻结日期当天 09:00（避免测试出现 00:00 的边界歧义）。"""
        return datetime.combine(self._current, datetime.min.time()).replace(hour=9)

    def set(self, current: date) -> None:
        """调整冻结日期（模拟时间流逝）。"""
        self._current = current

    def advance_days(self, days: int) -> None:
        """把冻结日期向后推进若干天。"""
        self._current = self._current + timedelta(days=days)


# 默认时钟实例：接口层与脚本可以直接使用
system_clock = SystemClock()
