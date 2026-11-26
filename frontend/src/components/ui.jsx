import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronDown, Database, Info, X, XCircle } from 'lucide-react'

/* ---------- formatting ---------- */
export const fmt = (n, d = 0) => (n === null || n === undefined || Number.isNaN(n) ? '—'
  : Number(n).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d }))
export const inr = (n, d = 0) => (n === null || n === undefined ? '—' : '₹' + fmt(n, d))
export const kg = n => (n === null || n === undefined ? '—' : `${fmt(n, 1)} kg`)
export const pct = (n, d = 1) => (n === null || n === undefined ? '—' : `${fmt(n, d)}%`)
export const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : '')
export const iso = d => {
  const x = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return x.toISOString().slice(0, 10)
}
export const addDays = (s, n) => { const d = new Date(s + 'T00:00:00'); d.setDate(d.getDate() + n); return iso(d) }
export const todayIso = () => iso(new Date())
export const prettyDate = (s, opts = { weekday: 'short', day: 'numeric', month: 'short' }) =>
  s ? new Date(s.length <= 10 ? s + 'T00:00:00' : s).toLocaleDateString('en-IN', opts) : '—'
export const prettyTime = s => (s ? new Date(s).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '—')
export const mondayOf = s => { const d = new Date(s + 'T00:00:00'); const wd = (d.getDay() + 6) % 7; d.setDate(d.getDate() - wd); return iso(d) }

/* ---------- layout ---------- */
export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

/**
 * Shows only the first `limit` rows of the list inside it, with a "View all N" button.
 * Works on any table (tbody rows), `.list` items or an element marked `data-viewall` (its children),
 * so pages keep their own markup. Rows are hidden, not removed, so nothing is refetched.
 */
export function ViewAll({ children, limit = 5, noun = '' }) {
  const ref = useRef(null)
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  useLayoutEffect(() => {
    const box = ref.current?.querySelector('[data-viewall], tbody, .list')
    const rows = box ? [...box.children] : []
    rows.forEach((r, i) => { r.hidden = !open && i >= limit })
    if (rows.length !== count) setCount(rows.length)
  })
  return (
    <div ref={ref} className="viewall">
      {children}
      {count > limit && (
        <div className="viewall-bar">
          <button type="button" className="btn sm ghost" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Show less' : `View all ${count}${noun ? ` ${noun}` : ''}`}
            <ChevronDown size={15} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }} />
          </button>
        </div>
      )}
    </div>
  )
}

export function Card({ title, subtitle, actions, children, footer, className = '', pad = false, bodyClass = '', viewAll }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>{title && <h2>{title}</h2>}{subtitle && <div className="sub">{subtitle}</div>}</div>
          {actions && <div className="row wrap">{actions}</div>}
        </div>
      )}
      <div className={pad ? 'card-pad' : `card-body ${bodyClass}`}>{viewAll ? <ViewAll limit={viewAll === true ? 5 : viewAll}>{children}</ViewAll> : children}</div>
      {footer && <div className="card-foot">{footer}</div>}
    </section>
  )
}

export function Kpi({ icon: Icon, label, value, unit, foot, loading }) {
  return (
    <div className="card kpi">
      <div className="kpi-label">{Icon && <Icon />}{label}</div>
      {loading ? <div className="skeleton" style={{ height: 28, width: '60%' }} />
        : <div className="kpi-value">{value}{unit && value !== '—' && <small>{unit}</small>}</div>}
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  )
}

export function Badge({ tone, children, icon: Icon }) {
  return <span className={`badge ${tone || ''}`}>{Icon && <Icon />}{children}</span>
}

export function Seg({ value, onChange, options }) {
  return (
    <div className="seg" role="tablist">
      {options.map(o => {
        const v = typeof o === 'string' ? o : o.value
        const l = typeof o === 'string' ? cap(o) : o.label
        return <button key={v} role="tab" aria-selected={value === v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{l}</button>
      })}
    </div>
  )
}

export function Field({ label, hint, children, className = '' }) {
  return <div className={`field ${className}`}><label>{label}</label>{children}{hint && <span className="hint">{hint}</span>}</div>
}

export function Alert({ tone = 'info', title, children }) {
  const Icon = { warn: AlertTriangle, error: XCircle, success: CheckCircle2, info: Info }[tone] || Info
  return <div className={`alert ${tone}`}><Icon /><div>{title && <b>{title} </b>}{children}</div></div>
}

export function Empty({ icon: Icon = Database, title = 'Nothing here yet', children }) {
  return <div className="empty"><Icon /><b>{title}</b>{children && <div className="small">{children}</div>}</div>
}

export function Loading({ rows = 3, height = 18 }) {
  return (
    <div className="stack" style={{ gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ height, width: `${90 - i * 12}%` }} />)}
    </div>
  )
}

