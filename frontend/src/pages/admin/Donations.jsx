import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BadgeCheck, Check, Copy, Download, HandHeart, Link2, MessageCircle, MessageSquare, Package, Pencil, Plus, Send, ShieldCheck, Trash2, Truck, UserCheck, Users, X, Zap } from 'lucide-react'
import { MessageLog, SendResults, WhatsAppSetup, useWhatsApp } from './WhatsApp'
import { api, download, useApi } from '../../api'
import {
  Alert, Badge, Card, Empty, ErrorState, Field, Loading, Meter, Modal, PageHeader, PageLoading, Seg, Stat, Tabs, cap, fmt, prettyTime, toLocalInput, useAction, useToast,
} from '../../components/ui'

export const STATUS = {
  available: ['Available', 'green'], request_sent: ['Request Sent', 'blue'], partially_accepted: ['Partially Accepted', 'amber'],
  fully_accepted: ['Fully Accepted', 'green'], pickup_confirmed: ['Pickup Confirmed', 'purple'], collected: ['Collected', 'solid'],
  expired: ['Expired', 'red'], cancelled: ['Cancelled', ''], completed: ['Completed', 'solid'],
}
const ALLOC = { accepted: ['Accepted', 'green'], pickup_confirmed: ['Pickup confirmed', 'purple'], collected: ['Collected', 'solid'], cancelled: ['Cancelled', ''] }
const unit = (q, u) => `${fmt(q, u === 'kg' ? 1 : 0)} ${u === 'kg' ? 'kg' : 'meals'}`
export const StatusBadge = ({ s }) => <Badge tone={STATUS[s]?.[1]}>{STATUS[s]?.[0] || s}</Badge>

const MEAL_OPTS = [{ value: 'breakfast', label: 'Breakfast' }, { value: 'lunch', label: 'Lunch' }, { value: 'dinner', label: 'Dinner' }, { value: 'other', label: 'Other food' }]
const currentMeal = () => { const h = new Date().getHours(); return h < 11 ? 'breakfast' : h < 17 ? 'lunch' : 'dinner' }
const categoryFor = name => /rice|pulao|biryani|khichdi/i.test(name) ? 'Rice & grains'
  : /dal|curry|sambar|rajma|chole|paneer|kadhi|sabzi|bhaji|masala/i.test(name) ? 'Curry / dal'
    : /chapati|roti|paratha|puri|naan|bread|bhakri/i.test(name) ? 'Breads'
      : /poha|upma|samosa|idli|dosa|vada|sandwich|pakoda/i.test(name) ? 'Snacks'
        : /banana|apple|fruit/i.test(name) ? 'Fruits' : 'Cooked meal'

/** Dishes on today's published menu for one meal: main dish first, then its items. */
function menuDishes(meals, meal) {
  const out = []
  let veg = true
  for (const m of meals.filter(x => x.meal_type === meal)) {
    veg = veg && m.is_veg
    for (const n of [m.name, ...(m.items || '').split(/\n|,/)]) {
      const name = n.replace(/\s*\(\d+\)\s*/g, ' ').replace(/[\s.,;:\-–]+$/, '').replace(/^[\s.,;:\-–•*]+/, '').replace(/\s+/g, ' ').trim()
      if (name && !out.some(x => x.toLowerCase() === name.toLowerCase())) out.push(name)
    }
  }
  return { dishes: out, veg }
}

