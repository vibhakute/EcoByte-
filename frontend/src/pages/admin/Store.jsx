import { useEffect, useRef, useState } from 'react'
import { ChefHat, Package, Pencil, Plus, ShoppingBag, Trash, Wallet, X } from 'lucide-react'
import { api, useApi } from '../../api'
import { ProductImage } from '../../components/Illustrations'
import { Badge, Card, Empty, ErrorState, Field, Loading, Modal, PageHeader, Stat, Tabs, cap, fmt, inr, prettyTime, useAction, ViewAll } from '../../components/ui'

export const ORDER_TONE = { placed: 'amber', accepted: 'blue', preparing: 'purple', ready: 'green', completed: 'solid', cancelled: '' }
const NEXT_LABEL = { accepted: 'Accept', preparing: 'Start preparing', ready: 'Mark ready', completed: 'Mark collected' }

function Orders() {
  const [status, setStatus] = useState('active')
  const { data, error, loading, reload } = useApi('/admin/orders', { status: status === 'all' ? '' : status })
  const [run, busy] = useAction()
  useEffect(() => { const t = setInterval(() => reload(true), 15000); return () => clearInterval(t) }, [reload])
  const move = async (o, s) => {
    if (s === 'cancelled' && !window.confirm(`Cancel order ${o.code}? The student will be notified.`)) return
    if (await run(() => api(`/admin/orders/${o.id}/status`, { method: 'POST', body: { status: s } }), `${o.code}: ${s}`)) reload(true)
  }
  return (
    <div className="stack">
      <div className="grid g-3">
        <Stat tone="orange" icon={ShoppingBag} label="Open orders" value={fmt(data?.items.filter(o => !['completed', 'cancelled'].includes(o.status)).length)} loading={!data} />
        <Stat tone="green" icon={ChefHat} label="Ready for pickup" value={fmt(data?.items.filter(o => o.status === 'ready').length)} loading={!data} />
        <Stat tone="blue" icon={Wallet} label="Sales completed today" value={inr(data?.sales_today)} loading={!data} foot="Paid at the counter" />
      </div>
      <Tabs value={status} onChange={setStatus} options={[{ value: 'active', label: 'Active queue' }, { value: 'completed', label: 'Completed' }, { value: 'cancelled', label: 'Cancelled' }, { value: 'all', label: 'All' }]} />
      {error ? <ErrorState error={error} onRetry={reload} /> : loading && !data ? <Loading rows={4} height={60} /> : !data.items.length ? (
        <Card><Empty icon={ShoppingBag} title="No orders here">New student orders appear automatically.</Empty></Card>
      ) : (
        <ViewAll limit={6} noun="orders"><div className="grid g-3" data-viewall>{data.items.map(o => (
          <div key={o.id} className="card card-pad stack" style={{ gap: 10 }}>
            <div className="between"><div><div className="strong">{o.code}</div><div className="tiny faint">{o.student?.name} · {o.student?.student_code}</div></div><Badge tone={ORDER_TONE[o.status]}>{o.status_label}</Badge></div>
            <div className="list">{o.items.map((i, k) => <div key={k} className="between small" style={{ padding: '4px 0' }}><span>{i.quantity} × {i.name}</span><span>{inr(i.line_total)}</span></div>)}</div>
            {o.note && <div className="small muted">Note: {o.note}</div>}
            <div className="between"><span className="tiny faint">{prettyTime(o.created_at)}</span><b>{inr(o.total)}</b></div>
            {o.next.length > 0 && <div className="row wrap">
              {o.next.filter(n => n !== 'cancelled').map(n => <button key={n} className="btn sm primary" disabled={busy} onClick={() => move(o, n)}>{NEXT_LABEL[n]}</button>)}
              <button className="btn sm ghost danger" disabled={busy} onClick={() => move(o, 'cancelled')}><X />Cancel</button>
            </div>}
          </div>
        ))}</div></ViewAll>
      )}
    </div>
  )
}

