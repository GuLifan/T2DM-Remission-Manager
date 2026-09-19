## 模板说明（mako 注释：不会写入生成文件）：
## 生成每个迁移脚本的头注释与标准结构。
## 注意：模板里不要写模块级文档字符串，否则会被插入生成文件开头，
##       导致 `from __future__` 不在文件最前而报 SyntaxError。

"""${message}

迁移编号：${up_revision}
修订内容：${message}
生成时间：${create_date}
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# 迁移标识
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """升级到本版本结构。"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """回退到上一版本结构。"""
    ${downgrades if downgrades else "pass"}
