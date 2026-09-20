"""
模块名称：test_api_flow.py
所属层级：测试（tests）
功能说明：临床流程接口的端到端测试（M4 过门依据）。

覆盖内容：
    1. 领域导出接口返回锁定定义（状态、流程单元、分支优先级顺序）；
    2. 完整链路：建档 → 重新发起预评估 → 预评估 → 完整评估 → 复评 → 停药 →
       观察期 → 到期进入判定 → 核对 → 确认缓解 → 缓解后复评；
    3. 入口守卫：快速建档仅限急性安全暂缓、关闭路径仅限分型存疑暂缓、
       确认缓解前必须有客观核对事件(IMP-3/4/5)；
    4. **对照实验**：check 接口是只读的（不产生事件），route 才落库（修正 V0.1 的 L5 问题）；
    5. 幂等：同一 request_id 不产生重复事件；
    6. 鉴权：未登录访问流程接口一律 401。

修改历史：
    - 2026-09-20  v1.0  M4 初始实现
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.domain import enums
from app.models.audit import AuditLog
from app.models.event import Event
from app.models.patient import Patient

# 测试用建档数据（非真实患者）
PATIENT = {
    "name": "接口测试患者",
    "gender": "女",
    "birth_date": "1980-01-01",
    "medical_record_no": "MRN-M4-0001",
}


def _create_patient(client, doctor, mrn: str = "MRN-M4-0001") -> int:
    """建档并返回患者主键（默认处于 ST00 常规管理）。"""
    payload = {**PATIENT, "medical_record_no": mrn}
    response = client.post("/api/patients", json=payload, headers=doctor["headers"])
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _reopen(client, doctor, patient_id: int) -> None:
    """从常规管理重新发起预评估（ST00 → ST10）。"""
    response = client.post(f"/api/patients/{patient_id}/reopen", headers=doctor["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["current_state"] == "ST10"


def _pre_enter(client, doctor, patient_id: int) -> dict:
    """提交"进入完整评估"的预评估。"""
    payload = {
        "f001_t2dm_established": enums.YES,
        "f002_acute_unsafe": enums.NO,
        "f003_type_doubt": enums.NO,
        "f004_treatment_context_sufficient": enums.YES,
        "f005_refused": enums.NO,
    }
    response = client.post(f"/api/patients/{patient_id}/pre-assessment", json=payload, headers=doctor["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _start_stable(client, doctor, patient_id: int) -> None:
    """完整评估：启动血糖稳定阶段。"""
    payload = {
        "f026_start": enums.START,
        "f027_stage": enums.STAGE_STABLE,
        "f028_stage_goal": "安全改善明显高血糖",
        "f029_interventions": ["结构化生活方式"],
    }
    response = client.post(f"/api/patients/{patient_id}/full-assessment", json=payload, headers=doctor["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["target_state"] == "ST31"


def _patient_state(db_session, patient_id: int) -> str:
    """直接读取患者当前状态（用于断言落库结果）。

    注意：接口层用的是**另一个数据库会话**，且本测试会话可能已缓存过该患者对象，
    因此必须 expire 之后再读，否则会拿到过期快照（这正是本测试第一版失败的原因）。
    """
    db_session.expire_all()
    return db_session.get(Patient, patient_id).current_state


# ===================== 领域导出接口 =====================


def test_domain_endpoints_export_locked_definitions(client, doctor) -> None:
    """领域接口必须返回锁定定义，且分支顺序即优先级。"""
    states = client.get("/api/domain/states", headers=doctor["headers"])
    assert states.status_code == 200
    assert len(states.json()) == 9
    # 前台名称不得包含状态代码
    assert all(item["code"] not in item["name"] for item in states.json())

    units = client.get("/api/domain/flow-units", headers=doctor["headers"])
    assert units.status_code == 200
    assert [item["index"] for item in units.json()] == [1, 2, 3, 4, 5, 6]

    branches = client.get("/api/domain/branches", headers=doctor["headers"])
    assert branches.status_code == 200
    assert [item["key"] for item in branches.json()] == [
        "uncontrolled",
        "on_treatment_non_diabetic",
        "stop_last_med",
        "routine_action",
    ]


def test_flow_endpoints_require_authentication(client) -> None:
    """未登录访问流程接口一律 401。"""
    for path in ("/api/domain/states", "/api/patients/1/observation", "/api/patients/1/events"):
        assert client.get(path).status_code == 401


# ===================== 完整链路 =====================


def test_full_flow_from_regular_care_to_post_remission(client, doctor, db_session) -> None:
    """从常规管理一路走到缓解后复评（M4 主链路）。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-FLOW")
    assert _patient_state(db_session, patient_id) == "ST00"

    _reopen(client, doctor, patient_id)
    result = _pre_enter(client, doctor, patient_id)
    assert result["conclusion"] == "进入完整评估"
    assert _patient_state(db_session, patient_id) == "ST20"

    _start_stable(client, doctor, patient_id)
    assert _patient_state(db_session, patient_id) == "ST31"

    # 停药：系统自动进入观察期（不经过任何"进入观察期"操作）
    # 停药日期取"今天前 10 天"：这样最早可判定日期（+3 个日历月）落在未来，才能验证"未到期不得判定"
    recent_stop_date = date.today() - timedelta(days=10)
    stop = client.post(
        f"/api/patients/{patient_id}/phase-review",
        json={
            "f034_action": enums.ACT_CONTINUE,
            "f035_stop_last_med": True,
            "f036_stop_date": recent_stop_date.isoformat(),
        },
        headers=doctor["headers"],
    )
    assert stop.status_code == 200, stop.text
    assert stop.json()["target_state"] == "ST40"
    # 最早可判定日期必须晚于今天（观察期尚未到期）
    assert date.fromisoformat(stop.json()["earliest_judge_date"]) > date.today()
    assert _patient_state(db_session, patient_id) == "ST40"

    # 未到期时不得进入判定
    too_early = client.post(f"/api/patients/{patient_id}/observation/enter-judge", headers=doctor["headers"])
    assert too_early.status_code == 422
    assert "最早可判定日期" in too_early.json()["detail"]

    # 模拟时间流逝：直接把停药日期与最早判定日期改到过去（服务层时间由 Clock 注入，这里只改数据）
    patient = db_session.get(Patient, patient_id)
    patient.last_med_stop_date = date.today() - timedelta(days=200)
    patient.earliest_judge_date = date.today() - timedelta(days=100)
    db_session.commit()

    observation = client.get(f"/api/patients/{patient_id}/observation", headers=doctor["headers"])
    assert observation.status_code == 200
    assert observation.json()["due"] is True

    enter = client.post(f"/api/patients/{patient_id}/observation/enter-judge", headers=doctor["headers"])
    assert enter.status_code == 200, enter.text
    assert _patient_state(db_session, patient_id) == "ST50"

    # 核对：客观条件满足（只读接口，不落库）
    judge_payload = {
        "f041_diagnosis_credible": enums.YES,
        "f042_drug_free_3m": enums.YES,
        "f043_hba1c_reliable": enums.YES,
        "f014_hba1c": 6.1,
    }
    check = client.post(
        f"/api/patients/{patient_id}/remission-judge/check", json=judge_payload, headers=doctor["headers"]
    )
    assert check.status_code == 200, check.text
    assert check.json()["objective_met"] is True
    assert check.json()["doctor_confirmation_required"] is True
    # 关键：核对不改变状态（系统绝不自动确认缓解）
    assert _patient_state(db_session, patient_id) == "ST50"

    # 检查接口是只读的：调用前后事件数不变
    before = len(db_session.scalars(select(Event).where(Event.patient_id == patient_id)).all())
    client.post(f"/api/patients/{patient_id}/remission-judge/check", json=judge_payload, headers=doctor["headers"])
    after = len(db_session.scalars(select(Event).where(Event.patient_id == patient_id)).all())
    assert before == after, "check 接口不应写入事件"

    # 落库（route）→ 生成 E4-B03 客观满足事件
    routed = client.post(
        f"/api/patients/{patient_id}/remission-judge/route", json=judge_payload, headers=doctor["headers"]
    )
    assert routed.status_code == 200, routed.text
    assert routed.json()["rule_id"] == "E4-B03"
    assert _patient_state(db_session, patient_id) == "ST50"

    # 医生确认缓解 → 进入缓解后复评
    confirm = client.post(
        f"/api/patients/{patient_id}/remission-judge/confirm",
        json={"f048_confirm": "确认"},
        headers=doctor["headers"],
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["target_state"] == "ST60"
    assert _patient_state(db_session, patient_id) == "ST60"

    # 缓解后复评：维持
    post = client.post(
        f"/api/patients/{patient_id}/post-remission-review",
        json={"f050_med_status": enums.MED_UNUSED, "f055_glucose_state": enums.GLUCOSE_BELOW_THRESHOLD},
        headers=doctor["headers"],
    )
    assert post.status_code == 200, post.text
    assert post.json()["rule_id"] == "E5-B01"


def test_case3_benefit_drug_path_over_http(client, doctor) -> None:
    """病例3 走 HTTP：治疗下达标仍用获益药 → 不进入观察期、不建议停药。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-CASE3")
    _reopen(client, doctor, patient_id)
    _pre_enter(client, doctor, patient_id)
    _start_stable(client, doctor, patient_id)

    response = client.post(
        f"/api/patients/{patient_id}/phase-review",
        json={
            "f034_action": enums.ACT_CONTINUE,
            "f053_has_drug": True,
            "f054_purpose": enums.PURPOSE_ORGAN,
            "glucose_non_diabetic": True,
        },
        headers=doctor["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule_id"] == "E3-B06"
    assert body["entered_observation"] is False
    assert body["target_state"] == "ST31"
    assert "不建议为获得缓解标签而停药" in body["output_text"]


# ===================== 入口守卫 =====================


def test_acute_stabilized_requires_acute_hold_first(client, doctor, db_session) -> None:
    """快速建档仅限"最近一次是急性安全暂缓"（IMP-4），并验证 ST10→ST31 合法。

    这也是对 V0.1 潜在缺陷的回归：V0.1 的状态矩阵里缺少 ST10→ST31，
    其"快速建档"接口一旦被调用就会被自己的状态机拦住。
    """
    patient_id = _create_patient(client, doctor, "MRN-M4-ACUTE")
    _reopen(client, doctor, patient_id)

    # 未暂缓就快速建档 → 拒绝
    denied = client.post(
        f"/api/patients/{patient_id}/pre-assessment/acute-stabilized",
        json={"stage_goal": "安全降糖", "interventions": ["结构化生活方式"]},
        headers=doctor["headers"],
    )
    assert denied.status_code == 422
    assert "急性安全暂缓" in denied.json()["detail"]

    # 先产生急性安全暂缓事件
    hold = client.post(
        f"/api/patients/{patient_id}/pre-assessment",
        json={
            "f001_t2dm_established": enums.YES,
            "f002_acute_unsafe": enums.YES,
            "f003_type_doubt": enums.NO,
            "f004_treatment_context_sufficient": enums.YES,
            "f005_refused": enums.NO,
            "f012_pre_tasks": "先处理急性问题",
        },
        headers=doctor["headers"],
    )
    assert hold.status_code == 200
    assert hold.json()["rule_id"] == "E1-B02"

    # 再做快速建档 → 允许，且直接进入血糖稳定阶段
    ok = client.post(
        f"/api/patients/{patient_id}/pre-assessment/acute-stabilized",
        json={"stage_goal": "安全降糖", "interventions": ["结构化生活方式"]},
        headers=doctor["headers"],
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["target_state"] == "ST31"
    assert _patient_state(db_session, patient_id) == "ST31"


def test_close_path_requires_type_doubt_first(client, doctor, db_session) -> None:
    """关闭路径仅限"最近一次是分型存疑暂缓"（IMP-5）。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-CLOSE")
    _reopen(client, doctor, patient_id)

    denied = client.post(f"/api/patients/{patient_id}/pre-assessment/close-path", headers=doctor["headers"])
    assert denied.status_code == 422

    client.post(
        f"/api/patients/{patient_id}/pre-assessment",
        json={
            "f001_t2dm_established": enums.YES,
            "f002_acute_unsafe": enums.NO,
            "f003_type_doubt": enums.YES,
            "f004_treatment_context_sufficient": enums.YES,
            "f005_refused": enums.NO,
            "f012_pre_tasks": "复查C肽与抗体",
        },
        headers=doctor["headers"],
    )
    closed = client.post(f"/api/patients/{patient_id}/pre-assessment/close-path", headers=doctor["headers"])
    assert closed.status_code == 200, closed.text
    assert closed.json()["target_state"] == "ST99"
    assert _patient_state(db_session, patient_id) == "ST99"


def test_wrong_state_is_rejected(client, doctor) -> None:
    """在常规管理状态下直接提交完整评估 → 拒绝（状态守卫）。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-WRONGSTATE")
    response = client.post(
        f"/api/patients/{patient_id}/full-assessment",
        json={
            "f026_start": enums.START,
            "f027_stage": enums.STAGE_STABLE,
            "f028_stage_goal": "目标",
            "f029_interventions": ["结构化生活方式"],
        },
        headers=doctor["headers"],
    )
    assert response.status_code == 422
    assert "完整评估" in response.json()["detail"]


def test_confirm_requires_objective_check_first(client, doctor, db_session) -> None:
    """未经客观核对直接确认缓解 → 拒绝（IMP-3 守卫）。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-GUARD")
    _reopen(client, doctor, patient_id)
    _pre_enter(client, doctor, patient_id)
    _start_stable(client, doctor, patient_id)

    # 直接停药→观察期→判定，跳过核对
    client.post(
        f"/api/patients/{patient_id}/phase-review",
        json={"f034_action": enums.ACT_CONTINUE, "f035_stop_last_med": True, "f036_stop_date": "2026-01-31"},
        headers=doctor["headers"],
    )
    patient = db_session.get(Patient, patient_id)
    patient.last_med_stop_date = date.today() - timedelta(days=200)
    patient.earliest_judge_date = date.today() - timedelta(days=100)
    db_session.commit()
    client.post(f"/api/patients/{patient_id}/observation/enter-judge", headers=doctor["headers"])

    denied = client.post(
        f"/api/patients/{patient_id}/remission-judge/confirm",
        json={"f048_confirm": "确认"},
        headers=doctor["headers"],
    )
    assert denied.status_code == 422
    assert "客观条件核对" in denied.json()["detail"]


# ===================== 幂等与审计 =====================


def test_duplicate_request_id_is_rejected(client, doctor, db_session) -> None:
    """同一 request_id 重复提交不得产生第二条事件。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-IDEMPOTENT")
    _reopen(client, doctor, patient_id)
    # 用"暂缓"路径（自环，仍停在预评估）来验证幂等：第二次提交会命中幂等守卫
    payload = {
        "request_id": "req-idem-001",
        "f001_t2dm_established": enums.YES,
        "f002_acute_unsafe": enums.YES,
        "f003_type_doubt": enums.NO,
        "f004_treatment_context_sufficient": enums.YES,
        "f005_refused": enums.NO,
        "f012_pre_tasks": "先处理急性问题",
    }
    first = client.post(f"/api/patients/{patient_id}/pre-assessment", json=payload, headers=doctor["headers"])
    assert first.status_code == 200
    assert first.json()["target_state"] == "ST10"

    # 重复提交同一 request_id（模拟网络重试/双击）
    second = client.post(f"/api/patients/{patient_id}/pre-assessment", json=payload, headers=doctor["headers"])
    assert second.status_code == 409
    assert "已经提交过" in second.json()["detail"]


def test_event_and_audit_are_written_together(client, doctor, db_session) -> None:
    """每次决策都要同时留下事件与审计（同事务）。"""
    patient_id = _create_patient(client, doctor, "MRN-M4-AUDIT")
    _reopen(client, doctor, patient_id)
    _pre_enter(client, doctor, patient_id)

    events = db_session.scalars(select(Event).where(Event.patient_id == patient_id)).all()
    # 事件链：REOPEN → E1-B01
    assert [event.rule_id for event in events] == ["REOPEN", "E1-B01"]
    # 事件必须记录操作者与迁移两端
    assert all(event.operator_id is not None for event in events)
    assert events[-1].source_state == "ST10"
    assert events[-1].target_state == "ST20"

    audits = db_session.scalars(select(AuditLog).where(AuditLog.action == "event_write")).all()
    assert audits, "决策未写入审计日志"


@pytest.mark.parametrize(
    "stage", [enums.STAGE_STABLE, enums.STAGE_INDUCTION]
)
def test_judgement_requires_doctor_chosen_stage_when_returning(
    client, doctor, db_session, stage: str
) -> None:
    """「仍在使用降糖药」时：未选阶段不落库，选了阶段才返回事件3。"""
    patient_id = _create_patient(client, doctor, f"MRN-M4-STAGE-{stage}")
    _reopen(client, doctor, patient_id)
    _pre_enter(client, doctor, patient_id)
    _start_stable(client, doctor, patient_id)
    stopped = client.post(
        f"/api/patients/{patient_id}/phase-review",
        json={
            "f034_action": enums.ACT_CONTINUE,
            "f035_stop_last_med": True,
            "f036_stop_date": date.today().isoformat(),
        },
        headers=doctor["headers"],
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["target_state"] == "ST40"
    patient = db_session.get(Patient, patient_id)
    patient.last_med_stop_date = date.today() - timedelta(days=200)
    patient.earliest_judge_date = date.today() - timedelta(days=100)
    patient.has_glucose_lowering_drug = True  # 仍在使用降糖作用药物
    db_session.commit()
    entered = client.post(f"/api/patients/{patient_id}/observation/enter-judge", headers=doctor["headers"])
    assert entered.status_code == 200, entered.text
    assert _patient_state(db_session, patient_id) == "ST50"

    base_payload = {
        "f041_diagnosis_credible": enums.YES,
        "f042_drug_free_3m": enums.NO,
        "f043_hba1c_reliable": enums.YES,
    }
    # 未选择返回阶段：返回提示但不落库
    hint = client.post(
        f"/api/patients/{patient_id}/remission-judge/route", json=base_payload, headers=doctor["headers"]
    )
    assert hint.status_code == 200
    assert hint.json()["needs_target_stage"] is True
    assert _patient_state(db_session, patient_id) == "ST50"

    # 选择返回阶段：落库并回到阶段复评
    routed = client.post(
        f"/api/patients/{patient_id}/remission-judge/route",
        json={**base_payload, "target_stage": stage},
        headers=doctor["headers"],
    )
    assert routed.status_code == 200, routed.text
    expected_state = "ST31" if stage == enums.STAGE_STABLE else "ST32"
    assert _patient_state(db_session, patient_id) == expected_state
