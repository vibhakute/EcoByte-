import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, Bell, CalendarCheck, CalendarX, Check, Clock, Gift, History, Minus, RefreshCw, ShoppingBag, Star, Ticket, Trophy, UtensilsCrossed, X,
} from 'lucide-react'
import { api, useApi } from '../../api'
import { GiftBox, Leaf, MealImage } from '../../components/Illustrations'
import { Alert, Badge, Card, Empty, ErrorState, Field, Modal, PageLoading, cap, fmt, inr, prettyDate, prettyTime, todayIso, useAction } from '../../components/ui'
import { MEAL_ICON } from '../admin/Overview'

const D = s => prettyDate(s, { day: 'numeric', month: 'long', year: 'numeric' })

export function RenewRequest({ onClose, onDone }) {
  const { data } = useApi('/student/subscription')
  const [type, setType] = useState('monthly')
  const [run, busy] = useAction()
  const pending = data?.renewal_request?.status === 'pending'
  async function send() {
    if (await run(() => api('/student/renewal-request', { method: 'POST', body: { pass_type: type } }), 'Renewal request sent to the canteen office')) { onDone?.(); onClose() }
  }
  return (
    <Modal open title="Renew your mess pass" onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Close</button>{!pending && <button className="btn primary" disabled={busy} onClick={send}>Send renewal request</button>}</>}>
      {pending ? <Alert tone="info">Your {data.renewal_request.pass_type === 'monthly' ? 'monthly' : 'six-month'} renewal request is waiting for the canteen office. Pay at the office; the pass is activated once approved.</Alert> : (
        <div className="stack">
          {[['monthly', 'Monthly pass', '30 days'], ['six_month', 'Six-month pass', '180 days']].map(([v, l, d]) => (
            <label key={v} className="card card-pad between" style={{ cursor: 'pointer', borderColor: type === v ? 'var(--brand-600)' : undefined, boxShadow: type === v ? '0 0 0 3px var(--brand-ring)' : undefined }}>
              <span className="row"><input type="radio" name="pt" checked={type === v} onChange={() => setType(v)} style={{ accentColor: 'var(--brand)' }} /><b>{l}</b><span className="muted small">{d}</span></span>
              <b>{data ? inr(data.prices[v]) : ''}</b>
            </label>
          ))}
          <p className="small muted">Payment is made at the canteen office. Your new pass starts the day after your current pass ends (or today if it has expired).</p>
        </div>
      )}
    </Modal>
  )
}

export function PassCard({ p, onRenew }) {
  if (!p.has_pass) return (
    <div className="pass-card red"><div className="small" style={{ opacity: .85 }}>Your Mess Subscription</div>
      <div className="big mt-8" style={{ fontSize: 30 }}>No active pass</div>
      <p className="small mt-8" style={{ opacity: .9 }}>You need a mess pass to book meals.</p>
      <button className="btn mt-16" onClick={onRenew}><RefreshCw />Get a pass</button></div>
  )
  return (
    <div className={`pass-card ${p.color}`}>
      <div className="between"><span className="small" style={{ opacity: .9 }}>Your Mess Subscription</span><span className="badge" style={{ background: 'rgba(255,255,255,.22)', color: '#fff' }}>{p.label}</span></div>
      <div className="row mt-12" style={{ alignItems: 'baseline', gap: 10 }}><span className="big">{p.remaining_days}</span><span style={{ fontSize: 18, fontWeight: 600 }}>Day{p.remaining_days === 1 ? '' : 's'} Remaining</span></div>
      <div className="mt-12 meter"><i style={{ width: `${p.progress_pct}%` }} /></div>
      <div className="between small mt-8" style={{ opacity: .92 }}><span>{p.used_days} of {p.total_days} days used</span><span>{p.progress_pct}% left</span></div>
      <dl className="kv mt-12" style={{ color: '#fff' }}>
        <dt style={{ color: 'rgba(255,255,255,.8)' }}>Pass type</dt><dd>{p.pass_label}</dd>
        <dt style={{ color: 'rgba(255,255,255,.8)' }}>Expiry date</dt><dd>{D(p.expiry_date)}</dd>
      </dl>
      {p.status === 'suspended' && <div className="small mt-8">Your pass is suspended. Please contact the canteen office.</div>}
      {['expired', 'expiring_soon'].includes(p.status) && <button className="btn mt-16" onClick={onRenew}><RefreshCw />{p.status === 'expired' ? 'Renew pass' : 'Renew early'}</button>}
    </div>
  )
}

