"""
模块名称：enums.py
所属层级：领域层（domain）
功能说明：字段允许值常量（与 `_DEV` 最小字段映射 F001–F056 的枚举一致）。

为什么要集中：枚举值一旦散落在服务层与界面里，就会出现"前端能选、后端不认"的漂移。
所有取值只在本文件定义，服务层与接口层统一引用。

修改历史：
    - 2026-09-20  v1.0  M3 初始实现（自 V0.1 继承取值，未增删改）
"""

from __future__ import annotations

# ===== 通用是否取值 =====
YES = "是"
NO = "否"
PENDING = "待确认"
PENDING_REVIEW = "待复核"
PENDING_CHECK = "待核对"

# ===== 事件1：暂缓原因（F011）=====
HOLD_ACUTE = "急性安全"
HOLD_TYPE = "分型存疑"
HOLD_DATA = "关键治疗背景不足"

# ===== 事件2：是否启动主动管理（F026）=====
START = "启动"
HOLD_SUPPLEMENT = "暂缓补充关键资料"
NOT_START = "当前不启动"

# ===== 管理阶段（F027）=====
STAGE_STABLE = "血糖稳定"
STAGE_INDUCTION = "缓解诱导"
STAGES: tuple[str, ...] = (STAGE_STABLE, STAGE_INDUCTION)

# ===== 事件3：复评动作（F034）=====
ACT_CONTINUE = "继续当前阶段"
ACT_ADJUST = "调整方案或目标"
ACT_SWITCH = "转换阶段"
ACT_END = "结束主动管理"

# ===== 药物主要使用目的（F054）=====
PURPOSE_GLYCEMIC = "高血糖治疗"
PURPOSE_ORGAN = "器官获益"
PURPOSE_WEIGHT = "体重获益"
PURPOSE_OTHER = "其他"
BENEFIT_PURPOSES: tuple[str, ...] = (PURPOSE_ORGAN, PURPOSE_WEIGHT)

# ===== 重新用药原因（F037）=====
RESTART_HYPERGLYCEMIA = "因高血糖"
RESTART_ORGAN = "因器官获益"
RESTART_WEIGHT = "因体重获益"
RESTART_OTHER = "其他"

# ===== 缓解后复评：用药状态（F050）=====
MED_UNUSED = "未使用"
MED_FOR_HYPERGLYCEMIA = "因高血糖"
MED_FOR_ORGAN = "因器官获益"
MED_FOR_WEIGHT = "因体重获益"

# ===== 缓解后复评：血糖状态（F055）=====
GLUCOSE_BELOW_THRESHOLD = "低于糖尿病诊断阈值"
GLUCOSE_DIABETIC_RANGE = "达到糖尿病范围"
GLUCOSE_UNEXPLAINED = "暂不能可靠解释"

# ===== 事件1 五问的选项集 =====
OPT_YES_NO: tuple[str, ...] = (YES, NO)
OPT_YES_NO_PENDING: tuple[str, ...] = (YES, NO, PENDING)
OPT_YES_NO_PENDING_REVIEW: tuple[str, ...] = (YES, NO, PENDING_REVIEW)

# ===== 其他界面用选项集（与最小字段映射一致）=====
OPT_INSULIN: tuple[str, ...] = ("未用", "短期强化", "长期使用", "其他")
OPT_DEMANDS: tuple[str, ...] = ("减重", "减药", "了解缓解", "无明确诉求")
OPT_INTERVENTIONS: tuple[str, ...] = ("结构化生活方式", "降糖治疗调整", "体重管理药物", "代谢手术评估")
OPT_SAFETY_ISSUES: tuple[str, ...] = ("无", "低血糖", "明显高血糖", "药物不良反应", "营养风险", "急性疾病")
OPT_TREATMENT_CHANGES: tuple[str, ...] = ("无", "新增", "减量", "停用", "无法继续")
OPT_CONSTRAINTS: tuple[str, ...] = ("CKD", "ASCVD或心衰", "严重视网膜病变", "低血糖", "衰弱", "相关用药")
OPT_RISK_TRIGGERS: tuple[str, ...] = ("体重反弹", "急性疾病", "糖皮质激素", "妊娠", "手术", "明显生活方式改变")
OPT_DRUG_PURPOSE: tuple[str, ...] = (PURPOSE_GLYCEMIC, PURPOSE_ORGAN, PURPOSE_WEIGHT, PURPOSE_OTHER)