function CreateModal({ onClose, onCreated, pickup, quick }) {
  const now = new Date()
  const menu = useApi('/admin/meals', { date: toLocalInput(now).slice(0, 10) })
  const [meal, setMeal] = useState(currentMeal())
  const [picked, setPicked] = useState([])
  const [f, setF] = useState({ food_name: '', category: 'Cooked meal', is_veg: true, quantity: '', unit: 'portions', meal_type: currentMeal(),
    prepared_at: toLocalInput(new Date(now.getTime() - 30 * 60000)), safe_until: toLocalInput(new Date(now.getTime() + 4 * 3600000)),
    pickup_deadline: toLocalInput(new Date(now.getTime() + 2 * 3600000)), pickup_location: pickup || '', instructions: '', food_safety_confirmed: false })
  const [file, setFile] = useState(null)
  const [run, busy] = useAction()
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const { dishes, veg } = meal === 'other' ? { dishes: [], veg: true } : menuDishes(menu.data?.meals || [], meal)

  function choose(list, m = meal, isVeg = veg) {
    setPicked(list)
    setF(x => ({ ...x, food_name: list.join(', ').slice(0, 120), category: list.length ? categoryFor(list.join(' ')) : x.category,
      is_veg: isVeg, meal_type: m === 'other' ? '' : m }))
  }
  // When the meal changes (or the menu arrives), pre-select that meal's main dish.
  useEffect(() => {
    if (meal === 'other') { setPicked([]); setF(x => ({ ...x, food_name: '', meal_type: '' })); return }
    if (!menu.data) return
    const d = menuDishes(menu.data.meals, meal)
    choose(d.dishes.slice(0, 1), meal, d.veg)
  }, [meal, menu.data]) // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = d => choose(picked.includes(d) ? picked.filter(x => x !== d) : [...picked, d])

  async function submit() {
    const d = await run(async () => {
      const created = await api('/admin/donations', { method: 'POST', body: { ...f, quantity: Number(f.quantity), meal_type: f.meal_type || null } })
      if (file) { const fd = new FormData(); fd.append('file', file); await api(`/admin/donations/${created.id}/image`, { method: 'POST', body: fd }) }
      return created
    }, r => `Donation ${r.code} created`)
    if (d) onCreated(d)
  }
  return (
    <Modal open title={quick ? 'Quick Donate: record surplus food' : 'Create food donation request'} onClose={onClose} width={660}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || !f.food_safety_confirmed || !f.food_name.trim() || !f.quantity} onClick={submit}>Create request</button></>}>
      <div className="stack">
        <Field label="Surplus food is from">
          <Seg value={meal} onChange={setMeal} options={MEAL_OPTS} />
        </Field>
        {meal !== 'other' && (menu.loading && !menu.data ? <Loading rows={1} height={40} /> : dishes.length ? (
          <div className="stack" style={{ gap: 8 }}>
            <div className="small muted">Today's <b>{meal}</b> menu. Tap every dish that is left over:</div>
            <div className="dish-chips">{dishes.map(d => (
              <button type="button" key={d} className={`dish-chip ${picked.includes(d) ? 'on' : ''}`} onClick={() => toggle(d)} aria-pressed={picked.includes(d)}>
                {picked.includes(d) && <Check size={14} />}{d}
              </button>
            ))}</div>
          </div>
        ) : <Alert tone="warn">No {meal} menu is published for today. Type the food name below, or add the menu in Meal &amp; Menu.</Alert>)}
        <div className="form-grid">
          <Field label="Food name" className="span-all" hint={meal !== 'other' && dishes.length ? 'Filled from the menu. You can still edit it.' : undefined}>
            <input className="input" value={f.food_name} onChange={set('food_name')} placeholder="e.g. Vegetable Rice" autoFocus={meal === 'other'} /></Field>
          <Field label="Food category"><select className="select" value={f.category} onChange={set('category')}>{['Cooked meal', 'Rice & grains', 'Curry / dal', 'Breads', 'Snacks', 'Fruits', 'Packaged food', 'Other'].map(c => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Type"><select className="select" value={f.is_veg ? 'veg' : 'non'} onChange={e => setF({ ...f, is_veg: e.target.value === 'veg' })}><option value="veg">Vegetarian</option><option value="non">Non-vegetarian</option></select></Field>
          <Field label="Available quantity"><input className="input" type="number" min="0" step={f.unit === 'kg' ? '0.1' : '1'} value={f.quantity} onChange={set('quantity')} /></Field>
          <Field label="Unit"><select className="select" value={f.unit} onChange={set('unit')}><option value="portions">Meal portions</option><option value="kg">Kilograms</option></select></Field>
          {quick ? <div className="formula span-all">Prepared ~30 min ago · safe until {new Date(f.safe_until).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })} · collect by {new Date(f.pickup_deadline).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })} at {f.pickup_location || 'the canteen'}. <button type="button" className="btn sm ghost" onClick={onClose}>Need to change times? Use “Detailed request”.</button></div> : <>
          <Field label="Prepared at"><input className="input" type="datetime-local" value={f.prepared_at} onChange={set('prepared_at')} /></Field>
          <Field label="Safe to eat until" hint="Food freshness deadline"><input className="input" type="datetime-local" value={f.safe_until} onChange={set('safe_until')} /></Field>
          <Field label="Pickup deadline" hint="Must be before the safe-until time" className="span-all"><input className="input" type="datetime-local" value={f.pickup_deadline} onChange={set('pickup_deadline')} /></Field>
          <Field label="Pickup location" className="span-all"><input className="input" value={f.pickup_location} onChange={set('pickup_location')} /></Field>
          <Field label="Additional instructions" className="span-all"><textarea className="textarea" value={f.instructions} onChange={set('instructions')} placeholder="e.g. Bring your own containers; collect from the back gate." /></Field>
          <Field label="Food image (optional)" className="span-all"><input className="input" type="file" accept="image/png,image/jpeg,image/webp" style={{ paddingTop: 6 }} onChange={e => setFile(e.target.files[0] || null)} /></Field>
          </>}
        </div>
        <label className="check" style={{ padding: 12, borderRadius: 10, background: 'var(--brand-50)', border: '1px solid var(--brand-200)' }}>
          <input type="checkbox" checked={f.food_safety_confirmed} onChange={set('food_safety_confirmed')} />
          <span><b>Food safety confirmation.</b> This food was prepared and stored hygienically, has not been served from plates, and is safe to eat until the time above. Expired or unsafe food must never be donated.</span>
        </label>
        <p className="small muted" style={{ margin: 0 }}>The Donation ID (ECO-DON-YYYY-NNN) is generated automatically.</p>
      </div>
    </Modal>
  )
}

