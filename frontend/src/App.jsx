import { Navigate, Route, Routes } from 'react-router-dom'
import { auth } from './lib/api.js'
import Shell from './components/Shell.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Transactions from './pages/Transactions.jsx'
import Invoices from './pages/Invoices.jsx'
import Customers from './pages/Customers.jsx'
import Forecast from './pages/Forecast.jsx'
import Insights from './pages/Insights.jsx'

function Protected({ children }) {
  return auth.token() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <Protected>
            <Shell>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/transactions" element={<Transactions />} />
                <Route path="/invoices" element={<Invoices />} />
                <Route path="/customers" element={<Customers />} />
                <Route path="/forecast" element={<Forecast />} />
                <Route path="/insights" element={<Insights />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Shell>
          </Protected>
        }
      />
    </Routes>
  )
}
