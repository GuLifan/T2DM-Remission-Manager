"""
包名称：services
所属层级：临床服务层（★最严格）
功能说明：6 个流程单元的临床决策逻辑。

铁律（`_SPEC/07` 第一节）：
    1. 服务层是**纯函数**：不读系统时间（today 由调用方注入）、不写数据库；
    2. 不直接访问 HTTP 上下文；
    3. 返回结果前必须通过 `domain.transitions.validate_transition()` 校验状态跳转；
    4. 临床结论一律由医生确认，系统只做核对、计算与阻断。

模块划分：
    - defaults：临床默认值（唯一来源，禁止散落硬编码）。
    - pre_assessment / full_assessment / phase_review：事件1–3。
    - observation：系统自动状态（缓解观察期）。
    - remission_judge / post_remission：事件4–5。
"""
