import React from 'react'
import { STATUS_LABELS, STATUS_COLORS, STAGE_STATUS_LABELS, STAGE_STATUS_COLORS } from '../lib/format.js'

export function OrderStatusBadge({ status }) {
  const label = STATUS_LABELS[status] || status
  const cls = STATUS_COLORS[status] || 'bg-slate-100 text-slate-600'
  return <span className={`badge ${cls}`}>{label}</span>
}

export function StageStatusBadge({ status }) {
  const label = STAGE_STATUS_LABELS[status] || status
  const cls = STAGE_STATUS_COLORS[status] || 'bg-slate-100 text-slate-600'
  return <span className={`badge ${cls}`}>{label}</span>
}
