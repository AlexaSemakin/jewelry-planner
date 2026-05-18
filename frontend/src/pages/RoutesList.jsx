import React, { useEffect, useState } from 'react'
import { api } from '../api/api.js'
import { fmtMoney, MODE_LABELS } from '../lib/format.js'
import Modal from '../components/Modal.jsx'

const blankRoute = () => ({
  origin_id: '', destination_id: '', mode: 'rail',
  cost: 0, duration_hours: 0, handover_hours: 1, pickup_hours: 1,
})

export default function RoutesList() {
  const [routes, setRoutes] = useState([])
  const [cities, setCities] = useState([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(blankRoute())
  const [err, setErr] = useState('')

  const reload = async () => {
    try { setErr(''); setRoutes(await api.routes()); setCities(await api.cities()) }
    catch (e) { setErr(e.message) }
  }
  useEffect(() => { reload() }, [])

  const u = (k, v) => setForm(s => ({ ...s, [k]: v }))

  const onSave = async () => {
    try {
      if (!form.origin_id || !form.destination_id) throw new Error('Выберите оба города')
      if (form.origin_id === form.destination_id) throw new Error('Города не должны совпадать')
      const payload = {
        ...form,
        origin_id: parseInt(form.origin_id), destination_id: parseInt(form.destination_id),
        cost: parseFloat(form.cost), duration_hours: parseFloat(form.duration_hours),
        handover_hours: parseFloat(form.handover_hours), pickup_hours: parseFloat(form.pickup_hours),
      }
      await api.createRoute(payload)
      setOpen(false); setForm(blankRoute()); await reload()
    } catch (e) { setErr(e.message) }
  }

  const onDelete = async (id) => {
    if (!confirm('Удалить маршрут?')) return
    try { await api.deleteRoute(id); await reload() }
    catch (e) { setErr(e.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Маршруты перевозки</h1>
        <button onClick={() => setOpen(true)} className="btn-primary">+ Маршрут</button>
      </div>
      <div className="text-xs text-slate-500">
        Маршруты — это варианты, возвращаемые имитацией интеграции с РЖД/Авиа.
        Замена заглушки на реальный коннектор не меняет остальную систему.
      </div>
      {err && <div className="card text-rose-700">{err}</div>}
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Откуда → куда</th>
              <th>Способ</th>
              <th>Время в пути, ч</th>
              <th>Передача / получение, ч</th>
              <th>Стоимость</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {routes.map(r => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td>{r.origin.name} → {r.destination.name}</td>
                <td>{MODE_LABELS[r.mode] || r.mode}</td>
                <td>{r.duration_hours}</td>
                <td>{r.handover_hours} / {r.pickup_hours}</td>
                <td>{fmtMoney(r.cost)}</td>
                <td className="text-right">
                  <button onClick={() => onDelete(r.id)} className="text-rose-500 hover:text-rose-700">удалить</button>
                </td>
              </tr>
            ))}
            {routes.length === 0 && <tr><td colSpan="6" className="text-center text-slate-500 py-6">Маршрутов пока нет</td></tr>}
          </tbody>
        </table>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Новый маршрут"
             footer={<><button onClick={() => setOpen(false)} className="btn-secondary">Отмена</button><button onClick={onSave} className="btn-primary">Сохранить</button></>}>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Откуда</label>
            <select className="input" value={form.origin_id} onChange={e => u('origin_id', e.target.value)}>
              <option value="">—</option>
              {cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Куда</label>
            <select className="input" value={form.destination_id} onChange={e => u('destination_id', e.target.value)}>
              <option value="">—</option>
              {cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Способ</label>
            <select className="input" value={form.mode} onChange={e => u('mode', e.target.value)}>
              <option value="rail">РЖД</option>
              <option value="air">Авиа</option>
              <option value="courier">Курьер</option>
            </select>
          </div>
          <div>
            <label className="label">Стоимость, ₽</label>
            <input type="number" className="input" value={form.cost} onChange={e => u('cost', e.target.value)} />
          </div>
          <div>
            <label className="label">Время в пути, ч</label>
            <input type="number" step="0.5" className="input" value={form.duration_hours} onChange={e => u('duration_hours', e.target.value)} />
          </div>
          <div>
            <label className="label">Передача, ч</label>
            <input type="number" step="0.5" className="input" value={form.handover_hours} onChange={e => u('handover_hours', e.target.value)} />
          </div>
          <div>
            <label className="label">Получение, ч</label>
            <input type="number" step="0.5" className="input" value={form.pickup_hours} onChange={e => u('pickup_hours', e.target.value)} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
