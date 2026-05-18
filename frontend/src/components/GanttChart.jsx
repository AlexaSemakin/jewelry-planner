import React, { useMemo } from 'react'
import { fmtDateTime, MODE_LABELS } from '../lib/format.js'

const COLOR_STAGE = '#0f172a'
const COLOR_MOVE = '#b08d57'
const PRIORITY_DAYS = [1, 2, 3, 4, 5, 6, 7, 14, 21, 30]

/**
 * Гантт по списку (stages, movements) активного плана.
 * Каждая строка — этап (с производственным интервалом).
 * Перевозки рисуются как соединительные линии между этапами + бейдж стоимости.
 */
export default function GanttChart({ plan }) {
  const rows = useMemo(() => {
    if (!plan) return []
    return (plan.plan_stages || []).map((ps) => ({
      stage_id: ps.stage_id,
      label: ps.stage.name,
      performer: ps.performer.name,
      city: ps.performer.city?.name,
      start: new Date(ps.start_at),
      end: new Date(ps.end_at),
      cost: ps.cost,
      order_index: ps.stage.order_index,
    })).sort((a, b) => a.order_index - b.order_index)
  }, [plan])

  const movesByStage = useMemo(() => {
    const m = {}
    if (!plan) return m
    for (const mv of (plan.movements || [])) {
      const key = mv.to_stage_id
      m[key] = m[key] || []
      m[key].push(mv)
    }
    return m
  }, [plan])

  if (!plan || rows.length === 0) {
    return <div className="text-sm text-slate-500">План пуст.</div>
  }

  // Временной диапазон
  const allStarts = rows.map(r => r.start.getTime())
  const allEnds = rows.map(r => r.end.getTime())
  const moveStarts = (plan.movements || []).map(m => new Date(m.start_at).getTime())
  const moveEnds = (plan.movements || []).map(m => new Date(m.end_at).getTime())
  const t0 = Math.min(...allStarts, ...moveStarts)
  const t1 = Math.max(...allEnds, ...moveEnds)
  const span = Math.max(1, t1 - t0)

  // Размеры
  const ROW_H = 36
  const LEFT_W = 280  // ширина левой панели с лейблами
  const RIGHT_W = 720 // ширина области графика
  const TOP_H = 30
  const HEIGHT = TOP_H + rows.length * ROW_H + 20
  const WIDTH = LEFT_W + RIGHT_W

  const xOf = (t) => LEFT_W + ((t - t0) / span) * (RIGHT_W - 20) + 10

  // Тики по дням
  const ticks = []
  const startDate = new Date(t0); startDate.setHours(0, 0, 0, 0)
  const oneDay = 24 * 60 * 60 * 1000
  const totalDays = Math.ceil(span / oneDay) + 1
  const stride = Math.max(1, Math.ceil(totalDays / 12))
  for (let d = 0; d <= totalDays; d += stride) {
    const t = startDate.getTime() + d * oneDay
    if (t > t1 + oneDay) break
    ticks.push(t)
  }

  return (
    <div className="overflow-x-auto">
      <svg width={WIDTH} height={HEIGHT} className="text-xs">
        {/* Заголовок шкалы времени */}
        <line x1={LEFT_W} y1={TOP_H} x2={WIDTH} y2={TOP_H} stroke="#cbd5e1" />
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={xOf(t)} y1={TOP_H} x2={xOf(t)} y2={HEIGHT - 10} stroke="#e2e8f0" />
            <text x={xOf(t)} y={TOP_H - 8} fill="#64748b" textAnchor="middle">
              {new Date(t).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}
            </text>
          </g>
        ))}

        {/* Строки */}
        {rows.map((r, i) => {
          const y = TOP_H + i * ROW_H + 6
          const x1 = xOf(r.start.getTime())
          const x2 = xOf(r.end.getTime())
          const w = Math.max(4, x2 - x1)
          return (
            <g key={r.stage_id}>
              {/* Лейбл слева */}
              <text x={8} y={y + 14} fill="#0f172a" fontWeight="500">
                {r.label.length > 32 ? r.label.slice(0, 32) + '…' : r.label}
              </text>
              <text x={8} y={y + 26} fill="#64748b">
                {r.performer} · {r.city || ''}
              </text>

              {/* Фоновая полоса */}
              <rect x={LEFT_W} y={y - 4} width={RIGHT_W} height={ROW_H - 8} fill={i % 2 ? '#f8fafc' : 'transparent'} />

              {/* Перевозки ДО этапа */}
              {(movesByStage[r.stage_id] || []).map((mv, j) => {
                const mx1 = xOf(new Date(mv.start_at).getTime())
                const mx2 = xOf(new Date(mv.end_at).getTime())
                const mw = Math.max(2, mx2 - mx1)
                return (
                  <g key={`mv-${j}`}>
                    <rect x={mx1} y={y + 7} width={mw} height={ROW_H - 22} fill={COLOR_MOVE} opacity={0.85} rx={2}>
                      <title>
                        Перевозка ({MODE_LABELS[mv.route.mode] || mv.route.mode}): {mv.route.origin.name} → {mv.route.destination.name}{'\n'}
                        {fmtDateTime(mv.start_at)} — {fmtDateTime(mv.end_at)}{'\n'}
                        Стоимость: {mv.cost} ₽, курьер #{mv.courier_index || '?'}
                      </title>
                    </rect>
                  </g>
                )
              })}

              {/* Прямоугольник этапа */}
              <rect x={x1} y={y} width={w} height={ROW_H - 14} fill={COLOR_STAGE} rx={3}>
                <title>
                  {r.label}{'\n'}
                  {fmtDateTime(r.start)} — {fmtDateTime(r.end)}{'\n'}
                  Исполнитель: {r.performer} ({r.city}){'\n'}
                  Стоимость: {r.cost} ₽
                </title>
              </rect>
            </g>
          )
        })}
      </svg>
      <div className="flex gap-6 mt-3 text-xs">
        <div className="flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-sm" style={{background: COLOR_STAGE}} /> Производство</div>
        <div className="flex items-center gap-2"><span className="inline-block w-3 h-3 rounded-sm" style={{background: COLOR_MOVE}} /> Логистика</div>
      </div>
    </div>
  )
}