export function PageLoading() {
  return (
    <div className="stack">
      <div className="skeleton" style={{ height: 28, width: 260 }} />
      <div className="grid g-4">{[0, 1, 2, 3].map(i => <div key={i} className="card kpi"><Loading rows={2} /></div>)}</div>
      <div className="card card-pad"><div className="skeleton" style={{ height: 260 }} /></div>
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="card card-pad">
      <Alert tone="error" title="Couldn't load this page.">{error}</Alert>
      {onRetry && <button className="btn mt-12" onClick={() => onRetry()}>Try again</button>}
    </div>
  )
}

export function Meter({ value, max = 100, progress = false }) {
  const p = Math.max(0, Math.min(100, (value / (max || 1)) * 100))
  return <div className={`meter ${progress ? '' : p >= 95 ? 'red' : p >= 80 ? 'amber' : ''}`} role="meter" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${p}%` }} /></div>
}

export function Modal({ open, title, onClose, children, footer, width }) {
  useEffect(() => {
    if (!open) return
    const h = e => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="modal-scrim" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} style={width ? { maxWidth: width } : undefined}>
        <div className="modal-head"><h2>{title}</h2><button className="btn ghost icon-btn" onClick={onClose} aria-label="Close"><X /></button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function Spinner() { return <span className="spinner" aria-label="Loading" /> }

export function SyntheticBanner({ show }) {
  if (!show) return null
  return (
    <div className="synthetic-banner"><AlertTriangle />
      <span><b>Historical data is synthetic.</b> The 2025 records (EcoByte_2025_Synthetic_Canteen_Data.xlsx) are demonstration data used for analytics only. Live numbers come from real student confirmations and your entries.</span>
    </div>
  )
}

/** Pastel stat card from the reference design. tone: green | blue | orange | purple | white */
export function Stat({ icon: Icon, label, value, unit, foot, tone = 'green', loading }) {
  return (
    <div className={`stat ${tone}`}>
      {Icon && <div className="ic"><Icon /></div>}
      <div style={{ minWidth: 0 }}>
        <div className="lbl">{label}</div>
        {loading ? <div className="skeleton" style={{ height: 30, width: 80, marginTop: 4 }} />
          : <div className="val">{value}{unit && value !== '—' && <small>{unit}</small>}</div>}
        {foot && <div className="foot">{foot}</div>}
      </div>
    </div>
  )
}

export function Ring({ value = 0, label, color = 'var(--brand-600)' }) {
  const v = Math.max(0, Math.min(100, value || 0))
  const r = 46, c = 2 * Math.PI * r
  return (
    <div className="ring" role="img" aria-label={`${Math.round(v)}% ${label || ''}`}>
      <svg viewBox="0 0 112 112">
        <circle cx="56" cy="56" r={r} fill="none" stroke="var(--surface-3)" strokeWidth="12" />
        <circle cx="56" cy="56" r={r} fill="none" stroke={color} strokeWidth="12" strokeLinecap="round" strokeDasharray={`${(v / 100) * c} ${c}`} />
      </svg>
      <div className="c"><div>{Math.round(v)}%{label && <small>{label}</small>}</div></div>
    </div>
  )
}

export function Tabs({ value, onChange, options }) {
  return (
    <div className="tabs" role="tablist">
      {options.map(o => <button key={o.value} role="tab" aria-selected={value === o.value} className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  )
}

export const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }
export const initials = n => (n || '?').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()
export const toLocalInput = d => { const x = new Date(d.getTime() - d.getTimezoneOffset() * 60000); return x.toISOString().slice(0, 16) }

/* ---------- toasts ---------- */
const ToastCtx = createContext(() => {})
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((msg, tone = 'success') => {
    const id = Math.random()
    setItems(x => [...x, { id, msg, tone }])
    setTimeout(() => setItems(x => x.filter(t => t.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map(t => (
          <div key={t.id} className={`toast ${t.tone}`}>{t.tone === 'error' ? <XCircle /> : <CheckCircle2 />}<span>{t.msg}</span></div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

/** Wrap an async action with busy state + toast on error. */
export function useAction() {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const run = useCallback(async (fn, success) => {
    setBusy(true)
    try {
      const r = await fn()
      if (success) toast(typeof success === 'function' ? success(r) : success)
      return r
    } catch (e) {
      toast(e.message, 'error')
      return undefined
    } finally { setBusy(false) }
  }, [toast])
  return [run, busy]
}
