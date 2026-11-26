import { useEffect, useState } from 'react'
import { BadgeCheck, Gift, Plus, ScanLine, Search, Settings2, Sparkles, Ticket, Users, X } from 'lucide-react'
import { api, useApi } from '../../api'
import { Alert, Badge, Card, Empty, ErrorState, Field, Loading, Modal, PageHeader, PageLoading, Stat, Tabs, fmt, prettyTime, useAction } from '../../components/ui'

export const COUPON_TONE = { active: 'green', redeemed: 'blue', expired: 'red', cancelled: '' }
const cap = s => s[0].toUpperCase() + s.slice(1)

function StudentTokens() {
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  useEffect(() => { const t = setTimeout(() => { setQuery(q); setPage(1) }, 300); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useApi('/admin/rewards/students', { q: query, page, size: 25 })
  const [hist, setHist] = useState(null)
  const history = useApi(hist ? `/admin/rewards/students/${hist.id}/history` : null)
  const [adjust, setAdjust] = useState(null)
  const [run, busy] = useAction()
  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1
  async function saveAdjust() {
    if (await run(() => api('/admin/points/adjust', { method: 'POST', body: { user_id: adjust.id, points: Number(adjust.points), reason: adjust.reason } }), r => `New balance: ${r.balance} tokens`)) { setAdjust(null); reload(true) }
  }
  return (
    <Card viewAll title="Student tokens" actions={<div className="search" style={{ maxWidth: 260 }}><Search /><input placeholder="Name or student ID" value={q} onChange={e => setQ(e.target.value)} aria-label="Search" /></div>}>
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={6} /> : !data.items.length ? <Empty icon={Users} title="No students found" /> : <>
        <div className="table-wrap flush" style={{ marginBottom: 0 }}>
          <table className="table">
            <thead><tr><th>Student</th><th>Student ID</th><th className="num">Tokens earned</th><th className="num">Tokens redeemed</th><th className="num">Available</th><th></th></tr></thead>
            <tbody>{data.items.map(s => (
              <tr key={s.id}>
                <td><div className="strong">{s.name}</div><div className="tiny faint">{s.email}</div></td><td>{s.student_code}</td>
                <td className="num">{fmt(s.earned)}</td><td className="num">{fmt(s.redeemed)}</td><td className="num strong">{fmt(s.balance)}</td>
                <td className="right nowrap"><button className="btn sm ghost" onClick={() => setHist(s)}>History</button><button className="btn sm ghost" onClick={() => setAdjust({ ...s, points: '', reason: '' })}>Award / adjust</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="between mt-16"><span className="small muted">{data.total} students · page {page} of {pages}</span>
          <div className="row"><button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><button className="btn sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></div></div>
      </>}
      <Modal open={!!hist} title={`Token history · ${hist?.name}`} onClose={() => setHist(null)} width={620}>
        {history.loading && !history.data ? <Loading /> : !history.data?.length ? <Empty title="No token activity yet" /> : (
          <table className="table compact"><tbody>{history.data.map(t => (
            <tr key={t.id}><td className="small muted nowrap">{prettyTime(t.created_at)}</td><td>{t.description}</td><td><Badge>{t.kind}</Badge></td>
              <td className="num strong" style={{ color: t.points > 0 ? 'var(--good-text)' : undefined }}>{t.points > 0 ? '+' : ''}{t.points}</td></tr>
          ))}</tbody></table>
        )}
      </Modal>
      <Modal open={!!adjust} title={`Award or adjust tokens · ${adjust?.name}`} onClose={() => setAdjust(null)}
        footer={<><button className="btn ghost" onClick={() => setAdjust(null)}>Cancel</button><button className="btn primary" disabled={busy || !adjust?.points || (adjust?.reason || '').length < 3} onClick={saveAdjust}>Apply</button></>}>
        {adjust && <div className="stack">
          <p className="small muted">Available: <b>{adjust.balance}</b> tokens. Use this for admin-approved activities (e.g. food-waste drives). Balances can never go below zero.</p>
          <Field label="Tokens (negative to deduct)"><input className="input" type="number" value={adjust.points} onChange={e => setAdjust({ ...adjust, points: e.target.value })} /></Field>
          <Field label="Reason (shown to the student)"><input className="input" value={adjust.reason} onChange={e => setAdjust({ ...adjust, reason: e.target.value })} placeholder="e.g. Volunteered at food-waste awareness drive" /></Field>
        </div>}
      </Modal>
    </Card>
  )
}

function Coupons() {
  const [code, setCode] = useState('')
  const [found, setFound] = useState(null)
  const [status, setStatus] = useState('active')
  const list = useApi('/admin/coupons', { status })
  const [run, busy] = useAction()
  const lookup = async e => {
    e.preventDefault()
    setFound(null)
    const r = await run(() => api('/admin/coupons/lookup', { method: 'POST', body: { code } }))
    if (r) setFound(r)
  }
  const redeem = async c => {
    if (!window.confirm(`Redeem ${c.code} for ${c.student}: ${c.reward}?`)) return
    const r = await run(() => api('/admin/coupons/redeem', { method: 'POST', body: { code: c.code } }), `${c.code} redeemed`)
    if (r) { setFound(r); list.reload(true) }
  }
  const cancel = async c => {
    if (!window.confirm(`Cancel ${c.code}? ${c.tokens} tokens will be refunded to ${c.student}.`)) return
    const r = await run(() => api(`/admin/coupons/${c.id}/cancel`, { method: 'POST' }), 'Coupon cancelled and tokens refunded')
    if (r) { if (found?.id === c.id) setFound(r); list.reload(true) }
  }
  return (
    <div className="stack">
      <Card title={<><ScanLine />Validate a coupon</>} subtitle="Ask the student for the code shown in their Rewards page">
        <form className="row wrap" onSubmit={lookup}>
          <input className="input" style={{ maxWidth: 260, fontFamily: 'monospace', textTransform: 'uppercase' }} placeholder="RW-XXXXXX" value={code} onChange={e => setCode(e.target.value)} aria-label="Coupon code" />
          <button className="btn primary" disabled={busy || code.trim().length < 4}>Check code</button>
        </form>
        {found && (
          <div className="card card-pad mt-16" style={{ background: found.status === 'active' ? 'var(--brand-50)' : 'var(--surface-2)' }}>
            <div className="between wrap">
              <div><div className="strong" style={{ fontSize: 18 }}>{found.reward}</div><div className="small muted">{found.student} · {found.student_code} · {found.tokens} tokens · <code>{found.code}</code></div>
                <div className="tiny faint mt-4">Issued {prettyTime(found.created_at)}{found.expires_at ? ` · expires ${prettyTime(found.expires_at)}` : ''}{found.redeemed_at ? ` · redeemed ${prettyTime(found.redeemed_at)}` : ''}</div></div>
              <div className="row"><Badge tone={COUPON_TONE[found.status]}>{cap(found.status)}</Badge>
                {found.status === 'active' && <><button className="btn primary" disabled={busy} onClick={() => redeem(found)}><BadgeCheck />Redeem now</button><button className="btn ghost danger" disabled={busy} onClick={() => cancel(found)}>Cancel</button></>}</div>
            </div>
            {found.status !== 'active' && <Alert tone="warn">This coupon cannot be used: it is {found.status}.</Alert>}
          </div>
        )}
      </Card>
      <Card viewAll title="Coupons" actions={<Tabs value={status} onChange={setStatus} options={['active', 'redeemed', 'expired', 'cancelled'].map(s => ({ value: s, label: cap(s) }))} />}>
        {list.loading && !list.data ? <Loading /> : !list.data?.length ? <Empty icon={Ticket} title={`No ${status} coupons`} /> : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>Code</th><th>Student</th><th>Reward</th><th className="num">Tokens</th><th>Issued</th><th>Expires</th><th></th></tr></thead>
              <tbody>{list.data.map(c => (
                <tr key={c.id}><td><code>{c.code}</code></td><td><div className="small strong">{c.student}</div><div className="tiny faint">{c.student_code}</div></td><td>{c.reward}</td><td className="num">{c.tokens}</td>
                  <td className="small muted nowrap">{prettyTime(c.created_at)}</td><td className="small muted nowrap">{c.expires_at ? prettyTime(c.expires_at) : '—'}</td>
                  <td className="right nowrap">{c.status === 'active' ? <><button className="btn sm primary" disabled={busy} onClick={() => redeem(c)}>Redeem</button><button className="btn sm ghost icon-btn danger" aria-label="Cancel coupon" disabled={busy} onClick={() => cancel(c)}><X /></button></> : <Badge tone={COUPON_TONE[c.status]}>{cap(c.status)}</Badge>}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

export default function AdminRewards() {
  const { data, error, loading, reload } = useApi('/admin/rewards')
  const settings = useApi('/admin/settings')
  const [tab, setTab] = useState('coupons')
  const [run, busy] = useAction()
  const [form, setForm] = useState(null)
  const [rules, setRules] = useState(null)
  useEffect(() => { if (settings.data && !rules) setRules(settings.data) }, [settings.data, rules])
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />

  async function save() {
    const body = { name: form.name, description: form.description, points_cost: Number(form.points_cost), stock: Number(form.stock), active: form.active }
    const r = form.id ? await run(() => api(`/admin/rewards/${form.id}`, { method: 'PATCH', body }), 'Reward updated') : await run(() => api('/admin/rewards', { method: 'POST', body }), 'Reward added')
    if (r) { setForm(null); reload(true) }
  }
  async function saveRules() {
    const body = { tokens_per_attended_meal: Number(rules.tokens_per_attended_meal), points_per_confirmation: Number(rules.points_per_confirmation),
      weekly_streak_bonus: Number(rules.weekly_streak_bonus), coupon_validity_days: Number(rules.coupon_validity_days) }
    if (await run(() => api('/admin/settings', { method: 'PATCH', body }), 'Token rules saved')) { reload(true); settings.reload(true) }
  }
  const active = data.redemptions.filter(r => r.status === 'active').length

  return (
    <div className="stack">
      <PageHeader title="Rewards & Coupons" subtitle="Students earn tokens for verified attendance and good booking habits, then exchange them for coupons."
        actions={<button className="btn primary" onClick={() => setForm({ name: '', description: '', points_cost: 200, stock: 100, active: true })}><Plus />New reward</button>} />
      <div className="grid g-4">
        <Stat tone="green" icon={Sparkles} label="Tokens issued" value={fmt(data.points_issued)} />
        <Stat tone="orange" icon={Gift} label="Tokens redeemed" value={fmt(data.points_redeemed)} />
        <Stat tone="blue" icon={Ticket} label="Active coupons" value={fmt(active)} foot="waiting to be used" />
        <Stat tone="purple" icon={BadgeCheck} label="Coupons redeemed" value={fmt(data.redemptions.filter(r => r.status === 'redeemed').length)} foot="last 50 coupons" />
      </div>
      <Tabs value={tab} onChange={setTab} options={[{ value: 'coupons', label: 'Coupon validation' }, { value: 'students', label: 'Student tokens' }, { value: 'catalog', label: 'Rewards & token rules' }]} />
      {tab === 'coupons' && <Coupons />}
      {tab === 'students' && <StudentTokens />}
      {tab === 'catalog' && (
        <div className="grid g-side">
          <Card title={<><Settings2 />Token rules</>} subtitle="All values are configurable">
            {rules && <div className="stack">
              <Field label="Tokens per attended meal" hint="Paid only when attendance is recorded at the counter, never for a booking alone"><input className="input" type="number" min="0" value={rules.tokens_per_attended_meal} onChange={e => setRules({ ...rules, tokens_per_attended_meal: e.target.value })} /></Field>
              <Field label="Tokens for planning a day in advance" hint="Once per day, for answering before the deadline"><input className="input" type="number" min="0" value={rules.points_per_confirmation} onChange={e => setRules({ ...rules, points_per_confirmation: e.target.value })} /></Field>
              <Field label="Full-week planning bonus"><input className="input" type="number" min="0" value={rules.weekly_streak_bonus} onChange={e => setRules({ ...rules, weekly_streak_bonus: e.target.value })} /></Field>
              <Field label="Coupon validity (days)"><input className="input" type="number" min="1" value={rules.coupon_validity_days} onChange={e => setRules({ ...rules, coupon_validity_days: e.target.value })} /></Field>
              <div><button className="btn primary" disabled={busy} onClick={saveRules}>Save rules</button></div>
            </div>}
          </Card>
          <Card title="Rewards (token prices)">
            <div className="table-wrap flush">
              <table className="table">
                <thead><tr><th>Reward</th><th className="num">Tokens required</th><th className="num">Stock</th><th>Status</th><th></th></tr></thead>
                <tbody>{data.catalog.map(r => (
                  <tr key={r.id}><td><div className="strong small">{r.name}</div><div className="tiny faint">{r.description}</div></td>
                    <td className="num strong">{fmt(r.points_cost)}</td><td className="num">{r.stock === 0 ? <Badge tone="red">Out</Badge> : fmt(r.stock)}</td>
                    <td>{r.active ? <Badge tone="green">Active</Badge> : <Badge>Hidden</Badge>}</td>
                    <td className="right"><button className="btn sm ghost" onClick={() => setForm({ ...r })}>Edit</button></td></tr>
                ))}</tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
      <Modal open={!!form} title={form?.id ? 'Edit reward' : 'New reward'} onClose={() => setForm(null)}
        footer={<><button className="btn ghost" onClick={() => setForm(null)}>Cancel</button><button className="btn primary" disabled={busy || !form?.name} onClick={save}>Save</button></>}>
        {form && <div className="form-grid">
          <Field label="Name" className="span-all"><input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Tea" /></Field>
          <Field label="Description" className="span-all"><textarea className="textarea" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Tokens required"><input className="input" type="number" min="1" value={form.points_cost} onChange={e => setForm({ ...form, points_cost: e.target.value })} /></Field>
          <Field label="Stock"><input className="input" type="number" min="0" value={form.stock} onChange={e => setForm({ ...form, stock: e.target.value })} /></Field>
          <label className="check span-all"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} />Visible to students</label>
        </div>}
      </Modal>
    </div>
  )
}