function ShareModal({ donation, ngos, wa, onClose, onShared }) {
  const active = ngos.filter(n => n.active)
  const [sel, setSel] = useState(active.map(n => n.id))
  const [generic, setGeneric] = useState(active.length === 0)
  const [links, setLinks] = useState(null)
  const [sent, setSent] = useState(null)
  const [run, busy] = useAction()
  const auto = wa?.ready
  const toast = useToast()
  async function generate() {
    const r = await run(() => api(`/admin/donations/${donation.id}/invites`, { method: 'POST', body: { ngo_ids: sel, generic, base_url: window.location.origin } }), 'Secure links ready')
    if (r) { setLinks(r.links); onShared() }
  }
  async function sendAuto() {
    const r = await run(() => api(`/admin/donations/${donation.id}/whatsapp`, { method: 'POST', body: { ngo_ids: sel, base_url: window.location.origin } }),
      x => x.failed ? `${x.sent} sent, ${x.failed} failed` : `WhatsApp sent to ${x.sent} NGO${x.sent === 1 ? '' : 's'}`)
    if (r) { setSent(r.results); onShared() }
  }
  const copy = async (text, what) => { try { await navigator.clipboard.writeText(text); toast(`${what} copied`) } catch { toast('Copy failed: select and copy manually', 'error') } }
  return (
    <Modal open title={`Send ${donation.code} to NGOs`} onClose={onClose} width={640}>
      {sent ? (
        <div className="stack">
          <SendResults results={sent} />
          <div className="small strong">Delivery status</div>
          <MessageLog donationId={donation.id} compact />
          <p className="tiny faint">Statuses update automatically (Twilio) or through the webhook (Meta). NGOs answer through the secure link in the message.</p>
        </div>
      ) : !links ? (
        <div className="stack">
          {!active.length ? <Alert tone="info">No NGO contacts saved yet. Add them in the “NGO contacts” tab, or create a shareable link below.</Alert> : (
            <div className="stack" style={{ gap: 8 }}>
              <div className="between"><span className="small strong">Registered NGOs</span><button className="btn sm ghost" onClick={() => setSel(sel.length === active.length ? [] : active.map(n => n.id))}>{sel.length === active.length ? 'Clear all' : 'Select all'}</button></div>
              {active.map(n => (
                <label key={n.id} className="check" style={{ padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 10 }}>
                  <input type="checkbox" checked={sel.includes(n.id)} onChange={e => setSel(e.target.checked ? [...sel, n.id] : sel.filter(x => x !== n.id))} />
                  <span><b>{n.name}</b> <span className="faint small">+{n.phone}{n.contact_person ? ` · ${n.contact_person}` : ''}</span></span>
                </label>
              ))}
            </div>
          )}
          <label className="check"><input type="checkbox" checked={generic} onChange={e => setGeneric(e.target.checked)} />Also create a shareable link (for NGOs not in the list; they enter their organisation name)</label>
          <Alert tone="info">Each NGO gets its own secure link. Opening it shows the live remaining quantity and lets them Accept or Decline, with no account or app needed. Two NGOs can never claim the same food.</Alert>
          {auto
            ? <Alert tone="success">Automatic WhatsApp is on ({wa.provider === 'meta' ? 'Meta Cloud API' : 'Twilio'}): the message goes straight to each selected NGO's WhatsApp.</Alert>
            : <Alert tone="info">Automatic sending is not set up, so WhatsApp opens a pre-filled chat for you to send. Set it up in the “WhatsApp setup” tab.</Alert>}
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            <button className={`btn ${auto ? '' : 'primary'}`} disabled={busy || (!sel.length && !generic)} onClick={generate}><Link2 />{auto ? 'Manual links instead' : 'Generate links'}</button>
            {auto && <button className="btn whatsapp" disabled={busy || !sel.length} onClick={sendAuto}><Send />{busy ? 'Sending…' : `Send automatically (${sel.length})`}</button>}
          </div>
        </div>
      ) : (
        <div className="stack">
          {links.map(l => (
            <div key={l.invite_id} className="card card-pad" style={{ padding: 14 }}>
              <div className="between wrap"><div><div className="strong">{l.ngo}</div><div className="tiny faint">{l.phone ? `+${l.phone}` : 'Share anywhere'} {l.response && <Badge tone={l.response === 'accepted' ? 'green' : ''}>{cap(l.response)}</Badge>}</div></div>
                <div className="row wrap">
                  <a className="btn sm whatsapp" href={l.whatsapp_url} target="_blank" rel="noreferrer"><MessageSquare />WhatsApp</a>
                  <a className="btn sm" href={l.sms_url}><Send />SMS</a>
                  <button className="btn sm" onClick={() => copy(l.link, 'Link')}><Link2 />Copy link</button>
                  <button className="btn sm ghost" onClick={() => copy(l.message, 'Message')}><Copy />Message</button>
                </div></div>
            </div>
          ))}
          <details><summary className="small strong" style={{ cursor: 'pointer' }}>Preview message</summary><pre className="formula" style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{links[0].message}</pre></details>
          <p className="tiny faint">WhatsApp opens a pre-filled chat; send it from your phone or WhatsApp Web. Acceptance is tracked through the secure link. For automatic sending with delivery status, set up the “WhatsApp setup” tab. If links show “localhost”, set the public address in Settings so NGOs can open them.</p>
        </div>
      )}
    </Modal>
  )
}

