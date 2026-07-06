import { NavLink, useNavigate } from 'react-router-dom'
import { auth } from '../lib/api.js'

const KeelMark = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 2v14c0 3-2.5 6-6 6" stroke="#c08a2d" strokeWidth="2.4" strokeLinecap="round" />
    <path d="M12 6c3.5 0 7 2 8 6-3 .5-6-.5-8-3" fill="#eef2f3" />
  </svg>
)

export default function Shell({ children }) {
  const navigate = useNavigate()
  const user = auth.user()
  const links = [
    ['/', 'Dashboard'],
    ['/transactions', 'Transactions'],
    ['/invoices', 'Invoices'],
    ['/customers', 'Customers'],
    ['/forecast', 'Forecast'],
    ['/insights', 'Insights'],
  ]
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><KeelMark /> Keel</div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
          ))}
        </nav>
        <div className="spacer" />
        <div style={{ padding: '0 12px 10px', fontSize: 13, color: '#b9cdc9' }}>{user?.business_name}</div>
        <button className="signout" onClick={() => { auth.clear(); navigate('/login') }}>
          Sign out
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  )
}
