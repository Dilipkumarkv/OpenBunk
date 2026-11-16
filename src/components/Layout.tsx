import { NavLink, Outlet, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', icon: '▦', label: 'Dashboard', end: true },
  { to: '/shifts', icon: '◷', label: 'Shift & readings' },
  { to: '/fuel', icon: '⛽', label: 'Fuel & stock' },
  { to: '/credit', icon: '⇄', label: 'Credit ledger' },
  { to: '/reports', icon: '▤', label: 'Reports' },
] as const

const CRUMBS: Record<string, string> = {
  '/': 'Dashboard',
  '/shifts': 'Shift & readings',
  '/fuel': 'Fuel & stock',
  '/credit': 'Credit ledger',
  '/reports': 'Reports',
  '/settings': 'Station settings',
}

export default function Layout() {
  const { pathname } = useLocation()
  const crumb = CRUMBS[pathname] ?? 'Dashboard'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">O</div>
          <div>
            <b>OpenBunk</b>
            <small>Station operations</small>
          </div>
        </div>
        <div>
          <div className="navlabel">Workspace</div>
          <nav className="nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={'end' in item ? item.end : false}
                className={({ isActive }) => (isActive ? 'active' : '')}
              >
                <span className="ico" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div>
          <div className="navlabel">Administration</div>
          <nav className="nav">
            <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : '')}>
              <span className="ico" aria-hidden="true">
                ⚙
              </span>
              Station settings
            </NavLink>
          </nav>
        </div>
        <div className="sidebottom">
          <strong>Prototype environment</strong>
          Sample data only · No real transactions
          <br />
          <br />
          <span className="sidebottom-note">Open source · Self-hostable</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="crumb">
            OpenBunk <span className="crumb-sep"> / </span>
            <b>{crumb}</b>
          </div>
          <div className="topright">
            <span className="live">● Demo mode</span>
            <div className="avatar">DB</div>
          </div>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