function MealCard({ m }) {
  const Icon = MEAL_ICON[m.meal_type]
  const main = m.items[0]
  return (
    <div className={`card meal-card ${m.meal_type}`}>
      <div className="head"><span className="row strong"><Icon size={18} />{cap(m.meal_type)}</span><span className="tiny muted">{m.hours}</span></div>
      <MealImage src={main?.image} meal={m.meal_type} alt={main?.name || m.meal_type} />
      <div className="body">
        {main ? <>
          <div className="row" style={{ alignItems: 'flex-start' }}><span className={`veg ${main.is_veg ? '' : 'non'}`} style={{ marginTop: 4 }} /><h3 style={{ fontSize: 16 }} className={main.available ? '' : 'strike'}>{main.name}</h3></div>
          {main.items.length > 0 && <div className="small muted">{main.items.join(' · ')}</div>}
          {!main.available && <Badge tone="red">Unavailable today</Badge>}
        </> : <div className="small muted">{m.availability === 'closed' ? 'No service' : 'Menu not published yet'}</div>}
        <div style={{ flex: 1 }} />
        <div className="between">
          <span className={`avail ${m.availability}`}>{m.availability === 'confirmed' || m.availability === 'locked' ? <Check size={14} /> : null}{m.label}</span>
          {m.availability === 'open' && <Link className="btn sm primary" to="/student/booking">Book</Link>}
        </div>
      </div>
    </div>
  )
}

export function WeekDots({ week }) {
  const today = todayIso()
  return (
    <div className="week-dots">
      {week.days.map(d => {
        const st = Object.values(d.meals).map(m => m.status)
        const yes = st.includes('coming')
        const no = !yes && st.some(Boolean)
        const cls = d.closed ? 'closed' : yes ? 'yes' : no ? 'no' : ''
        return (
          <div key={d.date} title={d.closed ? `Closed: ${d.closed_reason}` : yes ? 'Confirmed' : no ? 'Not attending' : d.locked ? 'Closed for confirmation' : 'Pending'}>
            <div className="d">{d.weekday}</div>
            <div className={`c ${cls} ${d.date === today ? 'today' : ''}`}>{d.closed ? <Minus /> : yes ? <Check /> : no ? <X /> : null}</div>
          </div>
        )
      })}
    </div>
  )
}

