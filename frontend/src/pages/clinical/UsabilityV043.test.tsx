import { useState } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import DateControl from '../../components/DateControl'
import type { Patient } from '../../types'
import ClinicalPage from './ClinicalPage'
import ExaminationEditor from './ExaminationEditor'
import type { ClinicalContext, Medication } from './types'

const p = (state='ST10'): Patient => ({id:303,name:'独立交互病例',gender:'女',birth_date:'1980-01-01',medical_record_no:'QA',department:'内分泌科',contact_phone:null,created_by:1,owner_id:1,owner_display_name:'医生',can_edit:true,profile_complete:true,is_test_patient:true,height_cm:170,weight_kg:80,bmi:27.7,current_state:state,stage:'血糖稳定',stage_goal:'核对',interventions:null,next_review_date:null,last_med_stop_date:'2026-07-01',lifestyle_start_date:null,surgery_date:null,earliest_judge_date:'2026-10-01',remission_confirmed_date:null,has_glucose_lowering_drug:false,drug_purpose:null,clinical_contract_version:'v0.3',clinical_revision:4,observation_status:'active',observation_cycle:1,applicable_interventions:['其他'],actual_stop_confirmed:true,current_remission_evaluation:null,objective_assessment_event_id:null,created_at:'2026-01-01',updated_at:'2026-01-01'})
const data = (): ClinicalContext => ({patient_revision:4,measurement:{id:10,kind:'measurement',clinical_date:'2026-10-21',source_event_id:1,supersedes_id:null,created_at:'2026-10-21',data:{weight_kg:80,height_cm:170,bmi:27.7,measured_on:'2026-10-21'}},measurements:[],weight_reduction_percent:null,regimen:null,duration:null,examinations:[],carried:{}})
const json = (value:unknown) => new Response(JSON.stringify(value),{status:200})
function setup(context=data(), result: Record<string,unknown>={tasks:[],output_text:'保存成功'}, onSubmit=()=>{}) {
  const fetcher=vi.fn((input:RequestInfo|URL, init?:RequestInit) => {
    const url=String(input)
    if(url.endsWith('/context')) return Promise.resolve(json(context))
    if(url.endsWith('/test-context')) return Promise.resolve(json({effective_date:'2026-10-21'}))
    if(url.endsWith('/reference')) return Promise.resolve(json({medication_catalog:{categories:[]}}))
    if(init?.method==='POST') {onSubmit();return Promise.resolve(json({patient_revision:5,objective_met:false,transition_ids:['T31'],assessment_event_id:10,...result}))}
    return Promise.resolve(json({}))
  })
  vi.stubGlobal('fetch',fetcher)
  return fetcher
}
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

it('底部提交漏填时居中提示，定位字段且保留草稿，无临床请求',async()=>{
  const fetcher=setup(),user=userEvent.setup()
  render(<ClinicalPage patient={p()} onUpdated={vi.fn()} />)
  await screen.findByText('沿用体重 80 kg')
  await user.type(screen.getByLabelText('病程月'),'18')
  await user.click(screen.getByRole('button',{name:'保存预评估结论'}))
  const dialog=await screen.findByRole('dialog',{name:'请补全或核对本次资料'})
  expect(dialog).toHaveTextContent('治疗背景充分')
  await user.click(within(dialog).getByRole('button',{name:'定位需要核对的位置'}))
  await waitFor(()=>expect(within(screen.getByRole('group',{name:'治疗背景充分'})).getByLabelText('是')).toHaveFocus())
  expect(screen.getByLabelText('病程月')).toHaveValue(18)
  expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(false)
})

it('移除继承药物撤销核对，全部移除须显式确认，提交声明移除ID且原草稿不变',async()=>{
  const c=data(),med:Medication={medication_id:'saved-drug',name:'继承药物',dose:'待核对',started_on:null,stopped_on:null,status:'使用中',has_glucose_lowering_effect:true,purposes:['降糖治疗']}
  c.regimen={id:20,kind:'medication_regimen',clinical_date:'2026-10-20',source_event_id:1,supersedes_id:null,created_at:'2026-10-20',data:{medications:[med],complete:true}}
  const fetcher=setup(c),user=userEvent.setup()
  render(<ClinicalPage patient={{...p('ST31'),has_glucose_lowering_drug:true}} onUpdated={vi.fn()} />)
  await user.click(await screen.findByText('继承药物',{exact:true}))
  await user.click(screen.getByRole('button',{name:'从本次方案移除'}))
  expect(screen.getByLabelText('已完整核对当前方案，包括在用、停用和是否遗漏')).not.toBeChecked()
  await user.click(screen.getByRole('button',{name:'保存本次复评'}))
  const error=await screen.findByRole('dialog',{name:'请补全或核对本次资料'})
  expect(error).toHaveTextContent('全部移除须明确确认')
  expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(false)
  await user.keyboard('{Escape}')
  await user.click(screen.getByLabelText('本次已核对当前无药（不代表已确认实际停药日期）'))
  await user.click(screen.getByLabelText('已完整核对当前方案，包括在用、停用和是否遗漏'))
  await user.click(screen.getByRole('button',{name:'保存本次复评'}))
  const dialog=await screen.findByRole('dialog',{name:'保存本次复评'})
  expect(dialog).toHaveTextContent('历史保留，不代表实际停药')
  await user.click(within(dialog).getByRole('button',{name:'保存本次复评'}))
  await waitFor(()=>expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(true))
  const call=fetcher.mock.calls.find(([,init])=>init?.method==='POST')!
  const body=JSON.parse(String(call[1]?.body))
  expect(body).toMatchObject({removed_medication_ids:['saved-drug'],no_current_medications_confirmed:true,medication_review_complete:true,f016_medications:[],f035_stop_last_med:false})
  expect(body.f036_stop_date).toBeNull()
  expect(c.regimen.data.medications).toHaveLength(1)
})

