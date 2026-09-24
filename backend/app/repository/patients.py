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

from app.domain.transitions import validate_transition
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
    department: str = "内分泌科",
    contact_phone: str | None = None,
    created_by: int | None = None,
    profile_complete: bool = True,
    is_test_patient: bool = False,
) -> Patient:
    """建立患者档案（新患者一律从 ST00 开始）。"""
    patient = Patient(
        name=name,
        gender=gender,
        birth_date=birth_date,
        medical_record_no=medical_record_no,
        department=department,
        contact_phone=contact_phone,
        created_by=created_by,
        profile_complete=profile_complete,
        is_test_patient=is_test_patient,
        current_state=INITIAL_STATE,
    )
    db.add(patient)
    db.flush()
    return patient


def update_profile(
    db: Session,
    patient: Patient,
    *,
    name: str,
    gender: str,
    birth_date,
    medical_record_no: str,
    department: str,
    contact_phone: str | None,
) -> None:
    """更新患者基本资料并解除“待完善”门禁。"""
    patient.name = name
    patient.gender = gender
    patient.birth_date = birth_date
    patient.medical_record_no = medical_record_no
    patient.department = department
    patient.contact_phone = contact_phone
    patient.profile_complete = True
    db.flush()


def get_patient(db: Session, patient_id: int) -> Patient | None:
    """按主键查询患者。"""
    return db.get(Patient, patient_id)


def find_by_medical_record_no(db: Session, medical_record_no: str) -> Patient | None:
    """按病历号查询（用于建档前的唯一性预检，给出友好的中文提示）。"""
    return db.scalar(select(Patient).where(Patient.medical_record_no == medical_record_no))


def list_patients(db: Session, limit: int = 200) -> list[Patient]:
    """按建档时间倒序列出患者（数量上限防止意外全表返回）。"""
    return list(db.scalars(select(Patient).order_by(Patient.created_at.desc()).limit(limit)).all())


def apply_outcome(
    db: Session,
    patient: Patient,
    *,
    target_state: str,
    updates: dict[str, object] | None = None,
) -> None:
    """把一次决策的结果落到患者档案上。

    为什么集中在这里：
        1. 状态跳转必须再经状态机校验（服务层已校验过一次，这里是第二道防线，
           防止将来有人绕过服务层直接改状态）；
        2. 阶段、目标、复评日期、时间锚点等字段的更新统一走本函数，
           避免各接口各写一套而产生字段漂移（V0.1 的 F053 状态漂移就是这类问题）。

    参数:
        db (Session): 数据库会话（不在此提交，由接口层统一提交）。
        patient (Patient): 目标患者。
        target_state (str): 本次决策后的状态代码。
        updates (dict | None): 需要一并更新的字段（如 stage、next_review_date、
            last_med_stop_date、earliest_judge_date、has_glucose_lowering_drug 等）。
            **显式传入 None 表示把该字段清空**，这与会话细节一致。
    """
    validate_transition(patient.current_state, target_state)
    patient.current_state = target_state
    for field_name, value in (updates or {}).items():
        # 只允许更新 Patient 上真实存在的字段，避免拼错字段名被静默忽略
        if not hasattr(patient, field_name):
            raise AttributeError(f"Patient 不存在字段：{field_name}")
        setattr(patient, field_name, value)
    db.flush()
