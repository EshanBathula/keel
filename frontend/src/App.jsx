import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { auth } from './lib/api.js'
import Shell from './components/Shell.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import Login from './pages/Login.jsx'
import Transactions from './pages/Transactions.jsx'
import Invoices from './pages/Invoices.jsx'
import Customers from './pages/Customers.jsx'
import Insights from './pages/Insights.jsx'
import Settings from './pages/Settings.jsx'

// Dashboard and Forecast pull in Recharts — the single largest dependency in
// the bundle. Lazy-loading them keeps everything else (auth, ledger, CRUD
// pages) out of the chart library's weight until a chart page is visited.
const Dashboard = lazy(() => import('./pages/Dashboard.jsx'))
const Forecast = lazy(() => import('./pages/Forecast.jsx'))

const PageFallback = () => <div className="muted" style={{ padding: 20 }}>Loading…</div>

function Protected({ children }) {
  if (!auth.isValid()) {
    auth.clear()
    return <Navigate to="/login" replace />
  }
  return children
}

function PageRoutes() {
  // Keyed by pathname so a crash on one page doesn't leave the boundary
  // stuck showing the error UI after the user navigates elsewhere.
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname}>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/customers" element={<Customers />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <Protected>
              <Shell>
                <PageRoutes />
              </Shell>
            </Protected>
          }
        />
      </Routes>
    </ErrorBoundary>
  )
}
