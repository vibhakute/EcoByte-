import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3, Bell, CalendarCheck, CalendarX, ChefHat, ChevronDown, Clock, Coins, FileSpreadsheet, Gift, HandHeart, LayoutDashboard,
  LineChart, LogOut, Menu as MenuIcon, PiggyBank, Recycle, Sprout as SproutIcon, UtensilsCrossed, Search, Settings, ShoppingBag, Trash2, Users,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Globe, Leaf } from '../components/Illustrations'
import { BrandMark } from '../components/Brand'
import { SyntheticBanner, initials, prettyTime } from '../components/ui'

export const ADMIN_NAV = [
  { to: '/admin', label: 'Dashboard Overview', icon: LayoutDashboard, end: true },
  { to: '/admin/students', label: 'Student Management', icon: Users },
  { to: '/admin/meals', label: 'Meal & Menu', icon: ChefHat },
  { to: '/admin/donations', label: 'NGO & Food Donation', icon: HandHeart },
  { to: '/admin/holidays', label: 'Holiday Management', icon: CalendarX },
  { to: '/admin/slots', label: 'Meal Slot Management', icon: Clock },
  { to: '/admin/attendance', label: 'Attendance', icon: CalendarCheck },
  { to: '/admin/store', label: 'Canteen Store', icon: ShoppingBag },
  { to: '/admin/rewards', label: 'Rewards & Coupons', icon: Gift },
  { label: 'Reports & Analytics', icon: LineChart, children: [
    { to: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
    { to: '/admin/waste', label: 'Waste Monitoring', icon: Trash2 },
    { to: '/admin/costs', label: 'Waste Cost Tracker', icon: Coins },
    { to: '/admin/savings', label: 'Savings Tracker', icon: PiggyBank },
    { to: '/admin/reports', label: 'Reports & Exports', icon: FileSpreadsheet },
  ] },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
]
export const FLAT_NAV = ADMIN_NAV.flatMap(i => i.children || [i])

function useOutside(ref, onOut) {
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) onOut() }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [ref, onOut])
}

function PageSearch() {
  const [q, setQ] = useState('')
  const [i, setI] = useState(0)
  const nav = useNavigate()
  const ref = useRef()
  useOutside(ref, () => setQ(''))
  const hits = q ? FLAT_NAV.filter(n => n.label.toLowerCase().includes(q.toLowerCase())) : []
  const go = n => { nav(n.to); setQ('') }
  return (
    <div className="search" ref={ref}>
      <Search />
      <input placeholder="Search pages… (e.g. waste, donation)" value={q} onChange={e => { setQ(e.target.value); setI(0) }}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') setI(Math.min(i + 1, hits.length - 1))
          if (e.key === 'ArrowUp') setI(Math.max(i - 1, 0))
          if (e.key === 'Enter' && hits[i]) go(hits[i])
          if (e.key === 'Escape') setQ('')
        }} aria-label="Search pages" />
      {q && (
        <div className="search-results">
          {hits.length ? hits.map((n, k) => <a key={n.to} className={k === i ? 'on' : ''} onMouseDown={e => { e.preventDefault(); go(n) }}><n.icon />{n.label}</a>)
            : <div className="small faint" style={{ padding: 10 }}>No page matches “{q}”</div>}
        </div>
      )}
    </div>
  )
}

