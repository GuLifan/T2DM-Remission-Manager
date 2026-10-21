/** 业务展示兼容层：保留原始数据库编号与历史来源，只转换已约定的展示值。 */
export function patientNumber(patient: {id: number; display_record_no?: string}): string {
  return patient.display_record_no || `ETMMS-${String(patient.id).padStart(6, '0')}`
}

export function historicalSource(value: string): string {
  return value === '测试数据' ? '历史录入来源' : value
}

/** 仅识别系统过去生成的维护事件模板，不清洗医生自由文本或原始payload。 */
export function eventText(text: string, source: string): string {
  if (source !== 'debug') return text
  const old = /^测试模式：已切换至“(.+)”。本记录不属于正式临床流程。$/.exec(text)
  return old ? `历史维护记录：状态调整为“${old[1]}”。` : text
}