function AssignModal({ d, ngos, onClose, onDone }) {
  const active = ngos.filter(n => n.active)
  const [f, setF] = useState({ ngo_id: active[0]?.id || '', quantity: d.remaining, pickup_eta: '' })
  const [run, busy] = useAction()
  async function save() {
    const r = await run(() => api(`/admin/donations/${d.id}/assign`, { method: 'POST', body: { ngo_id: Number(f.ngo_id), quantity: Number(f.quantity), pickup_eta: f.pickup_eta || null } }),
      `Assigned ${f.quantity} ${d.unit === 'kg' ? 'kg' : 'portions'}`)
    if (r) { onDone(); onClose() }
  }
  return (
    <Modal open title={`Assign ${d.code} to an NGO`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy || !f.ngo_id || !(Number(f.quantity) > 0)} onClick={save}><UserCheck />Assign</button></>}>
      {!active.length ? <Alert tone="info">Add an NGO in the “NGO contacts” tab first.</Alert> : (
        <div className="form-grid">
          <Field label="NGO" className="span-all"><select className="select" value={f.ngo_id} onChange={e => setF({ ...f, ngo_id: e.target.value })}>{active.map(n => <option key={n.id} value={n.id}>{n.name} (+{n.phone})</option>)}</select></Field>
          <Field label={`Quantity (${d.unit === 'kg' ? 'kg' : 'portions'})`} hint={`Up to ${d.remaining} remaining`}><input className="input" type="number" min="0" max={d.remaining} value={f.quantity} onChange={e => setF({ ...f, quantity: e.target.value })} /></Field>
          <Field label="Expected pickup"><input className="input" value={f.pickup_eta} onChange={e => setF({ ...f, pickup_eta: e.target.value })} placeholder="e.g. 3:30 PM" /></Field>
          <p className="tiny faint span-all">Use this when an NGO confirms by phone. The same atomic check as NGO self-acceptance prevents over-allocation.</p>
        </div>
      )}
    </Modal>
  )
}

