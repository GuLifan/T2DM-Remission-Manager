/** 从冻结的提交载荷生成摘要；不读取可能已变化的页面默认值。 */
export function confirmationSummary(action: string, p: Record<string, unknown>): string {
  const text = (value: unknown): string => Array.isArray(value) ? value.map(text).join('、') : value == null ? '' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)
  const lines: string[] = []
  const add = (label: string, value: unknown) => {if (value !== undefined && value !== null && value !== '' && !(Array.isArray(value) && value.length === 0)) lines.push(`${label}：${text(value)}`)}
  const actions: Record<string, string> = {'pre-assessment':'预评估', 'pre-recovery':'前置问题复核', 'full-assessment':'完整评估', 'phase-review':'阶段复评', 'observation-anchors':'观察日期核对', 'medication-restart':'重新用药', 'remission-judge':'仅核对客观条件，尚未确认缓解', 'remission-confirm':'缓解决定', 'post-remission':'缓解后复评', 'supplemental-decision':'重大变化返回处理'}
  add('本次操作', actions[action] ?? action)
  const fields: [string,string][] = [['f061_conclusion','医生结论'],['f001_t2dm_established','成人T2DM'],['f002_acute_unsafe','急性不安全'],['f003_type_doubt','分型疑点'],['f004_treatment_context_sufficient','治疗背景充分'],['f005_refused','患者拒绝'],['f011_hold_reasons','暂缓原因'],['result','复核结果'],['evidence_summary','依据'],['f026_start','医生决定'],['f027_stage','管理阶段'],['f023_constraints','管理约束'],['f029_interventions','干预计划'],['intervention_other','其他干预说明'],['f034_action','复评动作'],['f057_actual_stop','停药执行状态'],['planned_stop_date','计划停药日'],['f036_stop_date','实际停药日'],['f037_reason','重新用药原因'],['f048_confirm','医生缓解决定'],['f050_med_status','用药原因/状态'],['f055_glucose_state','血糖判定'],['f049_glucose','血糖摘要'],['f049_test_date','检测日期'],['f051_risk_triggers','风险线索'],['risk_increase_confirmed','确认风险上升'],['f062_target_stage','后续阶段'],['f028_stage_goal','主要目标'],['stage_goal','阶段目标'],['adjustment_summary','调整内容'],['end_reason','结束原因'],['f012_pre_tasks','任务/原因'],['next_review_date','下次复评'],['reason','返回原因']]
  for (const [key,label] of fields) add(label,p[key])
  if (p.transition_id) add('返回方向', ({P01:'重新预评估',P02:'返回完整评估',P03A:'返回完整评估',P03B:'返回完整评估',P04:'确认缓解终止，返回完整评估',P05A:'获益用药，进入血糖稳定',P05B:'获益用药，进入缓解诱导'} as Record<string,string>)[String(p.transition_id)])
  add('新增体重（kg）',p.f018_weight)
  if (Array.isArray(p.removed_medication_ids) && p.removed_medication_ids.length) add('从本次方案移除（历史保留，不代表实际停药）', `${p.removed_medication_ids.length}项`)
  if (p.no_current_medications_confirmed) add('本次明确确认', '当前无药，停药事实另行核对')
  if (p.measurement_id) add('沿用测量记录',p.measurement_id)
  if (Array.isArray(p.f016_medications)) add('当前药物',p.f016_medications.length ? p.f016_medications.map(m => `${m.name}（${m.status}；${m.dose}）`).join('；') : p.medication_review_complete ? '已完整核对无药' : '尚待核对')
  if (p.anchors && typeof p.anchors === 'object') {
    const a = p.anchors as Record<string,unknown>
    add('适用干预',a.f063_applicable_interventions); add('生活方式开始日',a.f038_lifestyle_start_date); add('手术日期',a.f039_surgery_date)
  }
  return lines.join('\n')
}
