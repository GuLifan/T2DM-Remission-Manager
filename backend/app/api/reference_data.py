"""
模块名称：reference_data.py
所属层级：接口层（api）
功能说明：公开输出注册与临床表单所需参考字典，防止前端复制并漂移。

安全说明：本接口只返回非敏感的固定参考选项，不读取账号或患者数据，因此登录前注册页可访问。

修改历史：
    - 2026-09-24  v1.0  第二轮第二批新增
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.domain.enums import DIAGNOSIS_BASES, GLUCOSE_LOWERING_DRUG_CLASSES
from app.repository import departments as departments_repo
from app.repository.database import get_db

router = APIRouter(prefix="/reference", tags=["参考字典"])


@router.get("")
def reference_data(db: Session = Depends(get_db)) -> dict[str, list[str]]:
    """返回科室、诊断基础与降糖药物类别。"""
    return {
        "departments": [item.name for item in departments_repo.list_active(db)],
        "diagnosis_bases": list(DIAGNOSIS_BASES),
        "drug_classes": list(GLUCOSE_LOWERING_DRUG_CLASSES),
    }
