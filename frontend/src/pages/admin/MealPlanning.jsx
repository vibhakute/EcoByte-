import { useRef, useState } from 'react'
import { Copy, Eye, EyeOff, ImagePlus, Pencil, Plus, Send, Trash } from 'lucide-react'
import { api, useApi } from '../../api'
import { MealImage } from '../../components/Illustrations'
import {
  Badge, Card, Empty, ErrorState, Field, Modal, PageHeader, PageLoading, addDays, cap, fmt, inr, prettyDate, todayIso, useAction,
} from '../../components/ui'
import { MEAL_ICON, PrepModal } from './Overview'

const MEALS = ['breakfast', 'lunch', 'dinner']
const blank = (meal_type, date) => ({ date, meal_type, name: '', items: '', description: '', is_veg: true, price: '', quantity_available: '', prep_cost: '', available: true, published: true })

function MealForm({ form, setForm, onSave, onClose, busy }) {
  const set = k => e => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const fileRef = useRef()
  return (
    <Modal open title={form.id ? 'Edit meal' : `Add ${form.meal_type} meal`} onClose={onClose} width={600}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || form.name.length < 2} onClick={() => onSave(fileRef.current?.files?.[0])}>{form.id ? 'Save changes' : 'Add meal'}</button></>}>
      <div className="form-grid">
        <Field label="Meal name" className="span-all"><input className="input" value={form.name} onChange={set('name')} placeholder="e.g. Veg Biryani with Raita" autoFocus /></Field>
        <Field label="Meal category"><select className="select" value={form.meal_type} onChange={set('meal_type')}>{MEALS.map(m => <option key={m} value={m}>{cap(m)}</option>)}</select></Field>
        <Field label="Date" hint="Schedule for a future date if needed"><input className="input" type="date" min={todayIso()} value={form.date} onChange={set('date')} /></Field>
        <Field label="Food items" hint="One per line" className="span-all"><textarea className="textarea" value={form.items} onChange={set('items')} placeholder={'Chapati\nDal Rice\nSalad'} /></Field>
        <Field label="Description" className="span-all"><textarea className="textarea" style={{ minHeight: 56 }} value={form.description} onChange={set('description')} placeholder="Short description shown to students" /></Field>
        <Field label="Meal price (₹)" hint="Leave 0 if included in the mess plan"><input className="input" type="number" min="0" value={form.price} onChange={set('price')} /></Field>
        <Field label="Available quantity" hint="Meals available (optional)"><input className="input" type="number" min="0" value={form.quantity_available ?? ''} onChange={set('quantity_available')} /></Field>
        <Field label="Estimated preparation cost (₹)" hint="Total for this meal (optional)"><input className="input" type="number" min="0" value={form.prep_cost ?? ''} onChange={set('prep_cost')} /></Field>
        <Field label="Menu image (optional)" hint="JPG, PNG or WEBP, max 4 MB"><input ref={fileRef} className="input" type="file" accept="image/png,image/jpeg,image/webp" style={{ paddingTop: 6 }} /></Field>
        <label className="check"><input type="checkbox" checked={form.is_veg} onChange={set('is_veg')} />Vegetarian</label>
        <label className="check"><input type="checkbox" checked={form.available} onChange={set('available')} />Available</label>
        <label className="check span-all"><input type="checkbox" checked={form.published} onChange={set('published')} />Publish now (visible to students immediately)</label>
      </div>
    </Modal>
  )
}

