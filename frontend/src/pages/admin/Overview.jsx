import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  BarChart3, CalendarCheck, CalendarClock, CalendarDays, CalendarX, CheckCircle2, ChefHat, Coffee, HandHeart, Info, Lightbulb, Moon, Plus,
  ShoppingBag, Soup, Ticket, Trash2, TriangleAlert, Users, Zap,
} from 'lucide-react'
import { api, useApi } from '../../api'
import { useAuth } from '../../auth'
import {
  Badge, Card, Empty, ErrorState, Field, Meter, Modal, PageLoading, Ring, cap, fmt, inr, prettyDate, todayIso, useAction,
} from '../../components/ui'

export const MEAL_ICON = { breakfast: Coffee, lunch: Soup, dinner: Moon }

export function PrepModal({ item, onClose, onSaved }) {
  const [prepared, setPrepared] = useState(item?.prepared ?? item?.recommended ?? 0)
  const [att, setAtt] = useState(item?.actual_attendance ?? '')
  const [served, setServed] = useState(item?.served ?? '')
  const [run, busy] = useAction()
  if (!item) return null
  const past = item.date <= todayIso()
  async function save() {
    const ok = await run(async () => {
      await api('/admin/preparation', { method: 'POST', body: { date: item.date, meal_type: item.meal_type, meals_prepared: Number(prepared) } })
      if (past && att !== '' && served !== '') {
        await api('/admin/actuals', { method: 'POST', body: { date: item.date, meal_type: item.meal_type, actual_attendance: Number(att), meals_prepared: Number(prepared), meals_served: Number(served) } })
      }
      return true
    }, `${cap(item.meal_type)} preparation updated`)
    if (ok) { onSaved(); onClose() }
  }
  return (
    <Modal open title={`Update ${item.meal_type} preparation · ${prettyDate(item.date)}`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || prepared === ''} onClick={save}>Save</button></>}>
      <div className="stack">
        <div className="alert info"><Info /><div>Recommended: <b>{item.recommended}</b> meals ({item.predicted} predicted + {item.buffer} buffer). Saving freezes the prediction so it can be compared with what actually happens.</div></div>
        <Field label="Meals prepared"><input className="input" type="number" min="0" value={prepared} onChange={e => setPrepared(e.target.value)} /></Field>
        {past && <>
          <div className="small strong">After the service (optional)</div>
          <div className="form-grid">
            <Field label="Actual attendance" hint="Students who actually ate"><input className="input" type="number" min="0" value={att} onChange={e => setAtt(e.target.value)} /></Field>
            <Field label="Meals served"><input className="input" type="number" min="0" value={served} onChange={e => setServed(e.target.value)} /></Field>
          </div>
          <p className="tiny faint">Recording actual attendance teaches EcoByte the real turnout ratio (walk-ins vs no-shows), which improves future predictions.</p>
        </>}
      </div>
    </Modal>
  )
}

export function MealColumn({ m, onUpdate, compact }) {
  const Icon = MEAL_ICON[m.meal_type]
  const status = m.closed ? <Badge>Closed</Badge>
    : m.prepared != null ? <Badge tone="green" icon={CheckCircle2}>Prepared {fmt(m.prepared)}</Badge>
      : m.recommended > 0 ? <Badge tone="amber">Needs preparation</Badge> : <Badge>Waiting</Badge>
  return (
    <div className={`meal-col ${m.meal_type}`}>
      <div className="meal-col-head">
        <div className="mi"><Icon /></div>
        <div style={{ flex: 1, minWidth: 0 }}><h3>{m.meal_type}</h3><div className="tiny muted" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.main_dish || 'Menu not planned'}</div></div>
        {status}
      </div>
      {m.closed ? <Empty title="Canteen closed">{m.closed_reason}</Empty> : <>
        <div className="meal-rows">
          <div className="r"><span>Expected attendance</span><b>{fmt(m.expected)}</b></div>
          <div className="r"><span>Confirmed students</span><b>{fmt(m.confirmed)} <span className="tiny faint">/ {m.registered}</span></b></div>
          <div className="r"><span title={m.historical_label}>Historical average</span><b title={m.historical_label}>{fmt(m.historical_avg)}</b></div>
          <div className="r"><span>Predicted demand</span><b>{fmt(m.predicted)}</b></div>
          <div className="r"><span>{m.buffer_pct}% buffer</span><b>+{fmt(m.buffer)}</b></div>
          {!compact && <>
            <div className="r"><span>Actual meals prepared</span><b>{m.prepared != null ? fmt(m.prepared) : '—'}</b></div>
            <div className="r"><span>Meals served</span><b>{m.served != null ? fmt(m.served) : '—'}</b></div>
            <div className="r"><span>Remaining meals</span><b>{m.remaining != null ? fmt(m.remaining) : '—'}</b></div>
          </>}
        </div>
        <div className="meal-reco"><div><div className="l">Recommended to prepare</div><div className="n">{fmt(m.recommended)} <span style={{ fontSize: 14, fontWeight: 500 }}>meals</span></div></div>
          <ChefHat size={30} style={{ opacity: .7 }} /></div>
        <div className="meal-col-foot">
          <span className="tiny faint">{m.recommended_kg ? `≈ ${fmt(m.recommended_kg, 1)} kg food` : ''}</span>
          {onUpdate && <button className="btn sm soft" onClick={() => onUpdate(m)}>Update preparation</button>}
        </div>
      </>}
    </div>
  )
}

