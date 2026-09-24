/**
 * 文件名称：types/index.ts
 * 所属层级：类型定义层（types）
 * 功能说明：与后端 Pydantic 模式对齐的 TypeScript 类型。
 *   字段名与后端保持一致（snake_case），便于对照 `_SPEC/07` 与 `MAPPING.md`。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

// ===== 账号 =====

export interface UserOut {
  id: number
  username: string
  display_name: string
  department?: string | null
  role: string
  is_test_account: boolean
  simulated_date: string | null
}

export interface AuthStatusOut {
  needs_bootstrap: boolean
}

export interface LoginOut {
  token: string
  expires_at: number
  user: UserOut
}

// ===== 患者 =====

export interface Patient {
  id: number
  name: string
  gender: string
  birth_date: string
  medical_record_no: string
  department: string
  contact_phone: string | null
  created_by: number | null
  profile_complete: boolean
  is_test_patient: boolean
  height_cm: number | null
  weight_kg: number | null
  bmi: number | null
  current_state: string
  stage: string | null
  stage_goal: string | null
  interventions: string | null
  next_review_date: string | null
  last_med_stop_date: string | null
  lifestyle_start_date: string | null
  surgery_date: string | null
  earliest_judge_date: string | null
  remission_confirmed_date: string | null
  has_glucose_lowering_drug: boolean | null
  drug_purpose: string | null
  created_at: string
}

export interface PatientCreateIn {
  name: string
  gender: '男' | '女'
  birth_date: string
  medical_record_no: string
  department: string
  contact_phone: string | null
}

export interface ReferenceData {
  departments: string[]
  diagnosis_bases: string[]
  drug_classes: string[]
}

export interface ImportRowResult {
  row: number
  medical_record_no: string | null
  status: 'success' | 'skipped' | 'failed'
  message: string
}

export interface PatientImportOut {
  success_count: number
  skipped_count: number
  failed_count: number
  rows: ImportRowResult[]
}

export interface EventOut {
  id: number
  rule_id: string
  source: string
  source_state: string
  target_state: string
  template_id: string | null
  output_text: string
  operator_id: number
  simulated_date: string | null
  created_at: string
}

export interface EventPage {
  total: number
  items: EventOut[]
}

// ===== 测试能力 =====

export interface TestContextOut {
  test_mode_enabled: boolean
  can_use_test_tools: boolean
  real_date: string
  effective_date: string
  simulated_date: string | null
}

// ===== 领域数据（由后端导出，前端不得自行硬编码）=====

export interface StateOut {
  code: string
  name: string
}

export interface FlowUnitOut {
  key: string
  index: number
  label: string
  states: string[]
}

export interface BranchOut {
  priority: number
  key: string
  rule_id: string
  label: string
  hint: string
  target: string
}

// ===== 临床流程结果 =====

export interface PreAssessmentResult {
  conclusion: string
  rule_id: string
  template_id: string
  output_text: string
  target_state: string
  hold_reasons: string[]
  return_hint: string | null
}

export interface FullAssessmentResult {
  rule_id: string
  template_id: string
  output_text: string
  target_state: string
  stage: string | null
  stage_goal: string | null
  interventions: string | null
  next_review_date: string | null
}

export interface PhaseReviewResult {
  rule_id: string
  template_id: string
  output_text: string
  target_state: string
  stage: string | null
  stage_goal: string | null
  next_review_date: string | null
  entered_observation: boolean
  earliest_judge_date: string | null
  /** 被更高优先级分支覆盖的说明（前端必须展示，不得静默丢弃） */
  ignored_branches: string[]
}

export interface ObservationStatus {
  stage: string
  last_med_stop_date: string | null
  lifestyle_start_date: string | null
  surgery_date: string | null
  earliest_judge_date: string | null
  due: boolean
  rule_id: string
  template_id: string
  output_text: string
}

export interface MedicationRestartResult {
  rule_id: string
  template_id: string
  output_text: string
  target_state: string
  stage: string
  stage_goal: string | null
}

export interface RemissionJudgeResult {
  blocked: boolean
  objective_met: boolean
  rule_id: string
  template_id: string
  output_text: string
  /** 空字符串表示"返回哪个阶段由医生选择" */
  target_state: string
  doctor_confirmation_required: boolean
  needs_target_stage: boolean
  needs_followup_tasks: boolean
}

export interface PostRemissionResult {
  rule_id: string
  template_id: string
  output_text: string
  target_state: string
  stage: string | null
  next_review_date: string | null
}

// ===== 界面用枚举（取值与最小字段映射一致）=====

export const YES = '是'
export const NO = '否'
export const PENDING = '待确认'

export const HOLD_ACUTE = '急性安全'
export const HOLD_TYPE = '分型存疑'
export const HOLD_DATA = '关键治疗背景不足'

export const STAGE_STABLE = '血糖稳定'
export const STAGE_INDUCTION = '缓解诱导'
export const STAGES: readonly string[] = [STAGE_STABLE, STAGE_INDUCTION]

export const START = '启动'
export const HOLD_SUPPLEMENT = '暂缓补充关键资料'
export const NOT_START = '当前不启动'

export const ACT_CONTINUE = '继续当前阶段'
export const ACT_ADJUST = '调整方案或目标'
export const ACT_SWITCH = '转换阶段'
export const ACT_END = '结束主动管理'

export const PURPOSE_GLYCEMIC = '高血糖治疗'
export const PURPOSE_ORGAN = '器官获益'
export const PURPOSE_WEIGHT = '体重获益'

export const MED_UNUSED = '未使用'
export const MED_FOR_HYPERGLYCEMIA = '因高血糖'
export const MED_FOR_ORGAN = '因器官获益'
export const MED_FOR_WEIGHT = '因体重获益'

export const GLUCOSE_BELOW = '低于糖尿病诊断阈值'
export const GLUCOSE_DIABETIC = '达到糖尿病范围'
export const GLUCOSE_UNEXPLAINED = '暂不能可靠解释'

export const OPT_INSULIN: readonly string[] = ['未用', '短期强化', '长期使用', '其他']
export const OPT_DRUG_PURPOSE_FALLBACK: readonly string[] = [
  PURPOSE_GLYCEMIC,
  PURPOSE_ORGAN,
  PURPOSE_WEIGHT,
  '其他',
]
export const OPT_DEMANDS: readonly string[] = ['减重', '减药', '了解缓解', '无明确诉求']
export const OPT_INTERVENTIONS: readonly string[] = [
  '结构化生活方式',
  '降糖治疗调整',
  '体重管理药物',
  '代谢手术评估',
]
export const OPT_SAFETY_ISSUES: readonly string[] = [
  '无',
  '低血糖',
  '明显高血糖',
  '药物不良反应',
  '营养风险',
  '急性疾病',
]
export const OPT_TREATMENT_CHANGES: readonly string[] = ['无', '新增', '减量', '停用', '无法继续']
export const OPT_CONSTRAINTS: readonly string[] = [
  'CKD',
  'ASCVD或心衰',
  '严重视网膜病变',
  '低血糖',
  '衰弱',
  '相关用药',
]
export const OPT_RISK_TRIGGERS: readonly string[] = [
  '体重反弹',
  '急性疾病',
  '糖皮质激素',
  '妊娠',
  '手术',
  '明显生活方式改变',
]