function Products() {
  const { data, error, loading, reload } = useApi('/admin/products')
  const [form, setForm] = useState(null)
  const [run, busy] = useAction()
  const file = useRef()
  async function save() {
    const body = { name: form.name, description: form.description, category: form.category, price: Number(form.price), available: form.available, is_veg: form.is_veg }
    const r = await run(async () => {
      const p = form.id ? await api(`/admin/products/${form.id}`, { method: 'PUT', body }) : await api('/admin/products', { method: 'POST', body })
      const f = file.current?.files?.[0]
      if (f) { const fd = new FormData(); fd.append('file', f); await api(`/admin/products/${p.id}/image`, { method: 'POST', body: fd }) }
      return p
    }, form.id ? 'Item updated' : 'Item added')
    if (r) { setForm(null); reload(true) }
  }
  const toggle = async p => { if (await run(() => api(`/admin/products/${p.id}`, { method: 'PUT', body: { ...p, available: !p.available } }), p.available ? `${p.name} marked unavailable` : `${p.name} available`)) reload(true) }
  const remove = async p => { if (window.confirm(`Delete ${p.name}?`) && await run(() => api(`/admin/products/${p.id}`, { method: 'DELETE' }), 'Item deleted')) reload(true) }
  if (loading && !data) return <Loading rows={6} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'flex-end' }}><button className="btn primary" onClick={() => setForm({ name: '', description: '', category: 'snack', price: '', available: true, is_veg: true })}><Plus />Add item</button></div>
      {!data.length ? <Card><Empty icon={Package} title="No items yet" /></Card> : (
        <div className="grid g-4">{data.map(p => (
          <div key={p.id} className="card" style={{ overflow: 'hidden', opacity: p.available ? 1 : .65 }}>
            <ProductImage src={p.image} category={p.category} name={p.name} />
            <div className="card-pad stack" style={{ gap: 6, padding: 14 }}>
              <div className="between"><b>{p.name}</b><b>{inr(p.price)}</b></div>
              <div className="small muted" style={{ minHeight: 36 }}>{p.description}</div>
              <div className="row wrap"><Badge>{cap(p.category)}</Badge>{p.available ? <Badge tone="green">Available</Badge> : <Badge tone="red">Unavailable</Badge>}</div>
              <div className="row wrap mt-4">
                <button className="btn sm" onClick={() => setForm({ ...p })}><Pencil size={14} />Edit</button>
                <button className="btn sm" disabled={busy} onClick={() => toggle(p)}>{p.available ? 'Mark unavailable' : 'Make available'}</button>
                <button className="btn sm ghost icon-btn danger" aria-label={`Delete ${p.name}`} disabled={busy} onClick={() => remove(p)}><Trash /></button>
              </div>
            </div>
          </div>
        ))}</div>
      )}
      <Modal open={!!form} title={form?.id ? 'Edit item' : 'Add item'} onClose={() => setForm(null)}
        footer={<><button className="btn ghost" onClick={() => setForm(null)}>Cancel</button><button className="btn primary" disabled={busy || !form?.name || !(Number(form?.price) > 0)} onClick={save}>Save</button></>}>
        {form && <div className="form-grid">
          <Field label="Item name" className="span-all"><input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Description" className="span-all"><input className="input" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Category"><select className="select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>{['beverage', 'snack', 'meal', 'dessert'].map(c => <option key={c} value={c}>{cap(c)}</option>)}</select></Field>
          <Field label="Price (₹)"><input className="input" type="number" min="1" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} /></Field>
          <Field label="Image (optional)" className="span-all"><input ref={file} className="input" type="file" accept="image/png,image/jpeg,image/webp" style={{ paddingTop: 6 }} /></Field>
          <label className="check"><input type="checkbox" checked={form.available} onChange={e => setForm({ ...form, available: e.target.checked })} />Available</label>
          <label className="check"><input type="checkbox" checked={form.is_veg} onChange={e => setForm({ ...form, is_veg: e.target.checked })} />Vegetarian</label>
        </div>}
      </Modal>
    </div>
  )
}

export default function AdminStore() {
  const [tab, setTab] = useState('orders')
  return (
    <div className="stack">
      <PageHeader title="Canteen Store" subtitle="Extra food orders, separate from mess passes. Students pay at the counter on pickup." />
      <Tabs value={tab} onChange={setTab} options={[{ value: 'orders', label: 'Orders' }, { value: 'products', label: 'Products & prices' }]} />
      {tab === 'orders' ? <Orders /> : <Products />}
    </div>
  )
}