function Notifications() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState({ unread: 0, items: [] })
  const ref = useRef()
  const nav = useNavigate()
  useOutside(ref, () => setOpen(false))
  const load = () => api('/admin/notifications').then(setData).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [])
  async function toggle() {
    setOpen(!open)
    if (!open && data.unread) { await api('/admin/notifications/read', { method: 'POST' }).catch(() => {}); setTimeout(load, 1500) }
  }
  return (
    <div className="icon-wrap" ref={ref}>
      <button className="btn ghost icon-btn" style={{ width: 42, height: 42 }} onClick={toggle} aria-label={`Notifications (${data.unread} unread)`}><Bell size={21} /></button>
      {data.unread > 0 && <span className="bell-badge">{data.unread}</span>}
      {open && (
        <div className="dropdown">
          <div className="dropdown-head"><b>Notifications</b><span className="tiny faint">NGO responses & alerts</span></div>
          <div className="dropdown-list">
            {!data.items.length ? <div className="small faint" style={{ padding: 20, textAlign: 'center' }}>No notifications yet</div>
              : data.items.map(n => (
                <a key={n.id} className={`notif ${n.read ? '' : 'unread'}`} onClick={() => { if (n.link) nav(n.link); setOpen(false) }} style={{ cursor: n.link ? 'pointer' : 'default' }}>
                  <Leaf style={{ width: 18, height: 18, flexShrink: 0, marginTop: 2 }} />
                  <div><div className="strong">{n.title}</div>{n.body && <div className="muted small">{n.body}</div>}<div className="tiny faint mt-4">{prettyTime(n.created_at)}</div></div>
                </a>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function NavGroup({ g }) {
  const loc = useLocation()
  const inside = g.children.some(c => loc.pathname === c.to)
  const [open, setOpen] = useState(inside)
  useEffect(() => { if (inside) setOpen(true) }, [inside])
  return (
    <div>
      <button className={`nav-link nav-group ${inside ? 'inside' : ''}`} onClick={() => setOpen(!open)} aria-expanded={open}>
        <g.icon />{g.label}<ChevronDown className="chev" style={{ transform: open ? 'rotate(180deg)' : 'none' }} />
      </button>
      {open && <div className="nav-children">
        {g.children.map(c => <NavLink key={c.to} to={c.to} className={({ isActive }) => `nav-link sub ${isActive ? 'active' : ''}`}><c.icon />{c.label}</NavLink>)}
      </div>}
    </div>
  )
}

function ImpactCard() {
  const [d, setD] = useState(null)
  useEffect(() => {
    const load = () => api('/admin/impact').then(setD).catch(() => {})
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])
  const donated = d ? [d.donated_portions ? `${d.donated_portions} meals` : '', d.donated_kg ? `${d.donated_kg} kg` : ''].filter(Boolean).join(' + ') || '0' : '–'
  const rows = [[UtensilsCrossed, 'Meals served', d ? d.meals_served.toLocaleString('en-IN') : '–'],
    [Recycle, 'Food waste', d ? `${d.waste_kg} kg` : '–'], [HandHeart, 'Donated', donated]]
  return (
    <div className="impact-card">
      <div className="impact-head"><span className="impact-icon"><SproutIcon /></span><div><b>This week's impact</b><span>Last 7 days · live</span></div></div>
      {rows.map(([I, label, value]) => <div className="impact-row" key={label}><I /><span>{label}</span><b>{value}</b></div>)}
    </div>
  )
}

export function Sidebar({ items, open, art, caption, footer, card }) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-brand">
        <BrandMark size={52} />
        <div className="wordmark"><span>Eco<span style={{ color: '#9be07a' }}>Byte</span></span></div>
        <div className="tagline">Reduce Waste. Feed Better.</div>
      </div>
      <nav className="sidebar-nav">
        {items.map(i => i.children ? <NavGroup key={i.label} g={i} /> : (
          <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><i.icon />{i.label}</NavLink>
        ))}
      </nav>
      {footer}
      <div className="sidebar-art">{card || <div className="art-card">{art || <Globe />}<div className="caption">{caption}</div></div>}</div>
    </aside>
  )
}

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  const [synthetic, setSynthetic] = useState(false)
  const loc = useLocation()
  const nav = useNavigate()
  const menuRef = useRef()
  useOutside(menuRef, () => setMenu(false))
  useEffect(() => setOpen(false), [loc.pathname])
  useEffect(() => { api('/admin/data-status').then(d => setSynthetic(d.has_synthetic)).catch(() => {}) }, [])
  const showBanner = synthetic && ['/admin/analytics', '/admin/reports', '/admin/savings', '/admin/costs'].includes(loc.pathname)

  return (
    <div className="app-shell">
      <Sidebar items={ADMIN_NAV} open={open} card={<ImpactCard />} />
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <button className="btn ghost icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu"><MenuIcon /></button>
          <PageSearch />
          <div style={{ flex: 1 }} />
          <Notifications />
          <div className="icon-wrap" ref={menuRef}>
            <button className="profile-chip" onClick={() => setMenu(!menu)} aria-label="Account menu">
              <span className="avatar">{initials(user?.name)}</span>
              <span className="pname strong small">{user?.name}</span><ChevronDown size={16} className="pname" />
            </button>
            {menu && (
              <div className="menu-pop">
                <div style={{ padding: '6px 10px 8px' }}><div className="strong small">{user?.name}</div><div className="tiny faint">{user?.email}</div></div>
                <a onClick={() => { setMenu(false); nav('/admin/settings') }}><Settings />Settings</a>
                <button onClick={() => { logout(); nav('/admin/login') }}><LogOut />Sign out</button>
              </div>
            )}
          </div>
        </header>
        <SyntheticBanner show={showBanner} />
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}
