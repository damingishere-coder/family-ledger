import {
  Archive,
  BarChart3,
  Database,
  Landmark,
  ShieldCheck,
  WalletCards,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'

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
        <Link className="brand" to="/" aria-label="家底 FamilyLedger，返回概览">
          <img className="brand-logo" src="/brand/familyledger-logo.svg" alt="" width="250" height="64" />
        </Link>
        <nav>
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="sidebar-status-dot" />
          <ShieldCheck size={16} />
          <div>
            <strong>本地数据存储</strong>
            <span>仅保存在本地设备</span>
          </div>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
