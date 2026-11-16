import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './authContext'
import { STATION } from '../config/station'
import {
  IconCredit,
  IconDashboard,
  IconFuel,
  IconReports,
  IconSettings,
  IconShifts,
  LogoMark,
} from './icons'

const NAV_ITEMS = [
  { to: '/', icon: IconDashboard, label: 'Dashboard', tab: 'Home', end: true },
  { to: '/shifts', icon: IconShifts, label: 'Shift & readings', tab: 'Shifts', end: true },
  { to: '/fuel', icon: IconFuel, label: 'Fuel & stock', tab: 'Fuel', end: true },
  { to: '/credit', icon: IconCredit, label: 'Credit ledger', tab: 'Credit', end: true },
  { to: '/reports', icon: IconReports, label: 'Reports', tab: 'Reports', end: true },
] as const

const CRUMBS: Record<string, string> = {
  '/': 'Dashboard',
  '/shifts': 'Shift & readings',
  '/fuel': 'Fuel & stock',
  '/credit': 'Credit ledger',
  '/reports': 'Reports',
  '/settings': 'Station settings',
}

// The tab bar only mounts on phone-sized viewports so desktop/screen-reader
// navigation never has two links with the same name.
function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(
    () =>
      typeof window !== 'undefined' &&
      !!window.matchMedia &&
      window.matchMedia('(max-width: 700px)').matches,
  )
  useEffect(() => {
    if (!window.matchMedia) return
    const mq = window.matchMedia('(max-width: 700px)')
    const onChange = (event: MediaQueryListEvent) => setMobile(event.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return mobile
}

export default function Layout() {
  const { pathname } = useLocation()
  const { session, online, logout } = useAuth()
  const isMobile = useIsMobile()
  const crumb = CRUMBS[pathname] ?? 'Dashboard'
  const station = session
    ? { name: session.station.name, code: session.station.code, address: STATION.address }
    : STATION
  const initials = session
    ? session.employee.name
        .split(' ')
        .map((w) => w[0] ?? '')
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'DB'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <LogoMark />
          <div>
            <b>DeepBNK</b>
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
                end={item.end}
                className={({ isActive }) => (isActive ? 'active' : '')}
              >
                <span className="ico">
                  <item.icon size={18} />
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
              <span className="ico">
                <IconSettings size={18} />
              </span>
              Station settings
            </NavLink>
          </nav>
        </div>
        <div className="sidebottom">
          {session ? (
            <>
              <strong>{online ? 'Connected' : 'Signed in · API unreachable'}</strong>
              {session.employee.name} · {session.employee.code} ({session.employee.role})
              <br />
              Station {session.station.code}
              <br />
              {!online && (
                <>
                  Live saves are unavailable until the backend is reachable.
                  <br />
                </>
              )}
              <button className="btn sidebutton" onClick={() => void logout()}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <strong>{online ? 'Backend reachable' : 'Offline'}</strong>
              {online ? 'Sign in to load station data.' : 'Sign in to load live station data.'}
              <br />
              <Link className="btn sidebutton" to="/login">
                Sign in
              </Link>
            </>
          )}
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="crumb">
            DeepBNK <span className="crumb-sep"> / </span>
            <b>{crumb}</b>
          </div>
          <div className="topright">
            <span className={session && online ? 'live' : 'live offline'}>
              {session
                ? online
                  ? '● Connected'
                  : '● Signed in · API unreachable'
                : online
                  ? '● API online'
                  : '● Offline'}
            </span>
            <Link className="topicon" to="/settings" aria-label="Station settings">
              <IconSettings size={17} />
            </Link>
            <div className="avatar">{initials}</div>
          </div>
        </header>
        <div className="stationbar">
          <span className="stationbar-name">{station.name}</span>
          <span className="stationbar-code">{station.code}</span>
          <span className="stationbar-address">{station.address}</span>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </main>
      {isMobile && (
        <nav className="tabbar" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              <span className="tabico">
                <item.icon size={17} />
              </span>
              {item.tab}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
