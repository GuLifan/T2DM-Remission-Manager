/**
 * 页面名称：PatientWorkspacePage.tsx
 * 所属层级：页面组件（pages）
 * 功能说明：患者工作台壳层——左侧流程导航 + 页头 + 内容区 + 底部动作条。
 *
 * 设计要点（对应 UI.md 第 4 节）：
 *   - **全应用只有一套流程导航**（左侧），页头不放横向步骤条；
 *   - 已完成环节**可点击回看**（修复 V0.1 "已完成项被禁用、医生无法回看"的缺陷），
 *     回看以只读方式展示该环节的事件记录；
 *   - 未到达环节置灰禁用并说明原因；
 *   - 页头不显示状态代码，只用自然语言表达当前阶段。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useMemo, useState } from 'react'

import { ApiError } from '../api/client'
import { domainApi, patientApi, testSupportApi } from '../api/endpoints'
import {
  DateControl,
  ErrorBanner,
  EvidenceDrawer,
  LoadingBlock,
  PageHeader,
  SideNav,
  StatusBadge,
  TaskPanel,
  TestToolsPanel,
} from '../components'
import type { NavItem } from '../components'
import { useAsync } from '../hooks/useAsync'
import type { EventOut, FlowUnitOut, Patient, UserOut } from '../types'
import FullAssessmentPage from './flow/FullAssessmentPage'
import ObservationPage from './flow/ObservationPage'
import PhaseReviewPage from './flow/PhaseReviewPage'
import PostRemissionPage from './flow/PostRemissionPage'
import PreAssessmentPage from './flow/PreAssessmentPage'
import RemissionJudgePage from './flow/RemissionJudgePage'
import { ClosedPathPage, RegularCarePage } from './flow/SimplePages'

interface WorkspaceProps {
  patientId: number
  currentUser: UserOut
  /** 返回患者列表 */
  onBack: () => void
}

/** 各状态的当前任务说明；只解释页面任务，不承载临床规则。 */
const TASK_DESCRIPTIONS: Record<string, string> = {
  ST00: '核对患者当前情况；条件或意愿变化时，可发起 60 秒缓解预评估。',
  ST10: '完成核心问题核对，由医生决定进入完整评估、暂缓处理或当前不启动。',
  ST20: '完成一次性完整评估，并由医生确认当前阶段、主要目标与干预组合。',
  ST31: '复评安全性、阶段指标与治疗变化，由医生决定下一步管理。',
  ST32: '复评安全性、阶段指标与治疗变化，由医生决定下一步管理。',
  ST40: '查看观察期时间锚点；到达最早日期后再进入缓解判定。',
  ST50: '先核对客观条件，再由医生确认是否形成 2 型糖尿病缓解结论。',
  ST60: '完成缓解后复评，识别维持、风险变化、不可评价或缓解终止。',
  ST99: '本患者的 T2DM 缓解路径已关闭，仅保留历史记录供追溯。',
}

