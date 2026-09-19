/**
 * 页面名称：KitchenSink.tsx
 * 所属层级：页面组件（pages）
 * 功能说明：**组件库自检页（M1 专用）**。
 *   用途有两个：
 *     1. 让人肉眼确认 Chrome / Material 3 视觉体系在真实浏览器中的落地效果；
 *     2. 让 `scripts/check_docs.py` 的 Token 使用率自查有意义——本页引用全部组件与
 *        全部 Token 语义类，若某个 Token 未被使用，说明它确实没有落地。
 *
 * 说明：M5 阶段本页会被真实的登录页 / 患者列表 / 患者工作台取代。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useState } from 'react'

import {
  ActionBar,
  CheckboxGroup,
  ChoiceGroup,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  EvidenceDrawer,
  FieldRow,
  LoadingBlock,
  PageHeader,
  ResultBanner,
  SettingsRow,
  SideNav,
  StatusBadge,
} from '../components'
import type { NavItem } from '../components'

// 演示用的流程单元（对应锁定稿的 6 个流程单元）
const NAV_ITEMS: NavItem[] = [
  { key: 'pre', label: '60秒缓解预评估', index: 1, active: false, done: true, locked: false },
  { key: 'full', label: '完整评估与计划', index: 2, active: false, done: true, locked: false },
  { key: 'review', label: '阶段复评', index: 3, active: true, done: false, locked: false },
  { key: 'obs', label: '缓解观察期', index: 4, active: false, done: false, locked: true },
  { key: 'judge', label: '缓解判定', index: 5, active: false, done: false, locked: true },
  { key: 'post', label: '缓解后复评', index: 6, active: false, done: false, locked: true },
]

/** 组件库自检页。 */
export default function KitchenSink() {
  // 各控件的演示状态
  const [branch, setBranch] = useState<string>('routine_action')
  const [interventions, setInterventions] = useState<string[]>(['结构化生活方式'])
  const [stopDate, setStopDate] = useState('')
  const [stageGoal, setStageGoal] = useState('安全改善明显高血糖')
  const [note, setNote] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [evidenceQuery, setEvidenceQuery] = useState('')
  const [showError, setShowError] = useState(true)

  return (
    <div className="app-shell">
      {/* 左侧导航：全应用唯一的流程进度表达（UI.md 4.1） */}
      <nav className="app-shell__nav">
        <SideNav
          items={NAV_ITEMS}
          onSelect={() => undefined}
          footer={
            <button type="button" className="side-nav__item" onClick={() => setDrawerOpen(true)}>
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
          title="阶段复评与治疗调整"
          context="演示患者 · 女 · 病历号 ZY0001 · 主动管理—缓解诱导阶段"
          actions={
            <>
              <StatusBadge tone="neutral">缓解诱导阶段</StatusBadge>
              <button type="button" className="btn btn--text" onClick={() => setDrawerOpen(true)}>
                查阅医学依据
              </button>
            </>
          }
        />

        <div className="app-shell__content">
          <div className="app-shell__content-inner">
            {showError ? (
              <ErrorBanner
                message="未能读取患者信息：后端服务未启动。"
                action={
                  <button type="button" className="btn btn--text" onClick={() => setShowError(false)}>
                    重新读取
                  </button>
                }
              />
            ) : null}

            {/* 分组 1：复评基本输入 */}
            <section className="section">
              <span className="section__title">本次复评输入</span>
              <span className="section__description">
                日常滴定、上传血糖和一般随访不生成正式复评节点。
              </span>
              <div className="card">
                <SettingsRow
                  label="最近一次 HbA1c"
                  control={
                    <input
                      className="input num"
                      defaultValue="6.8"
                      aria-label="最近一次 HbA1c"
                    />
                  }
                  description="仅作机会分层与方案参考，不作为准入或排除条件。"
                />
                <SettingsRow
                  label="当前管理阶段"
                  control={
                    <select className="select" defaultValue="缓解诱导" aria-label="当前管理阶段">
                      <option>血糖稳定</option>
                      <option>缓解诱导</option>
                    </select>
                  }
                />
                <SettingsRow
                  label="结构化生活方式干预开始日期"
                  control={<input className="input num" type="date" aria-label="生活方式干预开始日期" />}
                  description="用于计算最早可判定日期：与停药满 3 个月取较晚者。"
                />
                <SettingsRow
                  label="本次复评备注"
                  stacked
                  control={
                    <textarea
                      className="textarea"
                      value={note}
                      placeholder="记录影响本次判断的情况"
                      aria-label="本次复评备注"
                      onChange={(event) => setNote(event.target.value)}
                    />
                  }
                />
              </div>
            </section>

            {/* 分组 2：互斥临床分支（V1.0 关键改进：单选 + 优先级 + 禁用原因） */}
            <section className="section">
              <span className="section__title">本次复评分支</span>
              <span className="section__description">
                分支按优先级自上而下排列；勾选上方分支后，被覆盖的分支会禁用并说明原因。
              </span>
              <div className="card">
                <ChoiceGroup
                  legend="选择本次复评的实际分支"
                  value={branch}
                  onChange={setBranch}
                  options={[
                    {
                      value: 'uncontrolled',
                      label: '存在明显血糖失控（医生确认）',
                      hint: '确认后阶段置为血糖稳定，并生成治疗调整任务。',
                    },
                    {
                      value: 'on_treatment_non_diabetic',
                      label: '治疗下血糖已达非糖尿病范围，且仍在用获益药',
                      hint: '只记录当前状态，不建议停药、不进入观察期。',
                    },
                    {
                      value: 'stop_last_med',
                      label: '停用最后一种具有降糖作用的药物',
                      hint: '记录停药日期后，系统自动进入缓解观察期。',
                    },
                    {
                      value: 'routine_action',
                      label: '常规复评动作（继续 / 调整 / 转换阶段 / 结束主动管理）',
                      hint: '按所选动作更新阶段、目标与下次复评日期。',
                    },
                  ]}
                />
                <div className="settings-row settings-row--stacked">
                  <FieldRow label="停药日期" hint="选择「停用最后一种药物」后必填，作为观察期的时间锚点。">
                    {(fieldProps) => (
                      <input
                        {...fieldProps}
                        className="input num"
                        type="date"
                        value={stopDate}
                        disabled={branch !== 'stop_last_med'}
                        onChange={(event) => setStopDate(event.target.value)}
                      />
                    )}
                  </FieldRow>
                  {branch !== 'stop_last_med' ? (
                    <span className="settings-row__description">
                      本次未选择「停用最后一种具有降糖作用的药物」，停药日期不参与本次记录。
                    </span>
                  ) : null}
                </div>
              </div>
            </section>

            {/* 分组 3：可并存的多选（干预组合） */}
            <section className="section">
              <span className="section__title">干预组合</span>
              <span className="section__description">生活方式、降糖调整、体重管理药物与代谢手术评估可以组合使用。</span>
              <div className="card">
                <CheckboxGroup
                  legend="本次采用的干预"
                  values={interventions}
                  onChange={setInterventions}
                  options={[
                    { value: '结构化生活方式', label: '结构化生活方式干预' },
                    { value: '降糖治疗调整', label: '降糖治疗调整' },
                    { value: '体重管理药物', label: '体重管理药物' },
                    { value: '代谢手术评估', label: '代谢手术评估' },
                  ]}
                />
                <FieldRow label="一个主要阶段目标" hint="同一次复评只设一个主要目标。">
                  {(fieldProps) => (
                    <input
                      {...fieldProps}
                      className="input"
                      value={stageGoal}
                      onChange={(event) => setStageGoal(event.target.value)}
                    />
                  )}
                </FieldRow>
              </div>
            </section>

            {/* 分组 4：状态组件展示（加载 / 空态 / 徽章 / 结论） */}
            <section className="section">
              <span className="section__title">状态与结论组件</span>
              <div className="card">
                <div className="page-header__actions">
                  <StatusBadge tone="success">满足缓解条件</StatusBadge>
                  <StatusBadge tone="warning">暂缓进入</StatusBadge>
                  <StatusBadge tone="error">急性不安全</StatusBadge>
                  <StatusBadge tone="neutral">缓解观察期</StatusBadge>
                </div>
              </div>
              <ResultBanner
                tone="warning"
                text="治疗下血糖已达非糖尿病范围，暂不能判定缓解。继续按原方案管理，不建议为获得缓解标签停用具有心肾或体重获益作用的药物。"
              />
              <ResultBanner tone="success" text="客观条件已满足，请医生确认是否形成「2型糖尿病缓解」临床结论。" />
              <div className="card card--muted">
                <LoadingBlock message="正在读取观察期状态…" />
              </div>
              <div className="card">
                <EmptyState message="该患者暂无临床事件记录。" />
              </div>
            </section>
          </div>
        </div>

        {/* 底部动作条：一个界面最多一个主按钮 */}
        <ActionBar note="缺省按 12 周计算下次复评日期">
          <button type="button" className="btn btn--outlined" onClick={() => setDialogOpen(true)}>
            结束主动管理
          </button>
          <button type="button" className="btn btn--primary">
            记录本次复评结论
          </button>
        </ActionBar>
      </div>

      {/* 不可逆操作二次确认 */}
      <ConfirmDialog
        open={dialogOpen}
        title="结束主动管理"
        description="结束后患者返回常规糖尿病综合管理，本次主动缓解管理路径关闭，之后条件改变可重新发起预评估。"
        confirmLabel="结束主动管理"
        cancelLabel="保留当前管理"
        danger
        onConfirm={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
      />

      {/* 医学依据检索抽屉 */}
      <EvidenceDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        query={evidenceQuery}
        onQueryChange={setEvidenceQuery}
        hits={
          evidenceQuery
            ? [
                {
                  text: '完全停用降糖药物至少 3 个月后，HbA1c＜6.5% 可判定为 2 型糖尿病缓解。',
                  source: '中国 2 型糖尿病缓解专家共识 · 第 4 页',
                },
              ]
            : []
        }
      />
    </div>
  )
}
