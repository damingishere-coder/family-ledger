import type { ReactNode } from 'react'
import { House } from 'lucide-react'

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
      <div className="empty-mark"><House size={24} strokeWidth={2} /></div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  )
}
