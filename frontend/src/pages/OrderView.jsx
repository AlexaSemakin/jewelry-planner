import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { fmtDate, fmtDateTime, fmtMoney, MODE_LABELS } from '../lib/format.js'
import { OrderStatusBadge, StageStatusBadge } from '../components/Badges.jsx'
import GanttChart from '../components/GanttChart.jsx'
import RouteSchema from '../components/RouteSchema.jsx'

export default function OrderView() {
  const { id } = useParams()
  const [order, setOrder] = useState(null)
  const [plan, setPlan] = useState(null)
  const [history, setHistory] = useState([])
  const [estimating, setEstimating] = useState(false)
  const [estimateResult, setEstimateResult] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const reload = async () => {
    try {
      setErr('')
      const [o, p, h] = await Promise.all([api.order(id), api.activePlan(id), api.orderHistory(id)])
      setOrder(o); setPlan(p); setHistory(h)
    } catch (e) { setErr(e.message) }
  }
  useEffect(() => { reload() }, [id])

  const onEstimate = async () => {
    setEstimating(true); setEstimateResult(null); setErr('')
    try {
      const res = await api.estimateOrder(id, true)
      setEstimateResult(res)
      await reload()
    } catch (e) { setErr(e.message) }
    finally { setEstimating(false) }
  }

  const onConfirm = async () => { setBusy(true); try { await api.confirmOrder(id); await reload() } catch(e){ setErr(e.message) } finally { setBusy(false) } }
  const onStart = async () => { setBusy(true); try { await api.startOrder(id); await reload() } catch(e){ setErr(e.message) } finally { setBusy(false) } }
  const onReplan = async () => { setBusy(true); try { await api.replanOrder(id); await reload() } catch(e){ setErr(e.message) } finally { setBusy(false) } }

  const onStageStatus = async (sid, status) => {
    try {
      const update = { status }
      if (status === 'in_progress' || status === 'in_transit') update.actual_start = new Date().toISOString()
      if (status === 'done') update.actual_end = new Date().toISOString()
      await api.updateStageStatus(sid, update)
      await reload()
    } catch (e) { setErr(e.message) }
  }

  if (err) return <div className="card text-rose-700">Ошибка: {err}</div>
  if (!order) return <div className="card">Загрузка…</div>

  const planStages = (plan?.plan_stages || []).slice().sort((a, b) => a.stage.order_index - b.stage.order_index)
  const explanation = plan?.explanation || {}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <Link to="/orders" className="text-sm text-slate-600 hover:underline">← к списку</Link>
          <h1 className="text-xl font-semibold mt-1">{order.name}</h1>
          <div className="text-sm text-slate-500">
            Клиент: <b>{order.customer || '—'}</b> · Дедлайн: <b>{fmtDate(order.deadline)}</b>
            {' '}· Материал: <b>{order.material || '—'}</b>{order.weight_g ? `, ${order.weight_g} г` : ''}
            {' · '}<OrderStatusBadge status={order.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={onEstimate} disabled={estimating} className="btn-secondary disabled:opacity-50">
            {estimating ? 'Расчёт…' : 'Пересчитать оценку'}
          </button>
          {(order.status === 'estimated' || order.status === 'draft') && plan?.feasible && (
            <button onClick={onConfirm} disabled={busy} className="btn-primary disabled:opacity-50">Подтвердить</button>
          )}
          {order.status === 'confirmed' && (
            <button onClick={onStart} disabled={busy} className="btn-primary disabled:opacity-50">Запустить в работу</button>
          )}
          {(order.status === 'in_production' || order.status === 'at_risk') && (
            <button onClick={onReplan} disabled={busy} className="btn-secondary disabled:opacity-50">Пересчитать план</button>
          )}
          {(order.status === 'draft' || order.status === 'estimated') && (
            <Link to={`/orders/${id}/edit`} className="btn-secondary">Изменить</Link>
          )}
        </div>
      </div>

      {estimateResult && (
        <div className={`card ${estimateResult.feasible ? 'border-emerald-300 bg-emerald-50/40' : 'border-rose-300 bg-rose-50/40'}`}>
          <div className="font-semibold mb-1">
            {estimateResult.feasible
              ? '✔ Срок реалистичен'
              : '⚠ Срок невыполним'}
          </div>
          <div className="text-sm text-slate-700">{estimateResult.message}</div>
          <div className="text-sm mt-2">
            <b>Стоимость:</b> {fmtMoney(estimateResult.total_cost)} (производство {fmtMoney(estimateResult.production_cost)}, логистика {fmtMoney(estimateResult.logistics_cost)})
          </div>
          <div className="text-sm">
            <b>Готовность по плану:</b> {fmtDate(estimateResult.completion_date)}
          </div>
        </div>
      )}

      {plan ? (
        <>
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Активный план</h2>
              <div className="text-sm text-slate-600">
                Готовность: <b>{fmtDate(plan.completion_date)}</b> ·
                {' '}Стоимость: <b>{fmtMoney(plan.total_cost)}</b>
                {' '}(произв. {fmtMoney(plan.production_cost)}, лог. {fmtMoney(plan.logistics_cost)})
                {!plan.feasible && <span className="ml-2 text-rose-700 font-medium">срок не уложен</span>}
              </div>
            </div>
            <GanttChart plan={plan} />
          </div>

          <div className="card">
            <h2 className="font-semibold mb-3">Схема перемещений</h2>
            <RouteSchema plan={plan} />
          </div>

          <div className="card">
            <h2 className="font-semibold mb-3">Этапы плана и отслеживание</h2>
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Этап</th>
                  <th>Исполнитель</th>
                  <th>План: даты</th>
                  <th>Стоимость</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {planStages.map(ps => {
                  const stage = order.stages.find(s => s.id === ps.stage_id) || ps.stage
                  return (
                    <tr key={ps.id}>
                      <td>{ps.stage.order_index + 1}</td>
                      <td>{ps.stage.name}</td>
                      <td>
                        {ps.performer.name}<br />
                        <span className="text-xs text-slate-500">{ps.performer.city.name}</span>
                      </td>
                      <td>
                        <div>{fmtDateTime(ps.start_at)}</div>
                        <div className="text-xs text-slate-500">→ {fmtDateTime(ps.end_at)}</div>
                      </td>
                      <td>{fmtMoney(ps.cost)}</td>
                      <td><StageStatusBadge status={stage.status} /></td>
                      <td className="text-right">
                        {(order.status === 'in_production' || order.status === 'at_risk') && stage.status !== 'done' && (
                          <div className="flex gap-1 justify-end">
                            {stage.status === 'pending' && <button onClick={() => onStageStatus(ps.stage_id, 'in_progress')} className="btn-secondary text-xs">▶ начать</button>}
                            {stage.status === 'in_progress' && <button onClick={() => onStageStatus(ps.stage_id, 'done')} className="btn-secondary text-xs">✓ готово</button>}
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {plan.movements && plan.movements.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-3">Перемещения</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Откуда → куда</th>
                    <th>Способ</th>
                    <th>Старт</th>
                    <th>Прибытие</th>
                    <th>Стоимость</th>
                    <th>Курьер</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.movements.map(m => (
                    <tr key={m.id}>
                      <td>{m.route.origin.name} → {m.route.destination.name}</td>
                      <td>{MODE_LABELS[m.route.mode] || m.route.mode}</td>
                      <td>{fmtDateTime(m.start_at)}</td>
                      <td>{fmtDateTime(m.end_at)}</td>
                      <td>{fmtMoney(m.cost)}</td>
                      <td>#{m.courier_index || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="card">
            <h2 className="font-semibold mb-3">Объяснение плана</h2>
            <div className="space-y-3">
              {(explanation.stages || []).map((se, i) => (
                <div key={i} className="border border-slate-200 rounded-md p-3">
                  <div className="font-medium text-slate-800 mb-1">{se.stage_name}</div>
                  <div className="text-xs text-slate-500 mb-2">
                    {se.reasons && se.reasons.length > 0
                      ? se.reasons.join('; ')
                      : 'Выбор сделан с учётом стоимости, длительности и доступности.'}
                  </div>
                  <table className="table text-xs">
                    <thead>
                      <tr><th></th><th>Исполнитель</th><th>Цена</th><th>Длит., ч</th></tr>
                    </thead>
                    <tbody>
                      {se.alternatives.map((alt, j) => {
                        const p = (order.stages.find(s => s.name === se.stage_name)?.candidates || [])
                          .find(c => c.performer_id === alt.performer_id)?.performer
                        return (
                          <tr key={j} className={alt.chosen ? 'bg-emerald-50' : ''}>
                            <td>{alt.chosen ? '✔' : ''}</td>
                            <td>{p?.name || `#${alt.performer_id}`} <span className="text-slate-500">({p?.city?.name})</span></td>
                            <td>{fmtMoney(alt.cost)}</td>
                            <td>{alt.duration_hours}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="card text-sm text-slate-500">
          План ещё не построен. Нажмите «Пересчитать оценку», чтобы система подобрала исполнителей,
          маршруты и сроки.
        </div>
      )}

      <div className="card">
        <h2 className="font-semibold mb-3">История заказа</h2>
        {history.length === 0 ? (
          <div className="text-sm text-slate-500">События пока не зафиксированы.</div>
        ) : (
          <ul className="space-y-2 text-sm">
            {history.map(h => (
              <li key={h.id} className="flex gap-3 border-b border-slate-100 pb-1">
                <span className="text-slate-400 w-32 shrink-0">{fmtDateTime(h.created_at)}</span>
                <span className="font-medium text-slate-700">{h.event_type}</span>
                <span className="text-slate-500">{Object.keys(h.payload || {}).length > 0 ? JSON.stringify(h.payload) : ''}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
