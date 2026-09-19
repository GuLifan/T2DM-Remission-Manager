"""
模块名称：test_date_utils.py
所属层级：测试（tests）
功能说明：日期计算的边界测试。

覆盖内容：
    1. 日历月加法的月末钳位（8月31日+3月=11月30日）；
    2. 闰年二月边界；
    3. 最早可判定日期的 MAX 规则与空缺锚点处理。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现
"""

from __future__ import annotations

from datetime import date

from app.utils.date_utils import add_months_clamped, compute_earliest_judge_date


def test_add_months_clamps_to_target_month_end() -> None:
    """月末钳位：8月31日 + 3 个日历月 = 11月30日（裁决 Q001）。"""
    assert add_months_clamped(date(2026, 8, 31), 3) == date(2026, 11, 30)


def test_add_months_keeps_normal_day() -> None:
    """常规日期直接平移，不做多余调整。"""
    assert add_months_clamped(date(2026, 3, 15), 3) == date(2026, 6, 15)


def test_add_months_handles_year_rollover() -> None:
    """跨年计算正确。"""
    assert add_months_clamped(date(2026, 11, 30), 3) == date(2027, 2, 28)


def test_add_months_handles_leap_year() -> None:
    """闰年二月：1月31日 + 1 月 = 2月29日。"""
    assert add_months_clamped(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_earliest_judge_uses_max_of_anchors() -> None:
    """最早可判定日期取各锚点的最晚者。"""
    earliest = compute_earliest_judge_date(
        last_med_stop_date=date(2026, 1, 10),   # +3 月 = 4月10日
        lifestyle_start_date=date(2026, 1, 5),  # +6 月 = 7月5日（更晚）
    )
    assert earliest == date(2026, 7, 5)


def test_earliest_judge_ignores_missing_anchors() -> None:
    """不适用的锚点不参与 MAX。"""
    earliest = compute_earliest_judge_date(
        last_med_stop_date=date(2026, 1, 10),
        lifestyle_start_date=None,
        surgery_date=None,
    )
    assert earliest == date(2026, 4, 10)


def test_earliest_judge_returns_none_without_stop_date() -> None:
    """没有停药日期就没有观察期起点，系统不得凭空给日期。"""
    assert compute_earliest_judge_date(last_med_stop_date=None) is None
