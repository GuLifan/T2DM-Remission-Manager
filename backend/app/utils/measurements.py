"""
模块名称：measurements.py
所属层级：工具层（utils）
功能说明：计算 BMI 数值快照；不输出分级、不参与临床准入或状态转换。

修改历史：
    - 2026-09-24  v1.0  第二轮第二批新增
"""

from __future__ import annotations


def calculate_bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    """按 kg / m² 计算一位小数 BMI；任一值缺失时不计算。"""
    if height_cm is None or weight_kg is None:
        return None
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("身高和体重必须大于 0。")
    return round(weight_kg / ((height_cm / 100) ** 2), 1)
