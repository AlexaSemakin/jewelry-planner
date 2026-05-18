export const fmtMoney = (v) =>
  new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Math.round(v || 0)) + ' ₽'

export const fmtDate = (s) => {
  if (!s) return '—'
  const d = new Date(s)
  return d.toLocaleDateString('ru-RU')
}

export const fmtDateTime = (s) => {
  if (!s) return '—'
  const d = new Date(s)
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export const STATUS_LABELS = {
  draft: 'Черновик',
  estimated: 'Оценка',
  confirmed: 'Подтверждён',
  in_production: 'В работе',
  at_risk: 'Под угрозой',
  done: 'Завершён',
  overdue: 'Просрочен',
  cancelled: 'Отменён',
}

export const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-700',
  estimated: 'bg-blue-100 text-blue-800',
  confirmed: 'bg-indigo-100 text-indigo-800',
  in_production: 'bg-amber-100 text-amber-800',
  at_risk: 'bg-rose-100 text-rose-800',
  done: 'bg-emerald-100 text-emerald-800',
  overdue: 'bg-red-100 text-red-800',
  cancelled: 'bg-slate-200 text-slate-600',
}

export const STAGE_STATUS_LABELS = {
  pending: 'Ожидает',
  in_progress: 'Выполняется',
  in_transit: 'В пути',
  done: 'Готов',
}

export const STAGE_STATUS_COLORS = {
  pending: 'bg-slate-100 text-slate-600',
  in_progress: 'bg-amber-100 text-amber-800',
  in_transit: 'bg-sky-100 text-sky-800',
  done: 'bg-emerald-100 text-emerald-800',
}

export const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export const MODE_LABELS = {
  rail: 'РЖД',
  air: 'Авиа',
  courier: 'Курьер',
}