function DonationCard({ d, onShare, onChange, onAssign }) {
  const [run, busy] = useAction()
  const act = (a, status) => run(() => api(`/admin/allocations/${a.id}/status`, { method: 'POST', body: { status } }), `Marked ${status.replace('_', ' ')}`).then(r => r && onChange())
  return (
    <div className="card">
      <div className="card-head" style={{ alignItems: 'flex-start' }}>
        <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
          {d.image ? <img src={d.image} alt="" style={{ width: 64, height: 64, borderRadius: 12, objectFit: 'cover' }} /> : <div className="reward-icon" style={{ width: 56, height: 56 }}><Package /></div>}
          <div><div className="tiny faint strong">{d.code}</div><h2>{d.food_name}</h2>
            <div className="small muted">{d.category} · {d.is_veg ? 'Vegetarian' : 'Non-vegetarian'} · {d.pickup_location}</div></div>
        </div>
        <div className="row"><Badge tone="outline">{d.simple_status}</Badge><StatusBadge s={d.status} /></div>
      </div>
      <div className="card-body">
        <div className="progress-label"><span><b>{unit(d.allocated, d.unit)}</b> accepted of {unit(d.quantity, d.unit)}</span><span className="strong green">{unit(d.remaining, d.unit)} remaining</span></div>
        <Meter value={d.allocated} max={d.quantity} progress />
        <div className="row wrap small muted mt-12" style={{ gap: 16 }}>
          <span>Prepared {prettyTime(d.prepared_at)}</span><span>Pickup by <b>{prettyTime(d.pickup_deadline)}</b></span><span>Safe until {prettyTime(d.safe_until)}</span>
          <span>{d.invites_sent} link(s) sent · {d.responses} response(s)</span>
        </div>
        {d.allocations.length > 0 && (
          <div className="table-wrap mt-12" style={{ border: '1px solid var(--border)', borderRadius: 10 }}>
            <table className="table compact">
              <thead><tr><th>NGO</th><th>Contact</th><th className="num">Accepted</th><th>Status</th><th></th></tr></thead>
              <tbody>{d.allocations.map(a => (
                <tr key={a.id}>
                  <td className="strong">{a.organisation}<div className="tiny faint">{prettyTime(a.created_at)}{a.pickup_eta ? ` · ETA ${a.pickup_eta}` : ''}</div></td>
                  <td className="small">{a.contact_name}<div className="tiny faint">+{a.contact_phone}</div></td>
                  <td className="num strong">{unit(a.quantity, d.unit)}</td>
                  <td><Badge tone={ALLOC[a.status][1]}>{ALLOC[a.status][0]}</Badge></td>
                  <td className="right nowrap">
                    {a.status === 'accepted' && <button className="btn sm" disabled={busy} onClick={() => act(a, 'pickup_confirmed')}><Check />Pickup confirmed</button>}
                    {['accepted', 'pickup_confirmed'].includes(a.status) && <button className="btn sm soft" disabled={busy} onClick={() => act(a, 'collected')}><Truck />Collected</button>}
                    {['accepted', 'pickup_confirmed'].includes(a.status) && <button className="btn sm ghost danger" disabled={busy} title="Release this quantity back to other NGOs" onClick={() => window.confirm(`Cancel ${a.organisation}'s allocation and release ${unit(a.quantity, d.unit)}?`) && act(a, 'cancelled')}><X /></button>}
                  </td>
                </tr>
              ))}
              {d.remaining > 0 && d.allocations.length > 0 && <tr><td className="muted">Remaining</td><td /><td className="num">{unit(d.remaining, d.unit)}</td><td colSpan={2}>{d.accepting ? <Badge tone="blue">Open</Badge> : <Badge>Closed</Badge>}</td></tr>}
              {d.remaining <= 0 && <tr><td className="muted">Remaining</td><td /><td className="num">0</td><td colSpan={2}><Badge tone="green">Fully allocated</Badge></td></tr>}
              </tbody>
            </table>
          </div>
        )}
        {d.instructions && <p className="small muted mt-12">Instructions: {d.instructions}</p>}
        <div className="row wrap mt-16">
          {d.accepting && <button className="btn whatsapp" onClick={() => onShare(d)}><MessageSquare />Send to NGOs via WhatsApp</button>}
          {d.accepting && <button className="btn" onClick={() => onAssign(d)}><UserCheck />Assign to NGO</button>}
          {d.status === 'collected' && <button className="btn primary" disabled={busy} onClick={() => run(() => api(`/admin/donations/${d.id}/complete`, { method: 'POST' }), 'Donation completed').then(r => r && onChange())}><BadgeCheck />Mark completed</button>}
          {!['collected', 'cancelled'].includes(d.status) && <button className="btn ghost danger" disabled={busy} onClick={() => window.confirm(`Cancel ${d.code}? NGOs will no longer be able to accept it.`) && run(() => api(`/admin/donations/${d.id}/cancel`, { method: 'POST' }), 'Donation cancelled').then(r => r && onChange())}>Cancel donation</button>}
        </div>
      </div>
    </div>
  )
}

