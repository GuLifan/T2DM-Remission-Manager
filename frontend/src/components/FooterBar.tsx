import { useEffect, useState } from 'react'

import { systemApi } from '../api/endpoints'

/** 全局页脚：显示用途声明与实际后端版本。 */
export default function FooterBar() {
  const [version, setVersion] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    systemApi.health(controller.signal).then((result) => setVersion(result.version)).catch(() => undefined)
    return () => controller.abort()
  }, [])
  return (
    <footer className="footer-bar">
      <span>本工具用于辅助记录与提醒，医学决定由医生作出。</span>
      <span className="num">{version ? `版本 ${version}` : '版本读取中'}</span>
    </footer>
  )
}
