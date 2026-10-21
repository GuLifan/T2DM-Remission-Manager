import { expect, it } from 'vitest'
import { confirmationSummary } from './confirmationSummary'

it.each([
  ['phase-review',{f034_action:'继续当前阶段',f057_actual_stop:'仅计划停用',planned_stop_date:'2026-11-01'},['仅计划停用','计划停药日：2026-11-01']],
  ['pre-recovery',{result:'分型明确其他类型'},['复核结果：分型明确其他类型']],
  ['remission-confirm',{f048_confirm:'暂不确认',f012_pre_tasks:'独立复核检查'},['医生缓解决定：暂不确认','独立复核检查']],
  ['remission-confirm',{f048_confirm:'确认'},['医生缓解决定：确认']],
  ['supplemental-decision',{transition_id:'P05B',f050_med_status:'因体重获益'},['获益用药，进入缓解诱导','因体重获益']],
] as const)('摘要明确实际决定 %s',(action,payload,expected)=>{
  const text=confirmationSummary(action,payload)
  for(const part of expected)expect(text).toContain(part)
  if(action!=='phase-review')expect(text).not.toContain('继续当前阶段')
})