function NgoContacts({ ngos, reload, wa }) {
  const [form, setForm] = useState(null)
  const [run, busy] = useAction()
  const toast = useToast()
  async function remove(n) {
    if (!window.confirm(`Remove ${n.name} (+${n.phone})?\n\nLinks already sent to this NGO that it has not answered will stop working. Past donations keep its name.`)) return
    const r = await run(() => api(`/admin/ngos/${n.id}`, { method: 'DELETE' }), x => `${x.deleted} removed${x.links_revoked ? ` · ${x.links_revoked} open link(s) revoked` : ''}`)
    if (r) reload()
  }
  async function test(n) {
    const r = await run(() => api('/admin/whatsapp/test', { method: 'POST', body: { phone: n.phone, mode: wa?.provider === 'meta' ? 'hello_world' : 'text' } }))
    if (r) toast(r.status === 'failed' ? `Not sent to ${n.name}: ${r.error}` : `Test WhatsApp sent to ${n.name}. Check the phone and the message log.`, r.status === 'failed' ? 'error' : undefined)
  }
  async function save() {
    const body = { name: form.name, contact_person: form.contact_person || null, phone: form.phone, email: form.email || null, address: form.address || null, active: form.active }
    const r = form.id ? await run(() => api(`/admin/ngos/${form.id}`, { method: 'PATCH', body }), 'NGO updated') : await run(() => api('/admin/ngos', { method: 'POST', body }), 'NGO added')
    if (r) { setForm(null); reload() }
  }
  return (
    <Card viewAll title="Registered NGO contacts" subtitle="Requests are sent to these numbers on WhatsApp or SMS. NGOs never need an account."
      actions={<button className="btn primary sm" onClick={() => setForm({ name: '', contact_person: '', phone: '', email: '', address: '', active: true })}><Plus />Add NGO</button>}>
      {!ngos.length ? <Empty icon={Users} title="No NGOs yet">Add the NGOs you work with, including their WhatsApp numbers.</Empty> : (
        <div className="table-wrap flush">
          <table className="table">
            <thead><tr><th>NGO</th><th>Contact person</th><th>WhatsApp / phone</th><th>Address</th><th>Status</th><th></th></tr></thead>
            <tbody>{ngos.map(n => (
              <tr key={n.id}><td className="strong">{n.name}</td><td>{n.contact_person || '—'}</td><td>+{n.phone}</td><td className="small muted">{n.address || '—'}</td>
                <td>{n.active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}</td>
                <td className="right nowrap">
                  {wa?.ready && <button className="btn sm ghost" disabled={busy || !n.active} title="Send a test WhatsApp to this number" onClick={() => test(n)}><MessageCircle size={14} />Test</button>}
                  <button className="btn sm ghost" onClick={() => setForm({ ...n })}><Pencil size={14} />Edit</button>
                  <button className="btn sm ghost danger" disabled={busy} onClick={() => remove(n)}><Trash2 size={14} />Remove</button></td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Modal open={!!form} title={form?.id ? 'Edit NGO' : 'Add NGO'} onClose={() => setForm(null)}
        footer={<><button className="btn ghost" onClick={() => setForm(null)}>Cancel</button><button className="btn primary" disabled={busy || !form?.name || !form?.phone} onClick={save}>Save</button></>}>
        {form && <div className="form-grid">
          <Field label="NGO name" className="span-all"><input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Contact person"><input className="input" value={form.contact_person || ''} onChange={e => setForm({ ...form, contact_person: e.target.value })} /></Field>
          <Field label="WhatsApp number" hint="With country code, e.g. +91 98765 43210"><input className="input" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></Field>
          <Field label="Email"><input className="input" type="email" value={form.email || ''} onChange={e => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Address"><input className="input" value={form.address || ''} onChange={e => setForm({ ...form, address: e.target.value })} /></Field>
          <label className="check span-all"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} />Active (include in donation requests)</label>
        </div>}
      </Modal>
    </Card>
  )
}

export default function Donations() {
  const [params, setParams] = useSearchParams()
  const { data, error, loading, reload } = useApi('/admin/donations')
  const ngos = useApi('/admin/ngos')
  const settings = useApi('/admin/settings')
  const wa = useWhatsApp()
  const toast = useToast()
  const [tab, setTab] = useState(() => new URLSearchParams(window.location.search).get('tab') || 'active')
  const [creating, setCreating] = useState(false)
  const [share, setShare] = useState(null)
  const [assign, setAssign] = useState(null)
  const [run, busy] = useAction()
  useEffect(() => { if (params.get('new')) { setCreating(true); setParams({}, { replace: true }) } }, [params, setParams])
  if (loading && !data) return <PageLoading />
  if (error) return <ErrorState error={error} onRetry={reload} />
  const active = data.filter(d => !['collected', 'expired', 'cancelled'].includes(d.status))
  const open = active.filter(d => d.accepting)
  const daily = Object.values(data.reduce((acc, d) => {
    const k = d.created_at.slice(0, 10)
    const x = acc[k] || (acc[k] = { date: k, count: 0, portions: 0, kg: 0, collected: 0 })
    x.count++; if (d.unit === 'kg') x.kg += d.quantity; else x.portions += d.quantity
    x.collected += d.collected
    return acc
  }, {}))

  return (
    <div className="stack">
      <PageHeader title="NGO Food Donation" subtitle="Donate safe surplus food instead of wasting it. NGOs respond through a secure link, with no login needed."
        actions={<><button className="btn" onClick={() => setCreating(true)}><Plus />Detailed request</button>
          <button className="btn primary lg" onClick={() => setCreating('quick')}><Zap />Quick Donate</button></>} />
      <div className="grid g-4">
        <Stat tone="green" icon={HandHeart} label="Active donations" value={fmt(active.length)} />
        <Stat tone="blue" icon={Package} label="Portions still available" value={fmt(open.filter(d => d.unit === 'portions').reduce((a, d) => a + d.remaining, 0))} />
        <Stat tone="orange" icon={Check} label="Accepted by NGOs" value={fmt(data.filter(d => d.unit === 'portions').reduce((a, d) => a + d.allocated, 0))} unit="meals" />
        <Stat tone="purple" icon={Truck} label="Collected" value={fmt(data.filter(d => d.unit === 'portions').reduce((a, d) => a + d.collected, 0))} unit="meals" />
      </div>
      <Tabs value={tab} onChange={setTab} options={[{ value: 'active', label: `Active (${active.length})` }, { value: 'history', label: 'Donation history' }, { value: 'ngos', label: `NGO contacts (${ngos.data?.length ?? 0})` }, { value: 'whatsapp', label: wa.data?.ready ? 'WhatsApp ✓' : 'WhatsApp setup' }]} />
      {tab === 'active' && (!active.length ? <Card><Empty icon={HandHeart} title="No active donations">When leftover food is safe to donate, create a request and send it to NGOs.</Empty></Card>
        : <div className="stack">{active.map(d => <DonationCard key={d.id} d={d} onShare={setShare} onAssign={setAssign} onChange={() => reload(true)} />)}</div>)}
      {tab === 'history' && (
        <Card viewAll title="Donation history" actions={<button className="btn sm" disabled={busy} onClick={() => run(() => download('/admin/reports/donations', {}, 'EcoByte_Donations.xlsx'), 'Downloaded')}><Download />Export</button>}>
          {!data.length ? <Empty title="No donations yet" /> : (<>
            <div className="row wrap" style={{ gap: 10, marginBottom: 14 }}>{daily.slice(0, 7).map(x => (
              <div key={x.date} className="card" style={{ padding: '10px 14px', boxShadow: 'none' }}>
                <div className="tiny faint strong">{prettyTime(x.date + 'T00:00').split(',')[0]}</div>
                <div className="small"><b>{x.count}</b> donation{x.count > 1 ? 's' : ''} · {fmt(x.portions)} portions{x.kg ? ` · ${fmt(x.kg, 1)} kg` : ''}</div>
                <div className="tiny faint">{fmt(x.collected)} collected</div>
              </div>))}</div>
            <div className="table-wrap flush">
              <table className="table">
                <thead><tr><th>Donation ID</th><th>Food</th><th className="num">Total</th><th className="num">Accepted</th><th className="num">Collected</th><th>NGOs</th><th>Requested</th><th>Pickup deadline</th><th>Status</th></tr></thead>
                <tbody>{data.map(d => (
                  <tr key={d.id}><td className="strong nowrap">{d.code}</td><td>{d.food_name}</td><td className="num">{unit(d.quantity, d.unit)}</td><td className="num">{fmt(d.allocated)}</td><td className="num">{fmt(d.collected)}</td>
                    <td className="small">{d.allocations.filter(a => a.status !== 'cancelled').map(a => a.organisation).join(', ') || '—'}</td>
                    <td className="small muted nowrap">{prettyTime(d.created_at)}</td><td className="small muted nowrap">{prettyTime(d.pickup_deadline)}</td><td><StatusBadge s={d.status} /></td></tr>
                ))}</tbody>
              </table>
            </div>
          </>)}
        </Card>
      )}
      {tab === 'ngos' && (ngos.loading && !ngos.data ? <Loading /> : <NgoContacts ngos={ngos.data || []} wa={wa.data} reload={() => ngos.reload(true)} />)}
      {tab === 'whatsapp' && <WhatsAppSetup onChange={() => wa.reload(true)} />}
      <Alert tone="info">Only list food that was handled safely and is within its safe consumption time. EcoByte blocks expired food and closes acceptance automatically at the pickup deadline.</Alert>
      {creating && <CreateModal quick={creating === 'quick'} pickup={settings.data?.pickup_location} onClose={() => setCreating(false)} onCreated={d => {
        setCreating(false); reload(true)
        if (d.whatsapp_auto) { toast(`Sending ${d.code} to ${d.whatsapp_auto} NGO${d.whatsapp_auto === 1 ? '' : 's'} on WhatsApp automatically`); setTimeout(() => reload(true), 4000) } else setShare(d)
      }} />}
      {assign && <AssignModal d={assign} ngos={ngos.data || []} onClose={() => setAssign(null)} onDone={() => reload(true)} />}
      {share && <ShareModal donation={share} ngos={ngos.data || []} wa={wa.data} onClose={() => setShare(null)} onShared={() => reload(true)} />}
    </div>
  )
}
