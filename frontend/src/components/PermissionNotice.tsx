/**
 * 组件名称：PermissionNotice.tsx
 * 功能说明：清楚说明患者只读原因；不能只用灰色控件暗示权限。
 */

interface PermissionNoticeProps {
  ownerName: string | null
}

export default function PermissionNotice({ ownerName }: PermissionNoticeProps) {
  return (
    <div className="permission-notice" role="status">
      <strong>只读 · 责任医生：{ownerName ?? '未指定'}</strong>
      <span>您的账户暂无权限编辑此条记录</span>
    </div>
  )
}
