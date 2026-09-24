import { useState } from 'react'

import type { PatientImportOut } from '../types'

interface ImportDialogProps {
  open: boolean
  onClose: () => void
  onImport: (file: File) => Promise<PatientImportOut>
  onCompleted: () => void
}

/** 患者表格导入对话框：先说明模板列，再逐行展示成功、跳过与失败。 */
export default function ImportDialog({ open, onClose, onImport, onCompleted }: ImportDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<PatientImportOut | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  if (!open) return null

  async function submit() {
    if (!file) {
      setError('请先选择 xlsx 或 csv 文件。')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const imported = await onImport(file)
      setResult(imported)
      onCompleted()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '导入失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="confirm-dialog__scrim" role="presentation">
      <div className="confirm-dialog import-dialog" role="dialog" aria-modal="true" aria-label="批量导入患者">
        <span className="confirm-dialog__title">批量导入患者</span>
        <p className="page__subtitle">表头须包含：姓名、出生年、出生月、性别、住院号、当前科室、联系方式。重复住院号会跳过，不覆盖既有档案。</p>
        <input
          className="input"
          type="file"
          accept=".xlsx,.csv"
          aria-label="选择患者导入文件"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null)
            setResult(null)
          }}
        />
        {error ? <span className="field-row__error" role="alert">{error}</span> : null}
        {result ? (
          <div className="stack stack--compact">
            <p>成功 {result.success_count} 行，跳过 {result.skipped_count} 行，失败 {result.failed_count} 行。</p>
            <ul className="import-result-list">
              {result.rows.map((row) => (
                <li key={`${row.row}-${row.medical_record_no ?? ''}`}>
                  第 {row.row} 行 · {row.medical_record_no ?? '未识别住院号'} · {row.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="confirm-dialog__actions">
          <button type="button" className="btn btn--text" onClick={onClose}>关闭</button>
          <button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submit()}>
            {submitting ? '正在导入…' : '开始导入'}
          </button>
        </div>
      </div>
    </div>
  )
}