export default function StudentDashboard() {
  const { data, error, loading, reload } = useApi('/student/dashboard')
  const [renew, setRenew] = useState(false)
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const d = data
  const nr = d.next_reward
  const w = d.this_week
  const holidayNotes = d.notifications.filter(n => n.kind === 'holiday' && !n.read)

  return (
    <div className="stack">
      <div className="grid g-side">
        <PassCard p={d.pass} onRenew={() => setRenew(true)} />
        <div className="hero" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <h1>Welcome back to EcoByte!</h1>
          <p>Together for a greener campus 🌱</p>
          <div className="row wrap mt-16">
            {d.pending_days > 0 && <Link to="/student/attendance" className="btn primary">Plan {d.pending_days} pending day{d.pending_days > 1 ? 's' : ''} <ArrowRight /></Link>}
            <Link to="/student/booking" className="btn soft"><Clock />Book a meal slot</Link>
            <Link to="/student/store" className="btn soft"><ShoppingBag />Canteen store</Link>
          </div>
          <Leaf style={{ position: 'absolute', right: 24, bottom: 16, width: 90, height: 90, opacity: .25 }} />
        </div>
      </div>

      {holidayNotes.map(n => <Alert key={n.id} tone="warn" title={n.title}>{n.body}</Alert>)}

      <div>
        <div className="between" style={{ marginBottom: 10 }}><h2 className="row"><UtensilsCrossed size={19} className="green" />Today's Menu</h2><Link className="btn sm ghost" to="/student/menu">Full menu <ArrowRight /></Link></div>
        <div className="grid g-3">{d.today_meals.map(m => <MealCard key={m.meal_type} m={m} />)}</div>
      </div>

      <div className="grid g-3">
        <Card title={<><CalendarCheck />This Week</>} actions={<Link className="btn sm primary" to="/student/attendance">Plan meals</Link>}>
          <WeekDots week={w} />
          <div className="mt-16"><div className="progress-label"><span>{w.confirmed_days} / {w.open_days} days planned</span><span>{w.open_days ? Math.round(w.confirmed_days / w.open_days * 100) : 0}%</span></div>
            <div className="meter"><i style={{ width: `${w.open_days ? w.confirmed_days / w.open_days * 100 : 0}%` }} /></div></div>
        </Card>
        <Card title={<><Trophy />Reward Tokens</>}>
          <div className="between">
            <div><div className="row" style={{ gap: 10 }}><Star size={32} fill="#f5b301" color="#f5b301" /><span className="points-big">{fmt(d.balance)}</span></div><div className="muted small mt-4">Available tokens</div></div>
            <GiftBox style={{ width: 84, height: 84 }} />
          </div>
          {nr && <div className="mt-12"><div className="progress-label"><span>Next: {nr.name}</span><span>{nr.remaining ? `${nr.remaining} to go` : 'Ready!'}</span></div>
            <div className="meter"><i style={{ width: `${nr.progress}%` }} /></div></div>}
          <div className="row mt-12"><Link className="btn sm primary" to="/student/rewards">Redeem</Link>{d.active_coupons > 0 && <Badge tone="green"><Ticket />{d.active_coupons} active coupon{d.active_coupons > 1 ? 's' : ''}</Badge>}</div>
        </Card>
        <Card title={<><CalendarX />Upcoming Holidays</>}>
          {!d.holidays.length ? <Empty icon={CalendarX} title="No holidays announced" /> : (
            <div className="list">{d.holidays.map(h => (
              <div className="list-item" key={h.id}><div><div className="small strong">{h.name}</div><div className="tiny faint">{h.services}</div></div>
                <Badge tone="purple">{prettyDate(h.date, { weekday: 'short', day: 'numeric', month: 'short' })}</Badge></div>
            ))}</div>
          )}
        </Card>
      </div>

      <div className="grid g-2">
        <Card title={<><Clock />Upcoming Bookings</>} actions={<Link className="btn sm ghost" to="/student/booking">Manage <ArrowRight /></Link>}>
          {!d.upcoming_bookings.length ? <Empty icon={Clock} title="No upcoming bookings"><Link to="/student/booking" className="green strong">Book a slot</Link> to skip the queue.</Empty> : (
            <div className="list">{d.upcoming_bookings.map(b => (
              <div className="list-item" key={b.id}><div><div className="small strong">{cap(b.meal_type)} · {b.start}</div><div className="tiny faint">{prettyDate(b.date)} · {b.code}</div></div>
                <Badge tone={b.state === 'locked' ? 'blue' : 'green'}>{b.state === 'locked' ? 'Locked' : 'Confirmed'}</Badge></div>
            ))}</div>
          )}
        </Card>
        <Card title={<><Bell />Notifications & Activity</>} actions={<Link className="btn sm ghost" to="/student/history"><History />History</Link>}>
          {!d.notifications.length && !d.activity.length ? <Empty title="Nothing yet" /> : (
            <div className="list">
              {d.notifications.slice(0, 3).map(n => (
                <div className="list-item" key={'n' + n.id}><span className="row small" style={{ alignItems: 'flex-start' }}><span className={`notif-dot ${n.kind}`} /><span><b>{n.title}</b>{n.body && <span className="muted"> — {n.body}</span>}</span></span><span className="tiny faint nowrap">{prettyTime(n.created_at)}</span></div>
              ))}
              {d.activity.slice(0, 3).map((a, i) => (
                <div className="list-item" key={'a' + i}><span className="small">{a.text}{a.points ? <b className="green"> {a.points > 0 ? '+' : ''}{a.points} tokens</b> : ''}</span><span className="tiny faint nowrap">{prettyTime(a.at)}</span></div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="tiles">
        {[[UtensilsCrossed, 'View Menu', '/student/menu'], [Clock, 'Book Meal Slot', '/student/booking'], [ShoppingBag, 'Canteen Store', '/student/store'], [Gift, 'Rewards', '/student/rewards']].map(([I, l, to]) => (
          <Link key={l} className="tile" to={to}><I />{l}</Link>
        ))}
      </div>
      <div className="banner-bottom"><Leaf style={{ width: 26, height: 26 }} />Let's reduce food waste together!<Leaf style={{ width: 22, height: 22, transform: 'scaleX(-1)' }} /></div>
      {renew && <RenewRequest onClose={() => setRenew(false)} onDone={() => reload(true)} />}
    </div>
  )
}
