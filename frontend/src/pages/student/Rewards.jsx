import { useState } from 'react'
import { CalendarCheck, Coffee, Gift, IceCream, Package, Sandwich, Sparkles, Ticket, UtensilsCrossed, Utensils } from 'lucide-react'
import { api, useApi } from '../../api'
import { Badge, Card, Empty, ErrorState, Modal, PageHeader, PageLoading, Stat, Tabs, fmt, prettyTime, useAction } from '../../components/ui'
import { GiftBox } from '../../components/Illustrations'

const ICON = name => /tea|coffee|chaas/i.test(name) ? Coffee : /sandwich|samosa/i.test(name) ? Sandwich : /dessert/i.test(name) ? IceCream
  : /hamper/i.test(name) ? Package : /meal|thali|breakfast/i.test(name) ? Utensils : Gift
const COUPON = { active: ['Active', 'green'], redeemed: ['Redeemed', 'blue'], expired: ['Expired', 'red'], cancelled: ['Cancelled', ''] }

export default function StudentRewards() {
  const { data, error, loading, reload } = useApi('/student/rewards')
  const [run, busy] = useAction()
  const [pick, setPick] = useState(null)
  const [issued, setIssued] = useState(null)
  const [tab, setTab] = useState('coupons')
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const r = data.rules

  async function redeem() {
    const res = await run(() => api('/student/rewards/redeem', { method: 'POST', body: { reward_id: pick.id } }))
    if (res) { setIssued(res); setPick(null); setTab('coupons'); reload(true) }
  }
  const active = data.redemptions.filter(c => c.status === 'active')

  return (
    <div className="stack">
      <PageHeader title="Reward Tokens" subtitle="Earn tokens for attending meals and planning ahead, then swap them for food coupons." />
      <div className="grid g-4">
        <div className="card card-pad" style={{ background: 'linear-gradient(135deg,#0f5c2e,#1f9a4a)', color: '#fff', border: 0 }}>
          <div className="small" style={{ opacity: .85 }}>Available tokens</div>
          <div className="points-big mt-8">{fmt(data.balance)}</div>
          {data.next_reward && <><div className="small mt-12" style={{ opacity: .9 }}>Next: {data.next_reward.name} ({fmt(data.next_reward.points_cost)})</div>
            <div className="meter mt-4" style={{ background: 'rgba(255,255,255,.25)' }}><i style={{ width: `${data.next_reward.progress}%`, background: '#fff' }} /></div></>}
        </div>
        <Stat tone="green" icon={Sparkles} label="Total tokens earned" value={fmt(data.earned)} />
        <Stat tone="orange" icon={Gift} label="Total tokens redeemed" value={fmt(data.redeemed)} />
        <Stat tone="blue" icon={Ticket} label="Active coupons" value={fmt(active.length)} foot={`valid ${r.coupon_validity_days} days from issue`} />
      </div>

      {issued && (
        <div className="card card-pad between wrap" style={{ borderColor: 'var(--brand-600)', background: 'var(--brand-50)' }}>
          <div><div className="strong">{issued.reward} coupon created</div><div className="small muted">{issued.points} tokens deducted · balance {fmt(issued.balance)} · valid until {prettyTime(issued.expires_at)}</div></div>
          <div className="right"><div className="tiny faint">Show this code at the counter</div><div className="strong" style={{ fontSize: 24, letterSpacing: '.06em' }}>{issued.code}</div></div>
        </div>
      )}

      <Card title="How to earn tokens">
        <div className="grid g-3">
          <div className="row" style={{ alignItems: 'flex-start' }}><span className="reward-icon"><UtensilsCrossed /></span><div><b>+{r.per_attended_meal} per meal attended</b><div className="small muted">Recorded at the counter when you are served. Booking alone doesn't earn tokens.</div></div></div>
          <div className="row" style={{ alignItems: 'flex-start' }}><span className="reward-icon"><CalendarCheck /></span><div><b>+{r.per_planned_day} per day planned</b><div className="small muted">Confirm your meals before the deadline (once per day).</div></div></div>
          <div className="row" style={{ alignItems: 'flex-start' }}><span className="reward-icon"><Sparkles /></span><div><b>+{r.weekly_bonus} full-week bonus</b><div className="small muted">Plan every open day of a week. The canteen can also award tokens for food-waste activities.</div></div></div>
        </div>
      </Card>

      <div>
        <h2 style={{ marginBottom: 12 }}>Redeem rewards</h2>
        {!data.catalog.length ? <Card><Empty icon={Gift} title="No rewards available right now" /></Card> : (
          <div className="grid g-4">{data.catalog.map(c => {
            const Icon = ICON(c.name)
            const short = c.points_cost - data.balance
            return (
              <div className="card reward" key={c.id}>
                <div className="between"><div className="reward-icon"><Icon /></div><Badge tone="green">{fmt(c.points_cost)} tokens</Badge></div>
                <div><h3>{c.name}</h3><p className="small muted mt-4">{c.description}</p></div>
                <div style={{ flex: 1 }} />
                {!c.in_stock ? <button className="btn block" disabled>Out of stock</button>
                  : short > 0 ? <button className="btn block" disabled>{fmt(short)} more tokens needed</button>
                    : <button className="btn primary block" onClick={() => setPick(c)}>Redeem</button>}
              </div>
            )
          })}</div>
        )}
      </div>

      <Card viewAll actions={<Tabs value={tab} onChange={setTab} options={[{ value: 'coupons', label: `My coupons (${data.redemptions.length})` }, { value: 'history', label: 'Token history' }]} />}>
        {tab === 'coupons' ? (!data.redemptions.length ? <Empty icon={Ticket} title="No coupons yet">Redeem tokens to get a coupon code.</Empty> : (
          <div className="list">{data.redemptions.map(c => (
            <div className="list-item" key={c.id}>
              <div><div className="small strong">{c.reward}</div><div className="tiny faint">{c.points} tokens · issued {prettyTime(c.created_at)}{c.status === 'active' && c.expires_at ? ` · expires ${prettyTime(c.expires_at)}` : ''}{c.redeemed_at ? ` · used ${prettyTime(c.redeemed_at)}` : ''}</div></div>
              <div className="row"><code className="badge outline" style={{ fontSize: 13, letterSpacing: '.05em' }}>{c.code}</code><Badge tone={COUPON[c.status][1]}>{COUPON[c.status][0]}</Badge></div>
            </div>
          ))}</div>
        )) : (!data.ledger.length ? <Empty title="No token activity yet">Attend meals and plan ahead to start earning.</Empty> : (
          <div className="table-wrap flush" style={{ marginTop: -14 }}>
            <table className="table">
              <thead><tr><th>When</th><th>Activity</th><th className="num">Tokens</th></tr></thead>
              <tbody>{data.ledger.map(t => (
                <tr key={t.id}><td className="small muted nowrap">{prettyTime(t.created_at)}</td><td>{t.description}</td>
                  <td className="num strong" style={{ color: t.points > 0 ? 'var(--good-text)' : undefined }}>{t.points > 0 ? '+' : ''}{t.points}</td></tr>
              ))}</tbody>
            </table>
          </div>
        ))}
      </Card>

      <Modal open={!!pick} title="Redeem reward" onClose={() => setPick(null)}
        footer={<><button className="btn ghost" onClick={() => setPick(null)}>Cancel</button><button className="btn primary" disabled={busy} onClick={redeem}>{busy ? 'Redeeming…' : `Redeem for ${pick?.points_cost} tokens`}</button></>}>
        {pick && <div className="row" style={{ gap: 16 }}><GiftBox style={{ width: 70, height: 70, flexShrink: 0 }} />
          <p>Exchange <b>{fmt(pick.points_cost)} tokens</b> for <b>{pick.name}</b>? Your balance goes from {fmt(data.balance)} to {fmt(data.balance - pick.points_cost)}. You'll get a coupon code to show at the counter, valid for {r.coupon_validity_days} days.</p></div>}
      </Modal>
    </div>
  )
}
