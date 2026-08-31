import type { ReactNode } from 'react'

export default function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-mark">FL</div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  )
}
