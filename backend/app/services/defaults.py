"""
模块名称：defaults.py
所属层级：临床服务层（services）
功能说明：临床默认值常量（唯一来源）。

为什么集中：V0.1 把"12 周"散落在 10 处代码里，将来裁决调整时极易漏改
（V0.1 风险报告 R2 记录的问题）。V1.0 只在本文件定义。

临床依据：`_SPEC/06` 裁决——血糖稳定与缓解诱导两阶段正式复评默认间隔均为 12 周，
          医生可调整；缓解后随访第 1 年每 6 个月、第 2 年每 6 个月、满 2 年后每年。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date, timedelta

# 正式复评默认间隔（周）：两个主动管理阶段一致
REVIEW_INTERVAL_WEEKS = 12

# 缓解后随访月份锚点（自缓解确认日起算）：第 1 年 6/12 个月，第 2 年 18/24 个月
FOLLOWUP_MONTH_OFFSETS: tuple[int, ...] = (6, 12, 18, 24)
# 满 2 年后改为每年一次
ANNUAL_FOLLOWUP_MONTHS = 12


def default_next_review_date(today: date) -> date:
    """按默认间隔计算下次正式复评日期（医生可在界面上覆盖）。"""
    return today + timedelta(weeks=REVIEW_INTERVAL_WEEKS)


def next_followup_date(remission_date: date, today: date) -> date:
    """按随访节奏计算下一次随访日期。

    规则：缓解确认后第 6、12、18、24 个月各一次；满 2 年后每年一次。
    返回"今天之后最早的那个锚点"；若今天已超过第 24 个月，则按整年顺延。

    参数:
        remission_date (date): 缓解确认日期。
        today (date): 当前日期（由 Clock 注入）。
    """
    from app.utils.date_utils import add_months_clamped

    # 前两年：按固定锚点找下一个未到的随访日
    for months in FOLLOWUP_MONTH_OFFSETS:
        candidate = add_months_clamped(remission_date, months)
        if candidate > today:
            return candidate
    # 满 2 年后：从第 24 个月起按年顺延
    candidate = add_months_clamped(remission_date, FOLLOWUP_MONTH_OFFSETS[-1])
    while candidate <= today:
        candidate = add_months_clamped(candidate, ANNUAL_FOLLOWUP_MONTHS)
    return candidate
