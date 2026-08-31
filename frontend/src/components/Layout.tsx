import {
  Archive,
  BarChart3,
  Database,
  Landmark,
  PanelLeftClose,
  WalletCards,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: '概览', icon: BarChart3, end: true },
  { to: '/snapshot/new', label: '开始盘点', icon: WalletCards },
  { to: '/history', label: '历史记录', icon: Archive },
  { to: '/accounts', label: '账户管理', icon: Landmark },
  { to: '/data', label: '数据管理', icon: Database },
]

export default function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">家</div>
          <div>
            <strong>家庭统计台</strong>
            <span>FamilyLedger</span>
          </div>
        </div>
        <nav>
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <PanelLeftClose size={16} />
          <span>本地保存 · 断网可用</span>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
