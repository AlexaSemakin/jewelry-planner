import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { fmtMoney, fmtDate } from '../lib/format.js'
import { OrderStatusBadge } from '../components/Badges.jsx'

function Tile({ label, value, hint, accent }) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${accent || 'text-slate-900'}`}>{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [d, setD] = useState(null)
  const [orders, setOrders] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const reload = async () => {
    try {
      setError('')
      setD(await api.dashboard())
      setOrders(await api.orders())
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { reload() }, [])

  const onReplan = async () => {
    setBusy(true)
    try { await api.replanAll(); await reload() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (error) return <div className="card text-rose-700">Ошибка: {error}</div>
  if (!d) return <div className="card">Загрузка…</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Дашборд</h1>
        <button onClick={onReplan} disabled={busy} className="btn-primary disabled:opacity-50">
          {busy ? 'Пересчёт…' : 'Пересчитать планы по всем заказам'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Tile label="Активные заказы" value={d.active_orders} />
        <Tile label="Завершённые" value={d.done_orders} />
        <Tile label="Под угрозой" value={d.at_risk_orders} accent={d.at_risk_orders > 0 ? 'text-rose-600' : ''} />
        <Tile label="Просроченные" value={d.overdue_orders} accent={d.overdue_orders > 0 ? 'text-red-700' : ''} />

        <Tile label="Курьеров (лимит)" value={d.couriers_total}
              hint={`Загрузка ≈ ${d.couriers_load_pct}%`} />
        <Tile label="Активные исполнители" value={d.performers_active} />
        <Tile label="Стоимость производства" value={fmtMoney(d.total_production_cost)} />
        <Tile label="Стоимость логистики" value={fmtMoney(d.total_logistics_cost)} />
      </div>

      {d.savings_vs_naive_pct != null && (
        <div className="card flex items-center justify-between">
          <div>
            <div className="text-sm text-slate-500">Экономия относительно неоптимизированного плана</div>
            <div className="text-3xl font-semibold text-emerald-600 mt-1">
              {d.savings_vs_naive_pct > 0 ? `−${d.savings_vs_naive_pct}%` : `${d.savings_vs_naive_pct}%`}
            </div>
          </div>
          <div className="text-xs text-slate-400 max-w-sm text-right">
            «Наивный» план — самые дорогие исполнители + самые дорогие маршруты.
            Сравнивается с активным планом текущего портфеля.
          </div>
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-800">Заказы</h2>
          <Link to="/orders/new" className="btn-primary">Новый заказ</Link>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Клиент</th>
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
                <td>{fmtDate(o.deadline)}</td>
                <td><OrderStatusBadge status={o.status} /></td>
                <td>{fmtMoney(o.actual_cost || o.estimated_cost)}</td>
                <td className="text-right">
                  <Link to={`/orders/${o.id}`} className="text-slate-600 hover:text-slate-900">подробнее →</Link>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan="6" className="text-center text-slate-500 py-6">Заказов пока нет</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
