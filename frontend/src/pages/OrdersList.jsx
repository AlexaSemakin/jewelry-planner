import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { fmtMoney, fmtDate, STATUS_LABELS } from '../lib/format.js'
import { OrderStatusBadge } from '../components/Badges.jsx'

const FILTERS = [
  { v: '', label: 'Все' },
  { v: 'draft', label: 'Черновики' },
  { v: 'estimated', label: 'Оценки' },
  { v: 'confirmed', label: 'Подтверждены' },
  { v: 'in_production', label: 'В работе' },
  { v: 'at_risk', label: 'Под угрозой' },
  { v: 'done', label: 'Завершены' },
]

export default function OrdersList() {
  const [orders, setOrders] = useState([])
  const [filter, setFilter] = useState('')
  const [err, setErr] = useState('')

  const reload = async () => {
    try { setErr(''); setOrders(await api.orders(filter || undefined)) }
    catch (e) { setErr(e.message) }
  }
  useEffect(() => { reload() }, [filter])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Заказы</h1>
        <Link to="/orders/new" className="btn-primary">Новый заказ</Link>
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map(f => (
          <button key={f.v}
                  onClick={() => setFilter(f.v)}
                  className={`btn ${filter === f.v ? 'bg-slate-900 text-white' : 'btn-secondary'}`}>
            {f.label}
          </button>
        ))}
      </div>
      {err && <div className="card text-rose-700">Ошибка: {err}</div>}
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Клиент</th>
              <th>Материал</th>
              <th>Дедлайн</th>
              <th>Статус</th>
              <th>Стоимость</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td><Link to={`/orders/${o.id}`} className="text-slate-900 hover:underline">{o.name}</Link></td>
                <td>{o.customer || '—'}</td>
                <td>—</td>
                <td>{fmtDate(o.deadline)}</td>
                <td><OrderStatusBadge status={o.status} /></td>
                <td>{fmtMoney(o.actual_cost || o.estimated_cost)}</td>
                <td className="text-right">
                  <Link to={`/orders/${o.id}`} className="text-slate-600 hover:text-slate-900 mr-3">открыть</Link>
                  {(o.status === 'draft' || o.status === 'estimated') && (
                    <Link to={`/orders/${o.id}/edit`} className="text-slate-600 hover:text-slate-900">изменить</Link>
                  )}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan="7" className="text-center text-slate-500 py-6">Нет заказов в этой выборке</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
