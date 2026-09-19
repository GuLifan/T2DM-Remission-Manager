"""
模块名称：logging.py
所属层级：基础能力层（core）
功能说明：配置结构化日志。

设计要点：
    - 统一格式，便于开发者用脚本筛查（时间、级别、模块、消息）。
    - 前端不展示日志；错误细节只进日志，前台只看到自然语言说明。
    - 不记录患者完整病历内容（隐私要求见 `_SPEC/07` 第十三节）。

主要函数：
    - configure_logging()：初始化日志（幂等，可重复调用）。

修改历史：
    - 2026-09-20  v1.0  M1 初始实现
"""

from __future__ import annotations

import logging
import sys

# 日志格式：时间 | 级别 | 模块 | 消息
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _LevelFilter(logging.Filter):
    """按级别过滤的控制台过滤器（避免重复输出同一条日志）。"""

    def __init__(self, max_level: int) -> None:
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """只放行不高于 max_level 的记录。"""
        return record.levelno <= self.max_level


def configure_logging(level: str = "INFO") -> None:
    """配置根日志器。

    参数:
        level (str): 日志级别名称（DEBUG/INFO/WARNING/ERROR）。
    """
    root = logging.getLogger()
    # 幂等：重复调用时先清空已有处理器，避免日志重复打印
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(level.upper())

    # 统一输出到标准输出，交由启动器或控制台收集
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(_LevelFilter(logging.WARNING))
    root.addHandler(handler)
