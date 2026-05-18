import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { fmtDate, fmtMoney, STATUS_LABELS } from '../lib/format.js'
import { OrderStatusBadge } from '../components/Badges.jsx'

export default function History() {
  const [orders, setOrders] = useState([])
  const [err, setErr] = useState('')

  const reload = async () => {
    try {
      setErr('')
      const all = await api.orders()
      setOrders(all.filter(o => o.status === 'done' || o.status === 'cancelled' || o.status === 'overdue'))
    } catch (e) { setErr(e.message) }
  }
  useEffect(() => { reload() }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">История завершённых заказов</h1>
      {err && <div className="card text-rose-700">{err}</div>}
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Заказ</th>
              <th>Клиент</th>
              <th>Дедлайн</th>
              <th>Статус</th>
              <th>Стоимость (план / факт)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td><Link to={`/orders/${o.id}`} className="text-slate-900 hover:underline">{o.name}</Link></td>
                <td>{o.customer || '—'}</td>
                <td>{fmtDate(o.deadline)}</td>
                <td><OrderStatusBadge status={o.status} /></td>
                <td>{fmtMoney(o.estimated_cost)} / {fmtMoney(o.actual_cost)}</td>
                <td className="text-right">
                  <Link to={`/orders/${o.id}`} className="text-slate-600 hover:text-slate-900">подробнее →</Link>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan="6" className="text-center text-slate-500 py-6">Пока нет завершённых заказов</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
