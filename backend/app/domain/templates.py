"""
模块名称：templates.py
所属层级：领域层（domain）
功能说明：自然语言输出模板（锁定文案）。

**模板正文逐字取自 `_DEV/甲方材料/md派生/临床流程实现表_输出模板.md`，不得改写。**
任何改动必须走变更控制（先改 `_SPEC/04`，再改本文件，并同步测试）。
计数口径：30 个 `OUT-*` + 2 个 `SYS-*`（共 32 条），见 `_SPEC/06` V1.0-Q-01。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现（30 条锁定文案逐字录入 + 2 条 SYS 兜底提示）
"""

from __future__ import annotations

# ===== 事件1：60秒预评估（5 条）=====
TEMPLATES: dict[str, str] = {
    "OUT-E1-ENTER": (
        "当前可进入完整缓解评估。下一步将综合评估血糖与治疗、体重状态、管理约束及实施条件，"
        "并由医生确认是否启动主动管理。"
    ),
    "OUT-E1-HOLD-ACUTE": (
        "当前暂缓进入缓解管理路径。原因：存在需优先处理的急性安全问题。请先完成：{pre_tasks}。"
        "处理完成后返回本次预评估结论处；若已完成稳定化治疗，可由医生直接进入血糖稳定阶段。"
    ),
    "OUT-E1-HOLD-TYPE": (
        "当前暂缓进入缓解管理路径。原因：糖尿病分型尚需复核。请完成：{pre_tasks}。"
        "如明确仍为T2DM，直接进入完整评估；如明确为其他类型，关闭本路径。"
    ),
    "OUT-E1-HOLD-DATA": (
        "当前暂缓进入缓解管理路径。原因：关键治疗背景不足。请补充：{pre_tasks}。"
        "资料补齐后返回本次预评估结论处。"
    ),
    "OUT-E1-NOSTART": (
        "当前不启动缓解管理路径。继续常规糖尿病综合管理；"
        "后续患者意愿或临床条件改变时，可重新发起60秒预评估。"
    ),
    # ===== 事件2：完整评估并形成主动管理计划（4 条）=====
    "OUT-E2-STABLE": (
        "建议启动结构化主动管理。当前阶段：血糖稳定阶段。主要目标：{stage_goal}。"
        "干预组合：{interventions}。下一次正式复评：{next_review_date}。"
    ),
    "OUT-E2-INDUCTION": (
        "建议启动结构化主动管理。当前阶段：缓解诱导阶段。主要目标：{stage_goal}。"
        "干预组合：{interventions}。下一次正式复评：{next_review_date}。"
    ),
    "OUT-E2-HOLD": (
        "当前暂缓形成主动管理计划。请补充：{pre_tasks}。"
        "资料补齐后返回本次完整评估结论处，不重复预评估或完整录入。"
    ),
    "OUT-E2-NOSTART": (
        "当前不启动结构化主动缓解管理。继续常规糖尿病综合管理；"
        "后续实施条件或患者意愿改变时可重新发起。"
    ),
    # ===== 事件3：阶段复评与治疗调整（6 条）=====
    "OUT-E3-CONTINUE": "继续当前阶段。维持主要目标和当前方案，下一次正式复评：{next_review_date}。",
    "OUT-E3-ADJUST": (
        "建议调整当前方案或阶段目标，仍处于“{current_stage}”。调整内容：{adjustment_summary}。"
        "下一次正式复评：{next_review_date}。"
    ),
    "OUT-E3-SWITCH": (
        "管理阶段已由“{old_stage}”转换为“{new_stage}”。新的主要阶段目标：{stage_goal}。"
        "下一次正式复评：{next_review_date}。"
    ),
    "OUT-E3-END": "本次主动缓解管理已结束，返回常规糖尿病综合管理。以后临床条件或患者意愿改变时可重新发起。",
    "OUT-E3-ON-TREATMENT": (
        "治疗下血糖已达非糖尿病范围，暂不能判定缓解。"
        "当前药物具有心肾或体重获益，不建议为获得缓解标签而停药。"
    ),
    "OUT-E3-OBS-ENTER": (
        "已记录最后一种具有降糖作用药物停用日期：{last_med_stop_date}。"
        "系统已自动进入缓解观察期，并将计算最早可判定日期。"
    ),
    # ===== 观察期（4 条）=====
    "OUT-A1-WAIT": "目前处于缓解观察期，最早可于{earliest_assessment_date}进行正式判定。",
    "OUT-A1-DUE": "已到达最早可判定日期，请录入或核对判定指标，进入正式缓解判定。",
    "OUT-A1-RESTART-HIGH": "观察期已终止：因血糖升高重新用药或需要强化治疗。请返回阶段复评并调整方案。",
    "OUT-A1-RESTART-BENEFIT": (
        "当前因使用具有降糖作用的器官或体重获益药物，暂不能判定无药缓解；"
        "保留既往观察记录，不等同于缓解失败或复发。"
    ),
    # ===== 事件4：缓解判定（6 条）=====
    "OUT-E4-NOT-DUE": "目前处于缓解观察期，最早可于{earliest_assessment_date}进行正式判定。",
    "OUT-E4-ON-DRUG": "当前血糖已改善，但仍在使用具有降糖作用的药物，暂不能确认无药物缓解。",
    "OUT-E4-OBJECTIVE-MET": "当前客观资料符合T2DM缓解标准，请由医生确认。",
    "OUT-E4-CONFIRMED": "医生已确认“2型糖尿病缓解”。请进入缓解后复评并生成随访提醒。",
    "OUT-E4-NOT-MET": "当前未达到T2DM缓解标准，继续主动管理或调整方案。",
    "OUT-E4-UNCERTAIN": "当前资料不足以可靠确认或排除缓解，请完成：{pre_tasks}。",
    # ===== 事件5：缓解后复评（5 条）=====
    "OUT-E5-MAINTAIN": "缓解维持。请继续现有体重和生活方式管理，并按计划复查。",
    "OUT-E5-RISK": (
        "目前仍维持缓解，但复发风险上升。建议加强体重和生活方式维持干预，"
        "并由医生决定是否提前复查。"
    ),
    "OUT-E5-UNEVALUABLE": (
        "当前缓解状态不可评价：因重新使用具有降糖作用的器官或体重获益药物。"
        "保留既往缓解历史，不等同于复发。"
    ),
    "OUT-E5-END": "缓解状态已终止。请直接返回主动管理并重新设定当前阶段和治疗目标。",
    "OUT-E5-FOLLOWUP": (
        "默认随访提醒：第1年每3～6个月；第2年每6个月；满2年后每年。"
        "医生可根据异常结果或临床事件提前调整。"
    ),
    # ===== SYS 级兜底提示（非锁定临床模板，仅用于未定义出口的安全兜底）=====
    "SYS-E5-REVIEW": "当前血糖状态暂不能可靠解释，请完成定向复核后再行评价；系统保留缓解状态记录。",
    "SYS-E1-CLOSE": "分型复核明确为其他类型糖尿病，已关闭T2DM缓解管理路径。",
}

# 锁定临床模板（30 条）与 SYS 兜底提示（2 条）的分类，供自查脚本与测试使用
CLINICAL_TEMPLATE_IDS: tuple[str, ...] = tuple(sorted(k for k in TEMPLATES if k.startswith("OUT-")))
SYS_TEMPLATE_IDS: tuple[str, ...] = tuple(sorted(k for k in TEMPLATES if k.startswith("SYS-")))


def render(template_id: str, **variables: str) -> str:
    """按模板 ID 渲染自然语言文本。

    为什么集中渲染：模板正文是锁定文字，渲染逻辑只能有一处，避免各服务自行拼接造成漂移。

    参数:
        template_id (str): 模板 ID（如 OUT-E3-CONTINUE）。
        **variables: 模板变量的取值（如 next_review_date="2026-12-20"）。

    返回:
        str: 渲染后的自然语言文本。

    异常:
        KeyError: 模板 ID 不存在（属工程缺陷，应被测试拦截）。
    """
    template = TEMPLATES[template_id]
    # 变量缺失时保留占位符原样，便于开发者一眼看出漏传（不做静默清空）
    if not variables:
        return template
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    return result
