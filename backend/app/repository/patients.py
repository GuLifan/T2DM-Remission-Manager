"""
模块名称：patients.py
所属层级：数据访问层（repository）
功能说明：患者档案的数据访问。建档即进入"常规糖尿病综合管理"（ST00）。

事务约定：只 add/flush，不 commit（由接口层统一提交）。

修改历史：
    - 2026-09-20  v1.0  M2 初始实现
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient

# 初始状态：常规糖尿病综合管理
INITIAL_STATE = "ST00"


def create_patient(
    db: Session,
    *,
    name: str,
    gender: str,
    birth_date,
    medical_record_no: str,
) -> Patient:
    """建立患者档案（新患者一律从 ST00 开始）。"""
    patient = Patient(
        name=name,
        gender=gender,
        birth_date=birth_date,
        medical_record_no=medical_record_no,
        current_state=INITIAL_STATE,
    )
    db.add(patient)
    db.flush()
    return patient


def get_patient(db: Session, patient_id: int) -> Patient | None:
    """按主键查询患者。"""
    return db.get(Patient, patient_id)


def find_by_medical_record_no(db: Session, medical_record_no: str) -> Patient | None:
    """按病历号查询（用于建档前的唯一性预检，给出友好的中文提示）。"""
    return db.scalar(select(Patient).where(Patient.medical_record_no == medical_record_no))


def list_patients(db: Session, limit: int = 200) -> list[Patient]:
    """按建档时间倒序列出患者（数量上限防止意外全表返回）。"""
    return list(db.scalars(select(Patient).order_by(Patient.created_at.desc()).limit(limit)).all())