it('E4未通过结果在修订刷新重建表单后仍弹出，切换病例撤下旧结果',async()=>{
  const c=data(),reason='本轮判定可采用2026-10-01至2026-10-21的检查，请重新选择范围内检查。'
  c.regimen={id:20,kind:'medication_regimen',clinical_date:'2026-10-21',source_event_id:1,supersedes_id:null,created_at:'2026-10-21',data:{medications:[],complete:true}}
  c.examinations=[{id:30,kind:'examination',clinical_date:'2026-10-21',source_event_id:1,supersedes_id:null,created_at:'2026-10-21',data:{kind:'HbA1c',value:6.2,unit:'%',source:'本院检查',test_date:'2026-09-30',report_end_date:null,reliability:'可靠',independently_reviewed:false}}]
  setup(c,{tasks:[reason],output_text:'尚不能确认，请补充检查。'},()=>{c.patient_revision=5})
  function Harness(){const [patient,setPatient]=useState(p('ST50'));return <><button onClick={()=>setPatient({...p('ST50'),id:304})}>切换独立病例</button><ClinicalPage patient={patient} onUpdated={()=>setPatient(v=>({...v,clinical_revision:5}))} /></>}
  const user=userEvent.setup();render(<Harness />)
  await user.click(await screen.findByLabelText('作为本次缓解判定检查'))
  await user.click(within(screen.getByRole('group',{name:'HbA1c可解释'})).getByLabelText('是'))
  await user.click(screen.getByRole('button',{name:'核对客观条件'}))
  await user.click(within(await screen.findByRole('dialog',{name:'核对客观条件'})).getByRole('button',{name:'核对客观条件'}))
  const notice=await screen.findByRole('dialog',{name:'本次核对需要补充'})
  expect(notice).toHaveTextContent(reason)
  await user.keyboard('{Escape}')
  expect(await screen.findByRole('button',{name:'查看本次核对结果'})).toBeInTheDocument()
  expect(screen.queryByRole('button',{name:'医生确认缓解'})).not.toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'切换独立病例'}))
  await waitFor(()=>expect(screen.queryByRole('button',{name:'查看本次核对结果'})).not.toBeInTheDocument())
})

it('管理员页头日期窗口可取消、校验、设置和恢复，医生无按钮',async()=>{
  let simulated:string|null=null
  const fetcher=vi.fn((_input:RequestInfo|URL,init?:RequestInit)=>{
    if(init?.method==='POST')simulated=JSON.parse(String(init.body)).simulated_date
    return Promise.resolve(json({can_manage_date:true,real_date:'2026-10-21',effective_date:simulated??'2026-10-21',simulated_date:simulated}))
  })
  vi.stubGlobal('fetch',fetcher);const user=userEvent.setup()
  const view=render(<DateControl compact editable />)
  await user.click(await screen.findByRole('button',{name:'调整日期'}))
  await user.clear(screen.getByLabelText('业务日期'));await user.type(screen.getByLabelText('业务日期'),'2026/02/30')
  await user.click(screen.getByRole('button',{name:'应用日期'}))
  expect(screen.getByRole('alert')).toHaveTextContent('有效日期')
  expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(false)
  await user.keyboard('{Escape}');expect(screen.getByRole('button',{name:'调整日期'})).toHaveFocus()
  await user.click(screen.getByRole('button',{name:'调整日期'}))
  await user.clear(screen.getByLabelText('业务日期'));await user.type(screen.getByLabelText('业务日期'),'2027/01/01')
  await user.click(screen.getByRole('button',{name:'应用日期'}))
  await screen.findByText('当前日期：2027/01/01')
  await user.click(screen.getByRole('button',{name:'调整日期'}));await user.click(screen.getByRole('button',{name:'使用系统日期'}))
  await screen.findByText('当前日期：2026/10/21')
  view.unmount();vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(json({can_manage_date:false,real_date:'2026-10-21',effective_date:'2026-10-21'}))))
  render(<DateControl compact editable />)
  await screen.findByText('当前日期：2026/10/21')
  expect(screen.queryByRole('button',{name:'调整日期'})).not.toBeInTheDocument()
})

it('E4展示确切范围与所选过早检查原因，不阻止保存历史资料',()=>{
  const exam={id:30,kind:'examination' as const,clinical_date:'2026-10-21',source_event_id:1,supersedes_id:null,created_at:'2026-10-21',data:{kind:'HbA1c',value:6.2,unit:'%',source:'本院检查',test_date:'2026-09-30',report_end_date:null,reliability:'可靠',independently_reviewed:false}}
  render(<ExaminationEditor value={[]} onChange={vi.fn()} saved={[exam]} selectedIds={[30]} onSelect={vi.fn()} selectedJudge="saved:30" onJudge={vi.fn()} judgeRange={{earliest:'2026-10-01',today:'2026-10-21'}} />)
  expect(screen.getByText(/本轮已记录的判定检查日期范围/)).toHaveTextContent('2026-10-01—2026-10-21')
  expect(screen.getByText(/检测日2026-09-30早于/)).toHaveTextContent('可保留为历史资料')
  expect(screen.getByLabelText('作为本次缓解判定检查')).toBeEnabled()
})
