import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle2, Clock, MapPin, Package, ShieldCheck, XCircle } from 'lucide-react'
import { api, useApi } from '../api'
import { Leaf, MealImage } from '../components/Illustrations'
import { Alert, Badge, Field, Loading, Meter, Spinner, fmt, prettyTime } from '../components/ui'

const unitLabel = (q, u) => `${fmt(q, u === 'kg' ? 1 : 0)} ${u === 'kg' ? 'kg' : 'meal portions'}`

export default function DonationResponse() {
  const { token } = useParams()
  const { data, error, loading, setData, reload } = useApi(`/public/donations/${token}`)
  const [f, setF] = useState({ quantity: '', organisation: '', contact_name: '', contact_phone: '', pickup_eta: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')

  async function act(kind) {
    setBusy(true); setErr(null)
    try {
      const body = kind === 'accept' ? { ...f, quantity: Number(f.quantity) } : { reason: reason || null }
      setData(await api(`/public/donations/${token}/${kind}`, { method: 'POST', body }))
    } catch (e) { setErr(e.message); reload(true) } finally { setBusy(false) }
  }

  return (
    <div className="public-page">
      <div className="row" style={{ marginBottom: 20 }}><Leaf style={{ width: 34, height: 34 }} /><span className="logo">EcoByte</span><span className="small muted">Food Donation</span></div>
      <div className="public-card stack">
        {loading && !data ? <div className="card card-pad"><Loading rows={5} /></div> : error ? (
          <div className="card card-pad"><Alert tone="error" title="Link not valid.">{error}</Alert></div>
        ) : (() => {
          const d = data.donation
          const pct = d.quantity ? (d.quantity - d.remaining) / d.quantity * 100 : 0
          return <>
            <div className="card" style={{ overflow: 'hidden' }}>
              <MealImage src={d.image} meal="lunch" alt={d.food_name} className="food-thumb" />
              <div className="card-pad stack" style={{ gap: 12 }}>
                <div className="between"><span className="tiny faint strong">{d.code}</span>{d.accepting ? <Badge tone="green">Open for collection</Badge> : <Badge>Closed</Badge>}</div>
                <div><h1 style={{ fontSize: 22 }}>{d.food_name}</h1><div className="muted small">{d.category} · {d.is_veg ? 'Vegetarian' : 'Non-vegetarian'} · from {data.canteen_name}</div></div>
                <div className="card" style={{ padding: 14, background: 'var(--brand-50)', borderColor: 'var(--brand-200)' }}>
                  <div className="between"><span className="small muted">Still available</span><span className="strong" style={{ fontSize: 22, color: 'var(--brand-700)' }}>{unitLabel(d.remaining, d.unit)}</span></div>
                  <div className="mt-8"><Meter value={pct} max={100} /></div>
                  <div className="tiny faint mt-4">of {unitLabel(d.quantity, d.unit)} offered. Quantities claimed by other NGOs are already deducted.</div>
                </div>
                <div className="stack small" style={{ gap: 6 }}>
                  <div className="row"><MapPin size={15} className="green" /><b>Pickup:</b> {d.pickup_location}</div>
                  <div className="row"><Clock size={15} className="green" /><b>Collect before:</b> {prettyTime(d.pickup_deadline)}</div>
                  <div className="row"><ShieldCheck size={15} className="green" /><b>Safe to eat until:</b> {prettyTime(d.safe_until)} (prepared {prettyTime(d.prepared_at)})</div>
                  {d.instructions && <div className="row" style={{ alignItems: 'flex-start' }}><Package size={15} className="green" style={{ marginTop: 2 }} /><span>{d.instructions}</span></div>}
                </div>
              </div>
            </div>

            {err && <Alert tone="error">{err}</Alert>}
            {data.response === 'accepted' && data.my_allocation ? (
              <div className="card card-pad" style={{ textAlign: 'center' }}>
                <CheckCircle2 size={40} color="var(--brand-600)" />
                <h2 className="mt-8">Thank you, {data.my_allocation.organisation}!</h2>
                <p className="muted mt-4">You have reserved <b>{unitLabel(data.my_allocation.quantity, d.unit)}</b>. Please collect from {d.pickup_location} before {prettyTime(d.pickup_deadline)}. The canteen has been notified.</p>
              </div>
            ) : data.response === 'declined' ? (
              <div className="card card-pad" style={{ textAlign: 'center' }}><XCircle size={36} color="var(--text-3)" /><h2 className="mt-8">Response recorded</h2><p className="muted mt-4">Thanks for letting the canteen know.</p></div>
            ) : !d.accepting ? (
              <div className="card card-pad"><Alert tone="warn" title="This donation is closed.">It has been fully allocated, cancelled, or has passed its pickup deadline.</Alert></div>
            ) : declining ? (
              <div className="card card-pad stack">
                <h2>Decline this request</h2>
                <Field label="Reason (optional)"><input className="input" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. No vehicle available today" /></Field>
                <div className="row"><button className="btn" onClick={() => setDeclining(false)}>Back</button><button className="btn danger" disabled={busy} onClick={() => act('decline')}>Confirm decline</button></div>
              </div>
            ) : (
              <form className="card card-pad stack" onSubmit={e => { e.preventDefault(); act('accept') }}>
                <h2>{data.ngo ? `Accept for ${data.ngo}` : 'Accept this donation'}</h2>
                <div className="form-grid">
                  {!data.ngo && <Field label="Organisation name" className="span-all"><input className="input" value={f.organisation} onChange={e => setF({ ...f, organisation: e.target.value })} required minLength={2} /></Field>}
                  <Field label={`Quantity (${d.unit === 'kg' ? 'kg' : 'portions'})`} hint={`Up to ${fmt(d.remaining, d.unit === 'kg' ? 1 : 0)}`}>
                    <input className="input" type="number" min={d.unit === 'kg' ? 0.1 : 1} step={d.unit === 'kg' ? 0.1 : 1} max={d.remaining} value={f.quantity} onChange={e => setF({ ...f, quantity: e.target.value })} required /></Field>
                  <Field label="Expected pickup time"><input className="input" value={f.pickup_eta} onChange={e => setF({ ...f, pickup_eta: e.target.value })} placeholder="e.g. 2:30 PM" /></Field>
                  <Field label="Person collecting"><input className="input" value={f.contact_name} onChange={e => setF({ ...f, contact_name: e.target.value })} required minLength={2} /></Field>
                  <Field label="Phone"><input className="input" type="tel" value={f.contact_phone} onChange={e => setF({ ...f, contact_phone: e.target.value })} required placeholder="+91 …" /></Field>
                </div>
                <button type="button" className="btn ghost sm" style={{ alignSelf: 'flex-start' }} onClick={() => setF({ ...f, quantity: d.remaining })}>Take all remaining ({fmt(d.remaining)})</button>
                <div className="row">
                  <button className="btn primary lg" disabled={busy} style={{ flex: 1 }}>{busy ? <Spinner /> : 'Accept & reserve'}</button>
                  <button type="button" className="btn lg" onClick={() => setDeclining(true)}>Decline</button>
                </div>
                <p className="tiny faint">This link is for your organisation only and can be used once.</p>
              </form>
            )}
          </>
        })()}
      </div>
    </div>
  )
}
