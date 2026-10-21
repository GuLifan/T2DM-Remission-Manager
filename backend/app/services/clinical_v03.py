"""v0.3纯函数临床服务：原子转移与补充转移，医生决定与系统动作分离。

不查询数据库、不读系统时间。所有日期由today注入；客观条件符合不是缓解结论。
接口层仍须执行鉴权、患者归属、版本/幂等及同次确认快照守卫。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.core.exceptions import BusinessRuleError
from app.domain.clinical_v03 import TRANSITIONS_BY_ID, require_transition
from app.domain.templates import render
from app.models.clinical_v03 import (
    FullAssessmentV03,
    MedicationRestartV03,
    ObservationAnchors,
    PhaseReviewV03,
    PostRemissionV03,
    PreAssessmentV03,
    PreRecoveryV03,
    RemissionJudgeV03,
    SupplementalDecisionV03,
)
from app.services.defaults import default_next_review_date, next_followup_date
from app.utils.clinical_v03_dates import compute_earliest, examination_date_qualified, require_nonfuture


@dataclass(frozen=True)
class Context:
    """患者事实只读快照；空值保留未知，不推断已停药或已适用。"""

    state: str
    stage: str | None = None
    stage_goal: str | None = None
    stop_date: date | None = None
    anchors: ObservationAnchors | None = None
    observation_status: str = "none"
    observation_cycle: int = 0
    actual_stop_confirmed: bool | None = None
    has_drug: bool | None = None
    confirmed_date: date | None = None


@dataclass
class Decision:
    """有序转移列表允许E3并行提示；最终仅一个目标，更新与事件同事务。"""

    transition_ids: list[str]
    target_state: str
    rule_id: str
    template_id: str | None
    output_text: str
    updates: dict[str, object] = field(default_factory=dict)
    tasks: list[str] = field(default_factory=list)
    objective_met: bool = False


def fail(message: str) -> None:
    raise BusinessRuleError(message, code="V03_REQUIRED_FACT")


def decision(ctx: Context, ids: list[str], text: str, *, template: str | None = None,
             updates: dict[str, object] | None = None, tasks: list[str] | None = None,
             objective_met: bool = False) -> Decision:
    """逐条校验有序源/目标，不以一个宽泛的可达状态集合替代原子表。"""
    cursor = ctx.state
    for key in ids:
        item = TRANSITIONS_BY_ID[key]
        require_transition(key, cursor, item.target)
        cursor = item.target
    return Decision(ids, cursor, TRANSITIONS_BY_ID[ids[-1]].rule_id, template, text,
                    updates or {}, tasks or [], objective_met)


def target_for_stage(stage: str | None) -> str:
    if stage not in ("血糖稳定", "缓解诱导"):
        fail("请由医生明确选择返回的管理阶段。")
    return "ST31" if stage == "血糖稳定" else "ST32"


def require_text(value: str | None, label: str) -> str:
    if not value or not value.strip():
        fail(f"请填写{label}。")
    return value.strip()


def review_date(chosen: date | None, today: date) -> date:
    if chosen and chosen <= today:
        fail("下一次复评日期必须晚于本次记录日。")
    return chosen or default_next_review_date(today)


def evaluate_pre(ctx: Context, payload: PreAssessmentV03) -> Decision:
    if payload.f061_conclusion == "当前不启动":
        return decision(ctx, ["T09"], render("OUT-E1-NOSTART"), template="OUT-E1-NOSTART")
    if payload.f061_conclusion == "暂缓进入":
        task = require_text(payload.f012_pre_tasks, "前置任务与返回位置")
        if not payload.f011_hold_reasons:
            fail("请明确所有暂缓原因。")
        mapping = {"急性安全": ("T02", "OUT-E1-HOLD-ACUTE"), "分型存疑": ("T03", "OUT-E1-HOLD-TYPE"), "关键资料不足": ("T04", "OUT-E1-HOLD-DATA")}
        keys = [mapping[k] for k in mapping if k in payload.f011_hold_reasons]
        return decision(ctx, [k[0] for k in keys], "\n".join(render(k[1], pre_tasks=task) for k in keys), template=keys[0][1], tasks=[task])
    facts = (payload.f001_t2dm_established, payload.f002_acute_unsafe, payload.f003_type_doubt,
             payload.f004_treatment_context_sufficient, payload.f005_refused)
    if facts != ("是", "否", "否", "是", "否"):
        fail("入口事实与进入完整评估的选择不一致，请医生核对。")
    return decision(ctx, ["T01"], render("OUT-E1-ENTER"), template="OUT-E1-ENTER")


def require_constraints(values: list[str]) -> None:
    """与当前页面可选项等价；未知文本不是一次有效核对。旧记录读取不受影响。"""
    allowed = {"无", "CKD", "ASCVD或心衰", "严重视网膜病变", "低血糖", "衰弱", "相关用药"}
    if not values or any(item not in allowed for item in values):
        fail("请核对管理约束；没有时明确选择无，其他项从有效选项中选择。")


def evaluate_full(ctx: Context, payload: FullAssessmentV03, today: date) -> Decision:
    if payload.f026_start == "暂缓补充关键资料":
        task = require_text(payload.f012_pre_tasks, "需补充的关键资料")
        return decision(ctx, ["T12"], render("OUT-E2-HOLD", pre_tasks=task), template="OUT-E2-HOLD", tasks=[task])
    if payload.f026_start == "当前不启动":
        return decision(ctx, ["T13"], render("OUT-E2-NOSTART"), template="OUT-E2-NOSTART")
    if payload.input_schema_version == "v0.4":
        require_constraints(payload.f023_constraints)
    require_text(payload.f013_diagnosis_basis, "诊断依据")
    exam = payload.recent_examination
    valid_exam = exam is not None and exam.reliability == "可靠" and exam.effective_date is not None
    if payload.input_schema_version == "v0.4":
        valid_exam = valid_exam or any(e.reliability == "可靠" and e.effective_date for e in payload.examinations)
        # 引用检查由接口在服务执行前解析到examinations，所有日期仍逐项校验。
        for e in payload.examinations:
            for d in (e.test_date, e.report_start_date, e.report_end_date):
                if d:
                    require_nonfuture(d, today, "近期检查日期")
    valid_summary = bool(payload.f015_recent_glucose and payload.f015_test_date and payload.recent_glucose_reliable == "是")
    if not valid_exam and not valid_summary:
        fail("请提供可靠近期HbA1c或血糖摘要，并记录检测日期。")
    if valid_exam and exam:
        require_nonfuture(exam.effective_date, today, "近期检查日期")
    elif valid_summary:
        require_nonfuture(payload.f015_test_date, today, "近期血糖检测日期")
    if not payload.f016_medications and not payload.f016_no_medication_confirmed and not (payload.input_schema_version == "v0.4" and payload.medication_review_complete and payload.current_medication_confirmation == "否"):
        fail("请核对当前药物记录，或明确当前未使用药物。")
    if payload.f024_willing != "是" or payload.f025_review_accept != "是":
        fail("请核对实施条件与医生启动决定。")
    target = target_for_stage(payload.f027_stage)
    goal = require_text(payload.f028_stage_goal, "一个主要阶段目标")
    if not payload.f029_interventions:
        fail("请填写干预组合。")
    next_date = review_date(payload.next_review_date, today)
    template = "OUT-E2-STABLE" if target == "ST31" else "OUT-E2-INDUCTION"
    return decision(ctx, ["T10" if target == "ST31" else "T11"], render(template, stage_goal=goal, interventions="、".join(payload.f029_interventions), next_review_date=next_date.isoformat()), template=template, updates={"stage": payload.f027_stage, "stage_goal": goal, "interventions": "、".join(payload.f029_interventions), "next_review_date": next_date})


def evaluate_recovery(ctx: Context, payload: PreRecoveryV03, today: date, pending: list[str]) -> Decision:
    if not payload.doctor_confirmed:
        fail("前置问题处理结果必须由医生明确确认。")
    typing = payload.result.startswith("分型")
    required = "分型存疑" if typing else "急性安全"
    if required not in pending:
        fail("当前没有相应的暂缓任务，请先核对预评估记录。")
    if payload.result == "分型明确其他类型":
        return decision(ctx, ["T06"], "医生复核明确为其他类型，关闭本T2DM缓解路径。")
    remaining = [item for item in pending if item != required]
    if payload.result == "急性已处理返回结论":
        return decision(ctx, ["T07"], "安全问题已处理，请确认下一步。", tasks=remaining)
    if remaining:
        fail("仍有其他暂缓问题未解决，请先返回预评估核对，不可直接进入后续管理。")
    if typing:
        return decision(ctx, ["T05"], "已明确为T2DM，进入完整评估。")
    if payload.input_schema_version == "v0.4":
        require_constraints(payload.f023_constraints)
    goal = require_text(payload.stage_goal, "初始血糖稳定目标")
    if not payload.interventions:
        fail("请填写初始管理干预组合。")
    next_date = review_date(payload.next_review_date, today)
    return decision(ctx, ["T08"], render("OUT-E2-STABLE", stage_goal=goal,
                    interventions="、".join(payload.interventions), next_review_date=next_date.isoformat()),
                    template="OUT-E2-STABLE", updates={"stage": "血糖稳定", "stage_goal": goal,
                    "interventions": "、".join(payload.interventions), "next_review_date": next_date})


def evaluate_phase(ctx: Context, payload: PhaseReviewV03, today: date) -> Decision:
    suffix = "A" if ctx.state == "ST31" else "B"
    updates: dict[str, object] = {"has_glucose_lowering_drug": payload.f053_has_drug, "drug_purpose": payload.f054_purpose}
    if payload.f053_has_drug is True and payload.f054_purpose is None:
        fail("请核对降糖作用药物的主要用途。")
    if payload.f035_stop_last_med and payload.f057_actual_stop == "已实际停用":
        if payload.f056_uncontrolled:
            fail("明显失控与实际全部停药同时记录，请医生核对本次处理决定。")
        if payload.anchors is None:
            fail("请明确适用干预类型，不能将未知记为不适用。")
        earliest, tasks = compute_earliest(payload.f036_stop_date, payload.anchors, today=today)
        updates.update({"stage": None, "next_review_date": None, "last_med_stop_date": payload.f036_stop_date,
                        "earliest_judge_date": earliest, "actual_stop_confirmed": True,
                        "observation_status": "active", "observation_cycle": ctx.observation_cycle + 1,
                        "applicable_interventions": payload.anchors.f063_applicable_interventions,
                        "lifestyle_start_date": payload.anchors.f038_lifestyle_start_date,
                        "surgery_date": payload.anchors.f039_surgery_date, "drug_purpose": None})
        text = render("OUT-E3-OBS-ENTER", last_med_stop_date=payload.f036_stop_date.isoformat())
        if tasks:
            text += "\n请完成：" + "；".join(tasks) + "。"
        return decision(ctx, [f"T18{suffix}", "T23" if tasks else "T22"], text, template="OUT-E3-OBS-ENTER", updates=updates, tasks=tasks)
    next_date = review_date(payload.next_review_date, today)
    updates["next_review_date"] = next_date
    if payload.f056_uncontrolled:
        updates["stage"] = "血糖稳定"
        return decision(ctx, [f"T19{suffix}"], render("OUT-E3-ADJUST", current_stage="血糖稳定", adjustment_summary=payload.adjustment_summary or "医生确认明显血糖失控", next_review_date=next_date.isoformat()), template="OUT-E3-ADJUST", updates=updates)
    annotations = [f"T17{suffix}"] if payload.f060_non_diabetic_on_treatment == "是" and payload.f053_has_drug is True and payload.f054_purpose in ("器官获益", "体重获益") else []
    note = render("OUT-E3-ON-TREATMENT") + "\n" if annotations else ""
    action = payload.f034_action
    if action == "转换阶段":
        target = target_for_stage(payload.f062_target_stage)
        if target == ctx.state:
            fail("新阶段与当前阶段相同，请核对复评动作。")
        goal = require_text(payload.stage_goal, "新阶段主要目标")
        updates.update({"stage": payload.f062_target_stage, "stage_goal": goal})
        template, key = "OUT-E3-SWITCH", "T20" if ctx.state == "ST31" else "T21"
        text = render(template, old_stage=ctx.stage, new_stage=payload.f062_target_stage, stage_goal=goal, next_review_date=next_date.isoformat())
    elif action == "结束主动管理":
        require_text(payload.end_reason, "结束原因")
        updates.update({"stage": None, "stage_goal": None, "interventions": None, "next_review_date": None})
        template, key, text = "OUT-E3-END", f"T16{suffix}", render("OUT-E3-END")
    elif action == "调整方案或目标":
        summary = require_text(payload.adjustment_summary, "调整内容")
        template, key = "OUT-E3-ADJUST", f"T15{suffix}"
        if payload.stage_goal:
            updates["stage_goal"] = payload.stage_goal
        text = render(template, current_stage=ctx.stage, adjustment_summary=summary, next_review_date=next_date.isoformat())
    else:
        template, key = "OUT-E3-CONTINUE", f"T14{suffix}"
        text = render(template, next_review_date=next_date.isoformat())
    if payload.f035_stop_last_med:
        text += "\n停药尚未实际完成或待核对：保留阶段复评，不启动无药观察计时。"
    return decision(ctx, [*annotations, key], note + text, template=template, updates=updates)


def evaluate_observation(ctx: Context, today: date) -> Decision:
    earliest, tasks = compute_earliest(ctx.stop_date, ctx.anchors, today=today)
    if ctx.observation_status != "active" or ctx.actual_stop_confirmed is not True or ctx.has_drug is not False:
        # 暂停本身已由T27记录，刷新不是一次新的临床转移；不能冒用T23。
        return Decision([], ctx.state, "A1-B05" if ctx.observation_status == "suspended_benefit" else "A1-B02", None,
                        "当前无药观察已暂停或尚待核对，不能推断到期。", tasks=["核对有效观察与当前无药事实"])
    if tasks:
        return decision(ctx, ["T23"], "请完成：" + "；".join(tasks) + "。", updates={"earliest_judge_date": None}, tasks=tasks)
    if today >= earliest:
        return decision(ctx, ["T24"], render("OUT-A1-DUE"), template="OUT-A1-DUE", updates={"earliest_judge_date": earliest})
    return decision(ctx, ["T22", "T23"], render("OUT-A1-WAIT", earliest_assessment_date=earliest.isoformat()), template="OUT-A1-WAIT", updates={"earliest_judge_date": earliest})


def evaluate_restart(ctx: Context, payload: MedicationRestartV03) -> Decision:
    high = payload.f037_reason == "因高血糖"
    target = target_for_stage(payload.f062_target_stage) if high or payload.f062_target_stage else "ST40"
    key = ("T25" if target == "ST31" else "T26") if high else ("T27" if target == "ST40" else "T28" if target == "ST31" else "T29")
    template = "OUT-A1-RESTART-HIGH" if high else "OUT-A1-RESTART-BENEFIT"
    return decision(ctx, [key], render(template), template=template, updates={"has_glucose_lowering_drug": True, "drug_purpose": payload.f037_reason.removeprefix("因"), "stage": payload.f062_target_stage, "observation_status": "ended_restart" if high else "suspended_benefit", "earliest_judge_date": None, "actual_stop_confirmed": False, "current_remission_evaluation": "暂不能判定"})


def evaluate_judge(ctx: Context, payload: RemissionJudgeV03, today: date) -> Decision:
    anchors = payload.anchors or ctx.anchors
    earliest, tasks = compute_earliest(ctx.stop_date, anchors, today=today)
    if earliest and today < earliest:
        return decision(ctx, ["T30"], render("OUT-E4-NOT-DUE", earliest_assessment_date=earliest.isoformat()), template="OUT-E4-NOT-DUE")
    if payload.f053_has_drug is True:
        target = target_for_stage(payload.f062_target_stage)
        return decision(ctx, ["T32" if target == "ST31" else "T33"], render("OUT-E4-ON-DRUG"), template="OUT-E4-ON-DRUG", updates={"stage": payload.f062_target_stage, "has_glucose_lowering_drug": True, "observation_status": "ended_restart", "earliest_judge_date": None})
    for missing, task in [
        (payload.f041_diagnosis_credible != "是", "复核既往诊断"),
        (payload.f053_has_drug is not False, "核对当前药物状态"),
        (payload.f042_drug_free_3m != "是" or ctx.actual_stop_confirmed is not True, "核对实际全部停药"),
        (ctx.observation_status != "active", "核对本轮有效无药观察"),
        (payload.f059_completeness != "完整", "补齐本次判定资料"),
    ]:
        if missing:
            tasks.append(task)
    exam = payload.f058_examination
    if any(m.status in ("使用中", "待核对") and m.has_glucose_lowering_effect is not False
           for m in payload.f016_medications):
        tasks.append("药物记录与无降糖作用药物的结论不一致，请复核")
    if exam is None or not examination_date_qualified(exam, earliest, today):
        tasks.append("补齐日期在最早判定日至本次判定日内的检查")
    if exam is None or exam.reliability != "可靠":
        tasks.append("核对本次检查可靠性")
    if payload.f043_hba1c_reliable == "是":
        if exam is None or exam.kind != "HbA1c":
            tasks.append("HbA1c可靠时请使用HbA1c")
    elif payload.f043_hba1c_reliable == "否":
        if exam is None or exam.kind not in ("FPG", "CGM估算HbA1c") or not exam.independently_reviewed:
            tasks.append("复核替代指标及其独立核对")
    else:
        tasks.append("复核HbA1c可解释性")
    if tasks:
        tasks = list(dict.fromkeys(tasks))
        return decision(ctx, ["T31"], render("OUT-E4-UNCERTAIN", pre_tasks="；".join(tasks)), template="OUT-E4-UNCERTAIN", tasks=tasks)
    if exam.value >= (7.0 if exam.kind == "FPG" else 6.5):
        target = target_for_stage(payload.f062_target_stage)
        return decision(ctx, ["T37" if target == "ST31" else "T38"], render("OUT-E4-NOT-MET"), template="OUT-E4-NOT-MET", updates={"stage": payload.f062_target_stage, "observation_status": "ended_not_met"})
    updates = {"has_glucose_lowering_drug": False, "earliest_judge_date": earliest,
               "applicable_interventions": anchors.f063_applicable_interventions,
               "lifestyle_start_date": anchors.f038_lifestyle_start_date, "surgery_date": anchors.f039_surgery_date}
    return decision(ctx, ["T34"], render("OUT-E4-OBJECTIVE-MET"), template="OUT-E4-OBJECTIVE-MET", updates=updates, objective_met=True)


def evaluate_post(ctx: Context, payload: PostRemissionV03, today: date) -> Decision:
    if payload.f049_test_date:
        require_nonfuture(payload.f049_test_date, today, "检测日期")
    valid_result = bool(payload.f049_glucose and payload.f049_test_date and payload.f049_test_date <= today and payload.f055_glucose_state != "暂不能可靠解释")
    high = payload.f050_med_status == "因高血糖"
    if high or payload.f055_glucose_state == "达到糖尿病范围":
        if not high and not valid_result:
            fail("缺少本次可靠血糖及日期，不能确认缓解终止。")
        target = target_for_stage(payload.f062_target_stage)
        return decision(ctx, ["T42" if target == "ST31" else "T43"], render("OUT-E5-END"), template="OUT-E5-END", updates={"stage": payload.f062_target_stage, "current_remission_evaluation": "终止", "has_glucose_lowering_drug": high})
    if payload.f050_med_status in ("因器官获益", "因体重获益"):
        return decision(ctx, ["T41"], render("OUT-E5-UNEVALUABLE"), template="OUT-E5-UNEVALUABLE", updates={"current_remission_evaluation": "不可评价", "has_glucose_lowering_drug": True, "drug_purpose": payload.f050_med_status.removeprefix("因")})
    if not valid_result or payload.f050_med_status == "待核对":
        task = require_text(payload.f012_pre_tasks, "定向复核任务")
        return decision(ctx, ["T45"], render("SYS-E5-REVIEW") + "\n" + task, template="SYS-E5-REVIEW", updates={"current_remission_evaluation": "待复核"}, tasks=[task])
    next_date = payload.next_review_date or next_followup_date(ctx.confirmed_date or today, today)
    if next_date <= today:
        fail("下次复查日期必须晚于本次复评日。")
    template = "OUT-E5-RISK" if payload.risk_increase_confirmed else "OUT-E5-MAINTAIN"
    return decision(ctx, ["T40" if payload.risk_increase_confirmed else "T39"], render(template), template=template, updates={"current_remission_evaluation": "维持，风险上升" if payload.risk_increase_confirmed else "维持", "has_glucose_lowering_drug": False, "drug_purpose": None, "next_review_date": next_date})


def evaluate_supplement(ctx: Context, payload: SupplementalDecisionV03) -> Decision:
    if not payload.doctor_confirmed:
        fail("本次返回操作必须由医生明确确认。")
    key = payload.transition_id
    if key == "P04" and not payload.remission_termination_confirmed:
        fail("返回完整评估前须由医生明确确认缓解终止及新证据/重大变化。")
    updates: dict[str, object] = {}
    if key in ("P05A", "P05B"):
        if payload.f050_med_status not in ("因器官获益", "因体重获益"):
            fail("请核对器官或体重获益的重新用药原因。")
        updates.update({"current_remission_evaluation": "不可评价", "stage": "血糖稳定" if key == "P05A" else "缓解诱导",
                        "has_glucose_lowering_drug": any(m.status == "使用中" and m.has_glucose_lowering_effect is True for m in payload.f016_medications)})
        updates["drug_purpose"] = payload.f050_med_status.removeprefix("因")
    elif key == "P04":
        updates["current_remission_evaluation"] = "终止"
    else:
        updates["stage"] = None
    return decision(ctx, [key], "医生已确认本次返回决定。原因：" + payload.reason + "。关联资料：" + payload.evidence_summary, updates=updates)
