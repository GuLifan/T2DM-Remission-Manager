"""
模块名称：date_utils.py
所属层级：通用工具层（utils）
功能说明：临床日期计算——日历月加法（月末钳位）与最早可判定日期。

为什么必须钳位到目标月最后一天：临床上的"满 3 个月/满 6 个月"按日历月理解。
若起算日是某月 31 日而目标月只有 30 天，直接顺延会人为推迟判定日期，
钳位到目标月末更符合"满整月"的临床直觉（`_SPEC/06` Q001 裁决）。

主要函数：
    - add_months_clamped()：日历月加法（月末钳位）。
    - compute_earliest_judge_date()：按时间锚点计算最早可判定日期（F040）。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现（自 V0.1 继承算法，补充锚点组合计算）
"""

from __future__ import annotations

import calendar
from datetime import date

# 时间锚点的月数（锁定稿§8 与 `_SPEC/06` Q001）
DRUG_FREE_MONTHS = 3
LIFESTYLE_MONTHS = 6
SURGERY_MONTHS = 3


def add_months_clamped(d: date, months: int) -> date:
    """按日历月加法计算 d 之后 months 个月的日期，钳位到目标月最后一天。

    示例：8 月 31 日 + 3 个日历月 = 11 月 30 日（而不是 12 月 1 日）。

    参数:
        d (date): 起算日期。
        months (int): 增加的日历月数（本项目只使用非负值）。

    返回:
        date: 钳位后的目标日期。
    """
    # 换算为"绝对月序号"后一次加减，避免逐月进位误差
    total_month_index = d.year * 12 + (d.month - 1) + months
    target_year, target_month_zero = divmod(total_month_index, 12)
    target_month = target_month_zero + 1
    # monthrange 自动处理闰年二月
    last_day = calendar.monthrange(target_year, target_month)[1]
    return date(target_year, target_month, min(d.day, last_day))


def compute_earliest_judge_date(
    *,
    last_med_stop_date: date | None,
    lifestyle_start_date: date | None = None,
    surgery_date: date | None = None,
) -> date | None:
    """计算最早可判定日期（F040）。

    规则：F040 = MAX(停药日期+3 个日历月；生活方式干预开始+6 个日历月〔如适用〕；
    代谢手术日期+3 个日历月〔如适用〕)；不适用的锚点不参与 MAX。

    参数:
        last_med_stop_date (date | None): 最后一种降糖作用药物的停用日期（必需锚点）。
        lifestyle_start_date (date | None): 结构化生活方式干预开始日期（如适用）。
        surgery_date (date | None): 代谢手术日期（如适用）。

    返回:
        date | None: 最早可判定日期；停药日期缺失时返回 None（无法开始计时）。
    """
    if last_med_stop_date is None:
        # 没有停药日期就没有观察期起点，系统不得凭空给日期
        return None
    candidates = [add_months_clamped(last_med_stop_date, DRUG_FREE_MONTHS)]
    if lifestyle_start_date is not None:
        candidates.append(add_months_clamped(lifestyle_start_date, LIFESTYLE_MONTHS))
    if surgery_date is not None:
        candidates.append(add_months_clamped(surgery_date, SURGERY_MONTHS))
    # 取最晚者：所有干预等待条件都满足才可判定
    return max(candidates)
