import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell, CalendarCheck, Clock, Coins, Gift, History, Home, LogOut, Menu as MenuIcon, ShoppingBag, Sprout as SproutIcon, Ticket, UserRound, UtensilsCrossed,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { initials, prettyTime } from '../components/ui'
import { Sidebar } from './AdminLayout'

function MyImpact() {
  const [d, setD] = useState(null)
  const loc = useLocation()
  useEffect(() => { api('/student/impact').then(setD).catch(() => {}) }, [loc.pathname])
  const pass = !d ? '–' : d.pass_status === 'suspended' ? 'Suspended' : d.pass_status === 'expired' || d.pass_status === 'none' ? 'Expired'
    : `${d.pass_days} day${d.pass_days === 1 ? '' : 's'}`
  const rows = [[UtensilsCrossed, 'Meals this week', d ? d.meals_week : '–'], [Coins, 'Reward tokens', d ? d.tokens.toLocaleString('en-IN') : '–'],
    [Ticket, 'Pass left', pass]]
  return (
    <div className="impact-card">
      <div className="impact-head"><span className="impact-icon"><SproutIcon /></span><div><b>My green score</b><span>Eat smart · waste less</span></div></div>
      {rows.map(([I, label, value]) => <div className="impact-row" key={label}><I /><span>{label}</span><b>{value}</b></div>)}
    </div>
  )
}

const NAV = [
  { to: '/student', label: 'Home', icon: Home, end: true },
  { to: '/student/attendance', label: 'Attendance', icon: CalendarCheck },
  { to: '/student/menu', label: 'Menu', icon: UtensilsCrossed },
  { to: '/student/booking', label: 'Book Slots', icon: Clock },
  { to: '/student/store', label: 'Canteen Store', icon: ShoppingBag },
  { to: '/student/rewards', label: 'Rewards', icon: Gift },
  { to: '/student/history', label: 'History', icon: History },
  { to: '/student/profile', label: 'Profile', icon: UserRound },
]
const TABS = ['/student', '/student/booking', '/student/store', '/student/rewards', '/student/attendance']

function StudentBell() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState({ unread: 0, items: [] })
  const ref = useRef()
  const nav = useNavigate()
  const loc = useLocation()
  const load = () => api('/student/notifications').then(setData).catch(() => {})
  useEffect(() => { load() }, [loc.pathname])
  useEffect(() => { const t = setInterval(load, 30000); return () => clearInterval(t) }, [])
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  async function toggle() {
    setOpen(!open)
    if (!open && data.unread) { await api('/student/notifications/read', { method: 'POST' }).catch(() => {}); setTimeout(load, 1200) }
  }
  return (
    <div className="icon-wrap" ref={ref}>
      <button className="btn ghost icon-btn" style={{ width: 42, height: 42 }} onClick={toggle} aria-label={`Notifications (${data.unread} unread)`}><Bell size={21} /></button>
      {data.unread > 0 && <span className="bell-badge">{data.unread}</span>}
      {open && (
        <div className="dropdown">
          <div className="dropdown-head"><b>Notifications</b><span className="tiny faint">Holidays, pass & orders</span></div>
          <div className="dropdown-list">
            {!data.items.length ? <div className="small faint" style={{ padding: 20, textAlign: 'center' }}>No notifications yet</div>
              : data.items.map(n => (
                <a key={n.id} className={`notif ${n.read ? '' : 'unread'}`} style={{ cursor: n.link ? 'pointer' : 'default' }} onClick={() => { if (n.link) nav(n.link); setOpen(false) }}>
                  <span className={`notif-dot ${n.kind}`} />
                  <div><div className="strong">{n.title}</div>{n.body && <div className="muted small">{n.body}</div>}<div className="tiny faint mt-4">{prettyTime(n.created_at)}</div></div>
                </a>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function StudentLayout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  useEffect(() => setOpen(false), [loc.pathname])

  return (
    <div className="app-shell student">
      <Sidebar items={NAV} open={open} card={<MyImpact />} />
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <div className="main">
        <div className="s-topbar">
          <button className="btn ghost icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu"><MenuIcon /></button>
          <span className="avatar lg light">{initials(user?.name)}</span>
          <div style={{ minWidth: 0 }}>
            <div className="hello">Hello, {user?.name?.split(' ')[0]}!</div>
            <div className="small muted">Student ID: {user?.student_code}</div>
          </div>
          <div style={{ flex: 1 }} />
          <StudentBell />
          <button className="btn ghost icon-btn" style={{ width: 42, height: 42 }} aria-label="Sign out" title="Sign out" onClick={() => { logout(); nav('/login') }}><LogOut size={20} /></button>
        </div>
        <main className="content" style={{ paddingTop: 4 }}><Outlet /></main>
      </div>
      <nav className="tabbar">
        {TABS.map(t => NAV.find(i => i.to === t)).map(i => <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => (isActive ? 'active' : '')}><i.icon />{i.label.replace('Canteen ', '')}</NavLink>)}
      </nav>
    </div>
  )
}