export default function MealPlanning() {
  const [date, setDate] = useState(todayIso())
  const { data, error, loading, reload } = useApi('/admin/meals', { date })
  const week = useApi('/admin/forecast', { days: 7 })
  const [form, setForm] = useState(null)
  const [prep, setPrep] = useState(null)
  const [copyFrom, setCopyFrom] = useState(null)
  const [run, busy] = useAction()
  const days = Array.from({ length: 7 }, (_, i) => addDays(todayIso(), i))
  const refresh = () => { reload(true); week.reload(true) }

  async function save(file) {
    const body = { ...form, price: Number(form.price || 0), quantity_available: form.quantity_available === '' || form.quantity_available == null ? null : Number(form.quantity_available),
      prep_cost: form.prep_cost === '' || form.prep_cost == null ? null : Number(form.prep_cost) }
    const r = await run(async () => {
      const { id, image, ...rest } = body
      const saved = id ? await api(`/admin/meals/${id}`, { method: 'PATCH', body: rest }) : await api('/admin/meals', { method: 'POST', body: rest })
      if (file) { const fd = new FormData(); fd.append('file', file); await api(`/admin/meals/${saved.id}/image`, { method: 'POST', body: fd }) }
      return saved
    }, form.id ? 'Meal updated' : (body.published ? 'Meal added and published to students' : 'Meal saved as draft'))
    if (r) { setForm(null); refresh() }
  }
  const patch = async (m, body, msg) => { if (await run(() => api(`/admin/meals/${m.id}`, { method: 'PATCH', body }), msg)) refresh() }
  const remove = async m => { if (window.confirm(`Delete ${m.name}?`) && await run(() => api(`/admin/meals/${m.id}`, { method: 'DELETE' }), 'Meal deleted')) refresh() }
  const publishAll = async () => { if (await run(() => api('/admin/meals/publish', { method: 'POST', body: { date, published: true } }), r => `Published ${r.updated} meal(s) to students`)) refresh() }
  const copy = async () => { if (await run(() => api('/admin/meals/copy', { method: 'POST', body: { from_date: copyFrom, to_date: date } }), r => `Copied ${r.copied} meal(s) as drafts`)) { setCopyFrom(null); refresh() } }

  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const drafts = data.meals.filter(m => !m.published).length

  return (
    <div className="stack">
      <PageHeader title="Meal Planning" subtitle="Plan breakfast, lunch and dinner. Published meals appear in the student menu instantly."
        actions={<>
          <button className="btn" onClick={() => setCopyFrom(addDays(date, -7))}><Copy />Copy from…</button>
          {drafts > 0 && <button className="btn primary" disabled={busy} onClick={publishAll}><Send />Publish {drafts} draft{drafts > 1 ? 's' : ''}</button>}
        </>} />
      <div className="row wrap">
        {days.map((d, i) => <button key={d} className={`btn sm ${d === date ? 'primary' : ''}`} onClick={() => setDate(d)}>{i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : prettyDate(d, { weekday: 'short', day: 'numeric' })}</button>)}
        <input type="date" className="input sm" style={{ width: 160 }} value={date} onChange={e => e.target.value && setDate(e.target.value)} />
      </div>

      <div className="grid g-3">
        {MEALS.map(meal => {
          const f = data.forecast.find(x => x.meal_type === meal)
          const list = data.meals.filter(m => m.meal_type === meal)
          const Icon = MEAL_ICON[meal]
          return (
            <div key={meal} className={`meal-col ${meal}`}>
              <div className="meal-col-head">
                <div className="mi"><Icon /></div>
                <div style={{ flex: 1 }}><h3>{meal}</h3><div className="tiny muted">{f.closed ? `Closed · ${f.closed_reason}` : `${f.confirmed} confirmed · predicted ${f.predicted}`}</div></div>
                <button className="btn sm primary" onClick={() => setForm(blank(meal, date))}><Plus />Add Meal</button>
              </div>
              {!f.closed && (
                <div className="meal-rows" style={{ background: 'var(--surface-2)' }}>
                  <div className="r"><span>Predicted demand</span><b>{fmt(f.predicted)}</b></div>
                  <div className="r"><span>Recommended ({f.buffer_pct}% buffer)</span><b className="green">{fmt(f.recommended)} meals</b></div>
                  <div className="r"><span>Preparation quantity set</span>
                    <b>{f.prepared != null ? fmt(f.prepared) : '—'} <button className="btn sm ghost" style={{ height: 24 }} onClick={() => setPrep(f)}><Pencil size={13} />Set</button></b></div>
                </div>
              )}
              <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {!list.length ? <Empty title="No meal planned">Add a {meal} meal for {prettyDate(date)}.</Empty> : list.map(m => (
                  <div key={m.id} className="card" style={{ overflow: 'hidden' }}>
                    <MealImage src={m.image} meal={meal} alt={m.name} className="food-thumb" />
                    <div style={{ padding: 12 }}>
                      <div className="between" style={{ alignItems: 'flex-start' }}>
                        <div style={{ minWidth: 0 }}>
                          <div className="row"><span className={`veg ${m.is_veg ? '' : 'non'}`} /><span className={`strong ${m.available ? '' : 'strike'}`}>{m.name}</span></div>
                          {m.items && <div className="small muted mt-4">{m.items.split('\n').filter(Boolean).join(' · ')}</div>}
                        </div>
                        {m.published ? <Badge tone="green">Published</Badge> : <Badge tone="amber">Draft</Badge>}
                      </div>
                      <div className="row wrap small muted mt-8" style={{ gap: 12 }}>
                        <span>Price {m.price ? `₹${m.price}` : 'incl.'}</span>
                        {m.quantity_available != null && <span>Qty {fmt(m.quantity_available)}</span>}
                        {m.prep_cost != null && <span>Cost {inr(m.prep_cost)}</span>}
                        {!m.available && <Badge tone="red">Sold out</Badge>}
                      </div>
                      <div className="row wrap mt-12" style={{ gap: 6 }}>
                        <button className="btn sm" onClick={() => setForm({ ...m })}><Pencil />Edit</button>
                        <button className="btn sm" onClick={() => patch(m, { published: !m.published }, m.published ? 'Hidden from students' : 'Published to students')}>{m.published ? <><EyeOff />Unpublish</> : <><Eye />Publish</>}</button>
                        <button className="btn sm" onClick={() => patch(m, { available: !m.available }, m.available ? 'Marked sold out' : 'Marked available')}>{m.available ? 'Sold out' : 'Available'}</button>
                        <button className="btn sm ghost icon-btn danger" aria-label={`Delete ${m.name}`} onClick={() => remove(m)}><Trash /></button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <Card title="Next 7 days: demand forecast" subtitle="Live from student confirmations. Set preparation quantities as confirmations come in.">
        {week.loading && !week.data ? <div className="skeleton" style={{ height: 200 }} /> : (
          <div className="table-wrap flush">
            <table className="table">
              <thead><tr><th>Date</th><th>Main dishes</th>{MEALS.map(m => <th key={m} className="num">{cap(m)}<div className="tiny faint" style={{ fontWeight: 400 }}>confirmed → prepare</div></th>)}<th className="num">Total to prepare</th></tr></thead>
              <tbody>{week.data.days.map(d => (
                <tr key={d.date} style={{ cursor: 'pointer' }} onClick={() => setDate(d.date)}>
                  <td className="nowrap strong">{prettyDate(d.date)}{d.event && <div className="tiny faint">{d.event}</div>}</td>
                  <td className="small muted">{d.closed ? 'Closed' : d.meals.map(m => m.main_dish).filter(Boolean).join(' · ') || 'Not planned'}</td>
                  {d.meals.map(m => <td key={m.meal_type} className="num nowrap">{m.closed ? '—' : <>{m.confirmed} → <b>{m.recommended}</b></>}</td>)}
                  <td className="num strong">{d.closed ? '—' : fmt(d.recommended)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      {form && <MealForm form={form} setForm={setForm} onSave={save} onClose={() => setForm(null)} busy={busy} />}
      {prep && <PrepModal item={prep} onClose={() => setPrep(null)} onSaved={refresh} />}
      <Modal open={!!copyFrom} title="Copy meals" onClose={() => setCopyFrom(null)}
        footer={<><button className="btn ghost" onClick={() => setCopyFrom(null)}>Cancel</button><button className="btn primary" onClick={copy} disabled={busy}>Copy to {prettyDate(date)}</button></>}>
        <Field label="Copy all meals from" hint="Copies arrive as drafts so you can review them before publishing."><input type="date" className="input" value={copyFrom || ''} onChange={e => setCopyFrom(e.target.value)} /></Field>
      </Modal>
    </div>
  )
}