/** 患者工作台。 */
export default function PatientWorkspacePage({ patientId, currentUser, onBack }: WorkspaceProps) {
  const patient = useAsync((signal) => patientApi.get(patientId, signal), [patientId])
  const [viewUnitKey, setViewUnitKey] = useState<string | null>(null)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [jumping, setJumping] = useState(false)
  const [jumpError, setJumpError] = useState('')

  // 流程单元定义由后端导出（前端不硬编码）
  const flowUnits = useAsync((signal) => domainApi.flowUnits(signal), [])
  const states = useAsync((signal) => domainApi.states(signal), [])
  const events = useAsync((signal) => patientApi.events(patientId, signal), [patientId])
  const testContext = useAsync((signal) => testSupportApi.context(signal), [])

  // 测试入口必须同时满足：后端开放能力 + 当前患者明确标记为测试患者
  const testToolsEnabled = Boolean(
    testContext.data?.can_use_test_tools && patient.data?.is_test_patient,
  )

  /** 当前状态所属单元序号（用于判断已完成/未到达）。 */
  const currentIndex = useMemo(() => {
    if (!patient.data || !flowUnits.data) return -1
    const found = flowUnits.data.find((unit) => unit.states.includes(patient.data!.current_state))
    return found ? found.index : -1
  }, [patient.data, flowUnits.data])

  /** 构造左侧导航项。 */
  const navItems: NavItem[] = useMemo(() => {
    if (!flowUnits.data || !patient.data) return []
    return flowUnits.data.map((unit: FlowUnitOut) => ({
      key: unit.key,
      label: unit.label,
      index: unit.index,
      active: viewUnitKey ? unit.key === viewUnitKey : unit.states.includes(patient.data!.current_state),
      done: unit.index < currentIndex,
      // 未到达的环节禁用；已完成与当前环节可点击
      locked: testToolsEnabled ? false : unit.index > currentIndex,
    }))
  }, [flowUnits.data, patient.data, currentIndex, viewUnitKey, testToolsEnabled])

  /** 使用专用测试接口切换状态；正式状态机不受影响。 */
  async function jumpToState(targetState: string) {
    setJumping(true)
    setJumpError('')
    try {
      await testSupportApi.jumpState(patientId, targetState)
      setViewUnitKey(null)
      patient.reload()
      events.reload()
    } catch (caught) {
      setJumpError(caught instanceof ApiError ? caught.message : '切换测试环节失败，请重试。')
    } finally {
      setJumping(false)
    }
  }

  /** 处理左侧导航：测试患者可直接进入未来环节，普通患者仍按正式流程锁定。 */
  function selectUnit(key: string) {
    const unit = flowUnits.data?.find((item) => item.key === key)
    if (!unit) return
    if (testToolsEnabled && unit.index > currentIndex) {
      void jumpToState(unit.states[0])
      return
    }
    // 点击当前环节等于回到“当前步骤”视图；点击已完成环节进入只读回看
    setViewUnitKey(key === navItems.find((item) => item.active)?.key && !viewUnitKey ? null : key)
  }

  /** 某环节的事件记录（用于只读回看）。 */
  function eventsOfUnit(unitKey: string): EventOut[] {
    const unit = flowUnits.data?.find((item) => item.key === unitKey)
    if (!unit || !events.data) return []
    return events.data.items.filter(
      (event) => unit.states.includes(event.source_state) || unit.states.includes(event.target_state),
    )
  }

  /** 按当前状态渲染对应流程页面。 */
  function renderCurrentStep(loaded: Patient) {
    const props = { patient: loaded, onUpdated: () => { patient.reload(); events.reload() } }
    switch (loaded.current_state) {
      case 'ST00':
        return <RegularCarePage {...props} />
      case 'ST10':
        return <PreAssessmentPage {...props} />
      case 'ST20':
        return <FullAssessmentPage {...props} />
      case 'ST31':
      case 'ST32':
        return <PhaseReviewPage {...props} />
      case 'ST40':
        return <ObservationPage {...props} />
      case 'ST50':
        return <RemissionJudgePage {...props} />
      case 'ST60':
        return <PostRemissionPage {...props} />
      case 'ST99':
        return <ClosedPathPage {...props} />
      default:
        // 未知状态不泄漏状态代码（V0.1 的 L2 缺陷）
        return <ErrorBanner message="当前流程状态无法识别，请联系系统维护人员。" />
    }
  }

  if (patient.loading) return <LoadingBlock message="正在读取患者信息…" />
  if (patient.error || !patient.data) {
    return (
      <ErrorBanner
        message={patient.error || '未找到该患者档案。'}
        action={
          <button type="button" className="btn btn--text" onClick={onBack}>
            返回患者列表
          </button>
        }
      />
    )
  }

  const loaded = patient.data
  const currentStateName =
    states.data?.find((state) => state.code === loaded.current_state)?.name ?? '当前管理环节'

  return (
    <div className="app-shell">
      <nav className="app-shell__nav">
        <button type="button" className="side-nav__item" onClick={onBack}>
          <span className="side-nav__index" aria-hidden="true">
            ←
          </span>
          <span>返回患者列表</span>
        </button>
        {flowUnits.loading ? <LoadingBlock message="正在读取流程定义…" /> : null}
        <SideNav
          items={navItems}
          onSelect={selectUnit}
          footer={
            <button type="button" className="side-nav__item" onClick={() => setEvidenceOpen(true)}>
              <span className="side-nav__index" aria-hidden="true">
                ?
              </span>
              <span>医学依据</span>
            </button>
          }
        />
      </nav>

      <div className="app-shell__main">
        <PageHeader
          title={viewUnitKey ? `${navItems.find((item) => item.key === viewUnitKey)?.label ?? ''}（回看）` : currentStateName}
          context={`${loaded.name} · ${loaded.gender} · 病历号 ${loaded.medical_record_no} · 当前医生 ${currentUser.display_name}`}
          actions={
            <>
              <DateControl onDateChanged={onBack} />
              {loaded.is_test_patient ? <StatusBadge tone="neutral">测试患者</StatusBadge> : null}
              <StatusBadge tone="neutral">{currentStateName}</StatusBadge>
              <button type="button" className="btn btn--text" onClick={() => setEvidenceOpen(true)}>
                查阅医学依据
              </button>
            </>
          }
        />

        <div className="app-shell__content">
          <div className="app-shell__content-inner">
            {flowUnits.error ? <ErrorBanner message={flowUnits.error} /> : null}
            {states.error ? <ErrorBanner message={states.error} /> : null}
            {testContext.error ? <ErrorBanner message={testContext.error} /> : null}

            {!viewUnitKey ? (
              <TaskPanel
                title={currentStateName}
                description={TASK_DESCRIPTIONS[loaded.current_state] ?? '请完成当前环节要求。'}
              >
                {loaded.is_test_patient ? '当前为测试患者；测试行为会单独留痕。' : undefined}
              </TaskPanel>
            ) : null}

            {testToolsEnabled && states.data && !viewUnitKey ? (
              <TestToolsPanel
                states={states.data}
                currentState={loaded.current_state}
                jumping={jumping}
                error={jumpError}
                onJump={(targetState) => void jumpToState(targetState)}
              />
            ) : null}

            {viewUnitKey ? (
              /* 只读回看已完成环节（不提供任何会改变状态的控件） */
              <section className="section">
                <h2 className="section__title">该环节的历史记录</h2>
                <p className="section__description">
                  回看仅展示当时记录的自然语言结论，不提供修改入口；如需变更请回到当前环节处理。
                </p>
                {eventsOfUnit(viewUnitKey).length === 0 ? (
                  <div className="card card--muted">该环节暂无记录。</div>
                ) : (
                  <ul className="event-list">
                    {eventsOfUnit(viewUnitKey).map((event) => (
                      <li className="event-item" key={event.id}>
                        <span className="event-item__meta">
                          {event.created_at.replace('T', ' ').slice(0, 16)}
                        </span>
                        <span className="event-item__text">{event.output_text}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="page__actions">
                  <button type="button" className="btn btn--outlined" onClick={() => setViewUnitKey(null)}>
                    回到当前环节
                  </button>
                </div>
              </section>
            ) : (
              renderCurrentStep(loaded)
            )}

            {!viewUnitKey ? (
              <section className="section">
                <h2 className="section__title">本次管理记录</h2>
                <p className="section__description">按时间倒序展示，供医生回看每一步的自然语言结论。</p>
                {events.loading ? <LoadingBlock message="正在读取管理记录…" /> : null}
                {events.data && events.data.items.length > 0 ? (
                  <ul className="event-list">
                    {events.data.items.map((event) => (
                      <li className="event-item" key={event.id}>
                        <span className="event-item__meta">
                          {event.created_at.replace('T', ' ').slice(0, 16)}
                          {event.source === 'system' ? ' · 系统自动' : ''}
                          {event.source === 'debug' ? ' · 测试跳转' : ''}
                          {event.simulated_date
                            ? ` · 模拟日期 ${event.simulated_date.replaceAll('-', '/')}`
                            : ''}
                        </span>
                        <span className="event-item__text">{event.output_text}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {events.data && events.data.items.length === 0 ? (
                  <div className="card card--muted">暂无管理记录。</div>
                ) : null}
              </section>
            ) : null}
          </div>
        </div>
      </div>

      {/* 医学依据：M6 建立检索库后接入；当前显示未录入占位 */}
      <EvidenceDrawer
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        query=""
        onQueryChange={() => undefined}
        hits={[]}
      />
    </div>
  )
}
