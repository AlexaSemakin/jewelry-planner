import React, { useMemo } from 'react'
import { fmtMoney, MODE_LABELS } from '../lib/format.js'

/**
 * Схема перемещений по плану: круги-города в порядке прохождения,
 * стрелки-перевозки с лейблом (способ, время, цена).
 */
export default function RouteSchema({ plan }) {
  const sequence = useMemo(() => {
    if (!plan) return []
    const stages = (plan.plan_stages || []).slice().sort((a, b) => a.stage.order_index - b.stage.order_index)
    const seq = []
    for (const ps of stages) {
      const city = ps.performer.city?.name || '—'
      seq.push({ kind: 'stage', city, name: ps.stage.name, performer: ps.performer.name })
    }
    // Вставим перевозки между этапами
    const movesByTo = {}
    for (const mv of (plan.movements || [])) movesByTo[mv.to_stage_id] = mv
    const result = []
    for (let i = 0; i < stages.length; i++) {
      const ps = stages[i]
      const mv = movesByTo[ps.stage_id]
      if (mv && (i > 0 || (mv.route.origin.id !== mv.route.destination.id))) {
        result.push({
          kind: 'move',
          from: mv.route.origin.name,
          to: mv.route.destination.name,
          mode: mv.route.mode,
          cost: mv.cost,
          duration: mv.route.duration_hours,
        })
      }
      result.push({ kind: 'stage', city: ps.performer.city?.name || '—',
                    name: ps.stage.name, performer: ps.performer.name })
    }
    return result
  }, [plan])

  if (sequence.length === 0) {
    return <div className="text-sm text-slate-500">Нет перемещений.</div>
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {sequence.map((node, i) => {
        if (node.kind === 'stage') {
          return (
            <div key={i} className="flex flex-col items-center min-w-[130px] max-w-[160px] text-center">
              <div className="w-12 h-12 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-medium">
                {node.city}
              </div>
              <div className="text-xs font-medium mt-1 text-slate-800 leading-tight">{node.name}</div>
              <div className="text-[10px] text-slate-500 leading-tight">{node.performer}</div>
            </div>
          )
        }
        return (
          <div key={i} className="flex flex-col items-center min-w-[110px]">
            <div className="text-[10px] text-slate-500">{MODE_LABELS[node.mode] || node.mode}</div>
            <div className="flex items-center w-full">
              <div className="flex-1 h-0.5 bg-gold" />
              <div className="text-gold mx-1">▶</div>
            </div>
            <div className="text-[10px] text-slate-600 mt-0.5">
              {node.duration.toFixed(0)} ч · {fmtMoney(node.cost)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
