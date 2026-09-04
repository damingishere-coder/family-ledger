import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import LoadingState from './components/LoadingState'

const AccountsPage = lazy(() => import('./pages/AccountsPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const DataPage = lazy(() => import('./pages/DataPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const NewSnapshotPage = lazy(() => import('./pages/NewSnapshotPage'))
const SnapshotDetailPage = lazy(() => import('./pages/SnapshotDetailPage'))

export default function App() {
  return (
    <Suspense fallback={<LoadingState label="正在打开页面…" />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="snapshot/new" element={<NewSnapshotPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="snapshots/:snapshotId" element={<SnapshotDetailPage />} />
          <Route path="accounts" element={<AccountsPage />} />
          <Route path="data" element={<DataPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
