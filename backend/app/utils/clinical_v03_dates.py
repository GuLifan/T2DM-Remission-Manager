"""v0.3适用性与日期守卫；纯函数，不读取系统时间、不写患者数据。"""
from __future__ import annotations

from datetime import date

from app.core.exceptions import BusinessRuleError
from app.models.clinical_v03 import ExaminationRecord, ObservationAnchors
from app.utils.date_utils import add_months_clamped


def compute_earliest(
    stop: date | None, anchors: ObservationAnchors | None, *, today: date,
) -> tuple[date | None, list[str]]:
    """全部适用锚点齐全才取MAX；未知与不适用分开，未来事实拒绝。"""
    tasks: list[str] = []
    if stop is None:
        tasks.append("核对实际全部停药日期")
    if anchors is None:
        tasks.append("核对适用干预类型")
    candidates = []
    if stop:
        require_nonfuture(stop, today, "实际停药日期")
        candidates.append(add_months_clamped(stop, 3))
    if anchors:
        for kind, value, months, label in [
            ("结构化生活方式", anchors.f038_lifestyle_start_date, 6, "生活方式开始日期"),
            ("代谢手术", anchors.f039_surgery_date, 3, "代谢手术日期"),
        ]:
            # 连非适用日期也不接受未来的“已发生”记录，但不参与MAX。
            if value:
                require_nonfuture(value, today, label)
            if kind not in anchors.f063_applicable_interventions:
                continue
            if value is None:
                tasks.append(f"补齐适用的{label}")
            else:
                candidates.append(add_months_clamped(value, months))
    return (None if tasks else max(candidates)), tasks


def require_nonfuture(value: date, today: date, label: str) -> None:
    if value > today:
        raise BusinessRuleError(f"{label}不能晚于本次记录日。", code="FUTURE_CLINICAL_DATE")


def examination_date_qualified(exam: ExaminationRecord, earliest: date | None, today: date) -> bool:
    """不新增有效期窗口；检测日/CGM结束日需落在闭区间[F040,today]。"""
    return earliest is not None and exam.effective_date is not None and earliest <= exam.effective_date <= today