function KpiStrip({ d }) {
  const a = d.attendance
  const pct = Math.round(a.attendance_pct)
  const items = [
    [Users, 'green', 'Expected today', fmt(a.expected), 'meals', 'across breakfast, lunch & dinner'],
    [CheckCircle2, 'blue', 'Students confirmed', fmt(a.confirmed_students), `of ${a.registered}`, <><span className="kpi-bar"><i style={{ width: `${pct}%` }} /></span>{pct}% have ticked attendance</>],
    [ChefHat, 'orange', 'Cook today', fmt(d.day.recommended), 'meals', `${fmt(d.day.predicted)} expected + ${fmt(d.day.buffer)} buffer (${d.buffer_pct}%)`],
    [Trash2, 'purple', 'Waste today', fmt(d.waste.total_kg, 1), 'kg', d.waste.total_kg ? `${inr(d.waste.total_cost)}${d.waste.pct != null ? ` · ${d.waste.pct}% of food` : ''}` : <Link to="/admin/waste">Record after each meal →</Link>],
  ]
  return (
    <div className="card kpi-strip">
      {items.map(([I, tone, label, value, unit, foot]) => (
        <div className="ov-kpi" key={label}>
          <span className={`kpi-ic ${tone}`}><I /></span>
          <div style={{ minWidth: 0 }}>
            <div className="kpi-l">{label}</div>
            <div className="kpi-v">{value}<small>{unit}</small></div>
            <div className="kpi-f">{foot}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Attention({ o }) {
  const p = o.passes
  const h = o.holidays[0]
  const s = (n, one, many) => `${n} ${n === 1 ? one : many}`
  const todo = [
    o.renewals_pending > 0 && [CalendarClock, 'orange', s(o.renewals_pending, 'pass renewal request', 'pass renewal requests') + ' to approve', '/admin/students', 'Review'],
    p.expiring_soon > 0 && [CalendarClock, 'amber', s(p.expiring_soon, 'student pass expires', 'student passes expire') + ' within 7 days', '/admin/students?status=expiring_soon', 'View'],
    o.orders_pending > 0 && [ShoppingBag, 'blue', s(o.orders_pending, 'store order', 'store orders') + ' waiting to be prepared', '/admin/store', 'Open'],
    o.donations_pending > 0 && [HandHeart, 'green', s(o.donations_pending, 'donation is', 'donations are') + ' waiting for NGO pickup', '/admin/donations', 'Track'],
  ].filter(Boolean)
  return (
    <Card title={<><TriangleAlert />Needs your attention</>} subtitle={todo.length ? `${todo.length} thing${todo.length > 1 ? 's' : ''} to handle today` : undefined}>
      {!todo.length ? <div className="todo-done"><CheckCircle2 />All caught up. Nothing needs action right now.</div> : (
        <div className="todo-list">
          {todo.map(([I, tone, text, to, btn]) => (
            <Link key={text} to={to} className="todo"><span className={`todo-ic ${tone}`}><I /></span><span className="todo-t">{text}</span><span className="todo-btn">{btn} →</span></Link>
          ))}
        </div>
      )}
      <div className="todo-meta">
        <span><Users />{fmt(p.with_valid_pass)} students with an active pass</span>
        <span><Ticket />{fmt(o.coupons_active)} active coupons</span>
        <span><CalendarX /><span>{h ? <>Next holiday: <b>{h.name}</b>, {prettyDate(h.date, { weekday: 'short', day: 'numeric', month: 'short' })}</> : 'No holidays in the next 60 days'}</span></span>
      </div>
    </Card>
  )
}

export default function Overview() {
  const [date, setDate] = useState(todayIso())
  const { data, error, loading, reload } = useApi('/admin/overview', { date })
  const { user } = useAuth()
  const nav = useNavigate()
  const [prep, setPrep] = useState(null)
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const d = data
  const a = d.attendance
  const isToday = d.date === d.today
  const INS = { good: CheckCircle2, warn: TriangleAlert, info: Lightbulb }
  const actions = [
    [Plus, "Add Today's Menu", '/admin/meals'], [ChefHat, 'Update Meal Preparation', '/admin/meals'],
    [CalendarCheck, 'View Attendance', '/admin/attendance'], [BarChart3, 'View Analytics', '/admin/analytics'],
    [Trash2, 'Add Food Waste', '/admin/waste'], [HandHeart, 'Create NGO Donation Request', '/admin/donations?new=1'],
  ]

  return (
    <div className="stack">
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Hello, {user?.name || 'Admin'}! 🌱</h1>
          <p>Here's what's happening in {d.canteen_name} {isToday ? 'today' : `on ${prettyDate(d.date, { weekday: 'long', day: 'numeric', month: 'long' })}`}.</p>
        </div>
        <label className="date-pill"><CalendarDays /><input type="date" value={date} onChange={e => e.target.value && setDate(e.target.value)} aria-label="Date" /></label>
      </div>

      <KpiStrip d={d} />
      {d.operations && isToday && <Attention o={d.operations} />}

      <Card title={<><ChefHat />Daily Meal Preparation</>} subtitle={d.recommendation}
        actions={<Link className="btn sm" to="/admin/meals">Open meal planning</Link>}>
        <div className="grid g-3">
          {d.meals.map(m => <MealColumn key={m.meal_type} m={m} onUpdate={setPrep} />)}
        </div>
        <p className="tiny faint mt-12">
          {d.forecast_mode === 'hybrid' ? 'Hybrid mode: history model blended with confirmations.'
            : 'Predicted demand = confirmed students × learned turnout ratio. Everything starts at 0 and rises as students tick attendance.'}
        </p>
      </Card>

      <div className="grid g-3">
        <Card title={<><Users />Attendance Summary</>}>
          <div className="row" style={{ gap: 20, alignItems: 'center' }}>
            <Ring value={a.attendance_pct} label="confirmed" />
            <dl className="kv" style={{ flex: 1 }}>
              <dt>Registered students</dt><dd>{fmt(a.registered)}</dd>
              <dt>Confirmed</dt><dd>{fmt(a.confirmed_students)}</dd>
              <dt>Expected meals</dt><dd>{fmt(a.expected)}</dd>
              <dt>Not attending</dt><dd>{fmt(a.absent_students)}</dd>
              <dt>No response yet</dt><dd>{fmt(a.pending_students)}</dd>
            </dl>
          </div>
        </Card>
        <Card title={<><Lightbulb />Quick Insights</>}>
          {d.insights.map((x, i) => { const I = INS[x.tone] || Lightbulb; return <div key={i} className={`insight ${x.tone}`}><I />{x.text}</div> })}
        </Card>
        <Card title={<><Zap />Quick Actions</>}>
          <div className="stack" style={{ gap: 8 }}>
            {actions.map(([I, l, to]) => <button key={l} className="qa" onClick={() => nav(to)}><I />{l}</button>)}
          </div>
        </Card>
      </div>

      <div className="grid g-2">
        <Card title={<><Trash2 />Food Waste {isToday ? 'Today' : prettyDate(d.date)}</>} actions={<Link className="btn sm" to="/admin/waste">Record waste</Link>}>
          {!d.waste.total_kg ? <Empty icon={Trash2} title="No waste recorded">Add measurements after each meal in Waste Monitoring.</Empty> : (
            <div className="stack" style={{ gap: 14 }}>
              {Object.entries(d.waste.by_meal).map(([m, w]) => (
                <div key={m}><div className="between small"><span className="strong">{cap(m)}</span><span className="muted">{fmt(w.kg, 1)} kg · {inr(w.cost)}</span></div>
                  <div className="mt-4"><Meter value={w.kg} max={Math.max(...Object.values(d.waste.by_meal).map(x => x.kg), 1)} /></div></div>
              ))}
            </div>
          )}
        </Card>
        <Card title={<><HandHeart />NGO Food Donations</>} actions={<Link className="btn sm primary" to="/admin/donations?new=1"><Plus />New request</Link>}>
          {!d.donations.active ? <Empty icon={HandHeart} title="No active donations">Share safe surplus food with NGOs instead of wasting it.</Empty> : (
            <div className="list">
              {d.donations.open_qty.map(x => (
                <div className="list-item" key={x.code}>
                  <div><div className="small strong">{x.food}</div><div className="tiny faint">{x.code}</div></div>
                  <div className="row"><span className="small">{fmt(x.remaining)} {x.unit === 'kg' ? 'kg' : 'portions'} left</span><Badge tone="blue">{x.status.replace(/_/g, ' ')}</Badge></div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      {prep && <PrepModal item={prep} onClose={() => setPrep(null)} onSaved={() => reload(true)} />}
    </div>
  )
}
