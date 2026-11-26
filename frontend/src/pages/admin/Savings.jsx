import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BadgeCheck, Calculator, PiggyBank, Receipt, TrendingDown } from 'lucide-react'
import { api, useApi } from '../../api'
import { C, Legend, Tip, axisProps, barCursor, cursor, gridProps, yAxisProps } from '../../components/charts'
import { Alert, Badge, Card, Empty, ErrorState, Field, Kpi, Modal, PageHeader, PageLoading, fmt, inr, useAction } from '../../components/ui'

const k = v => '₹' + fmt(v / 1000) + 'k'

export default function Savings() {
  const { data, error, loading, reload } = useApi('/admin/savings')
  const [edit, setEdit] = useState(null)
  const [run, busy] = useAction()
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const b = data.baseline
  const months = data.months
  const latestYear = data.years[data.years.length - 1]

  async function saveVerified() {
    const r = await run(() => api(`/admin/savings/${edit.period}`, { method: 'PATCH', body: {
      verified_amount: edit.verified_amount === '' ? null : Number(edit.verified_amount), verified_note: edit.verified_note || null } }), 'Verified amount saved')
    if (r) { setEdit(null); reload(true) }
  }

  return (
    <div className="stack">
      <PageHeader title="Savings tracker" subtitle="How much less food money is being wasted compared with the baseline." />
      <Alert tone="warn" title="Estimated, not verified.">
        Estimated savings compare current waste cost with the baseline. They are not money in the bank. Enter a <b>verified</b> amount for a month only when it is backed by purchase records or invoices.
      </Alert>

      <Card title="Baseline" subtitle={b.description} actions={<Link className="btn sm" to="/admin/settings">Change baseline</Link>}>
        {b.cost_per_meal == null && b.daily_cost == null ? <Empty title="No baseline yet">Import historical waste records or set a manual baseline in Settings.</Empty> : (
          <div className="grid g-2" style={{ gap: 12 }}>
            <div className="formula">
              {b.cost_per_meal != null
                ? <>Baseline cost/meal = {inr(b.total_cost)} ÷ {fmt(b.meals_served)} meals served = <b>₹{b.cost_per_meal.toFixed(2)}</b></>
                : <>Baseline = ₹{fmt(b.daily_cost)} per operating day (manual)</>}
            </div>
            <div className="formula">
              {b.cost_per_meal != null
                ? <>Monthly estimated saving = (baseline ₹/meal × meals served) − actual waste cost</>
                : <>Monthly estimated saving = baseline/day × operating days − actual waste cost</>}
            </div>
          </div>
        )}
        <p className="tiny faint mt-8">Normalising by meals served means a quiet vacation month is not counted as a saving. Months never overlap, so yearly totals do not double-count.</p>
      </Card>

      <div className="grid g-4">
        <Kpi icon={Calculator} label={`Baseline cost ${latestYear ? latestYear.year : ''}`} value={inr(latestYear?.baseline_cost)} foot="What waste would have cost at the baseline rate" />
        <Kpi icon={Receipt} label="Actual waste cost" value={inr(latestYear?.actual_cost)} foot={`${latestYear?.months || 0} months recorded`} />
        <Kpi icon={TrendingDown} label="Estimated reduction" value={inr(latestYear?.estimated_saving)} foot={<><Badge tone="amber">Estimated</Badge>{latestYear?.baseline_cost ? `${fmt(latestYear.estimated_saving / latestYear.baseline_cost * 100, 1)}% below baseline` : ''}</>} />
        <Kpi icon={BadgeCheck} label="Verified savings" value={inr(data.total_verified)} foot={<Badge tone="green">Verified</Badge>} />
      </div>

      {!months.length ? <Card><Empty icon={PiggyBank} title="No months after the baseline period yet" /></Card> : (
        <>
          <div className="grid g-2">
            <Card title="Monthly waste cost vs baseline" actions={<Legend items={[{ label: 'Baseline', color: C.s2 }, { label: 'Actual', color: C.s1 }]} />}>
              <div className="chart-box">
                <ResponsiveContainer>
                  <BarChart data={months} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barGap={2}>
                    <CartesianGrid {...gridProps} />
                    <XAxis dataKey="label" {...axisProps} minTickGap={12} />
                    <YAxis {...yAxisProps} width={60} tickFormatter={k} />
                    <Tooltip cursor={barCursor} content={<Tip format={v => inr(v)} extra={r => <div className="tt-row"><span>Estimated saving</span><b>{inr(r.estimated_saving)}</b></div>} />} />
                    <Bar isAnimationActive={false} dataKey="baseline_cost" name="Baseline" fill={C.s2} radius={[4, 4, 0, 0]} maxBarSize={22} />
                    <Bar isAnimationActive={false} dataKey="actual_cost" name="Actual" fill={C.s1} radius={[4, 4, 0, 0]} maxBarSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Cumulative estimated savings" subtitle="Running total across months">
              <div className="chart-box">
                <ResponsiveContainer>
                  <LineChart data={months} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                    <CartesianGrid {...gridProps} />
                    <XAxis dataKey="label" {...axisProps} minTickGap={12} />
                    <YAxis {...yAxisProps} width={60} tickFormatter={k} />
                    <Tooltip cursor={cursor} content={<Tip format={v => inr(v)} />} />
                    <Line isAnimationActive={false} dataKey="cumulative_estimated" name="Cumulative (estimated)" stroke={C.s1} strokeWidth={2} dot={{ r: 3, fill: C.s1, strokeWidth: 0 }} activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card title="Annual summary">
            <table className="table" style={{ margin: '0 -20px -18px', width: 'calc(100% + 40px)' }}>
              <thead><tr><th>Year</th><th className="num">Months</th><th className="num">Baseline cost</th><th className="num">Actual cost</th><th className="num">Estimated saving</th><th className="num">Verified</th></tr></thead>
              <tbody>{data.years.map(y => (
                <tr key={y.year}><td className="strong">{y.year}</td><td className="num">{y.months}</td><td className="num">{inr(y.baseline_cost)}</td><td className="num">{inr(y.actual_cost)}</td><td className="num strong">{inr(y.estimated_saving)}</td><td className="num">{y.verified_amount ? inr(y.verified_amount) : '—'}</td></tr>
              ))}</tbody>
            </table>
          </Card>

          <Card title="Monthly ledger" subtitle="Add verified amounts once they are confirmed by finance">
            <div className="table-wrap" style={{ margin: '0 -20px -18px' }}>
              <table className="table">
                <thead><tr><th>Month</th><th className="num">Days</th><th className="num">Baseline</th><th className="num">Actual</th><th className="num">Estimated saving</th><th className="num">Verified</th><th></th></tr></thead>
                <tbody>{[...months].reverse().map(m => (
                  <tr key={m.period}>
                    <td className="strong nowrap">{m.label}</td><td className="num">{m.operating_days}</td><td className="num">{inr(m.baseline_cost)}</td><td className="num">{inr(m.actual_cost)}</td>
                    <td className="num"><span className="strong" style={{ color: m.estimated_saving < 0 ? 'var(--crit-text)' : undefined }}>{inr(m.estimated_saving)}</span> <Badge tone="amber">Est.</Badge></td>
                    <td className="num">{m.verified_amount != null ? <span title={m.verified_note || ''}>{inr(m.verified_amount)} <Badge tone="green">Verified</Badge></span> : <span className="faint">—</span>}</td>
                    <td className="right"><button className="btn sm ghost" onClick={() => setEdit({ period: m.period, label: m.label, verified_amount: m.verified_amount ?? '', verified_note: m.verified_note || '' })}>Verify</button></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      <Modal open={!!edit} title={`Verified savings · ${edit?.label}`} onClose={() => setEdit(null)}
        footer={<><button className="btn ghost" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary" onClick={saveVerified} disabled={busy}>Save</button></>}>
        {edit && (
          <div className="stack">
            <Field label="Verified amount (₹)" hint="Leave blank to clear. Use the reduction confirmed by procurement or invoices."><input className="input" type="number" value={edit.verified_amount} onChange={e => setEdit({ ...edit, verified_amount: e.target.value })} /></Field>
            <Field label="Evidence / note"><textarea className="textarea" value={edit.verified_note} onChange={e => setEdit({ ...edit, verified_note: e.target.value })} placeholder="e.g. Rice & dal purchase down 120 kg vs Nov 2025 (invoice #…)" /></Field>
          </div>
        )}
      </Modal>
    </div>
  )
}
