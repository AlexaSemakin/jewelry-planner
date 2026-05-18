import React, { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api } from '../api/api.js'

const emptyStage = () => ({
  stage_template_id: null,
  order_index: 0,
  name: '',
  attributes: {},
  candidate_performer_ids: [],
})

export default function OrderEditor() {
  const nav = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)
  const [cities, setCities] = useState([])
  const [templates, setTemplates] = useState([])
  const [performers, setPerformers] = useState([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const [form, setForm] = useState({
    name: '',
    description: '',
    customer: '',
    deadline: '',
    material: '',
    weight_g: 0,
    start_city_id: null,
    stages: [],
  })

  useEffect(() => {
    (async () => {
      try {
        const [c, t, p] = await Promise.all([api.cities(), api.stageTemplates(), api.performers()])
        setCities(c); setTemplates(t); setPerformers(p)
        if (isEdit) {
          const o = await api.order(id)
          setForm({
            name: o.name,
            description: o.description || '',
            customer: o.customer || '',
            deadline: o.deadline,
            material: o.material || '',
            weight_g: o.weight_g || 0,
            start_city_id: o.start_city_id,
            stages: o.stages.map(s => ({
              stage_template_id: s.stage_template_id,
              order_index: s.order_index,
              name: s.name,
              attributes: s.attributes || {},
              candidate_performer_ids: s.candidates.map(c => c.performer_id),
            })),
          })
        }
      } catch (e) { setErr(e.message) }
    })()
  }, [id])

  const updField = (k, v) => setForm(s => ({ ...s, [k]: v }))
  const updStage = (i, k, v) => setForm(s => {
    const stages = [...s.stages]; stages[i] = { ...stages[i], [k]: v }; return { ...s, stages }
  })
  const addStage = () => setForm(s => ({
    ...s,
    stages: [...s.stages, { ...emptyStage(), order_index: s.stages.length }]
  }))
  const removeStage = (i) => setForm(s => {
    const stages = s.stages.filter((_, idx) => idx !== i).map((st, idx) => ({ ...st, order_index: idx }))
    return { ...s, stages }
  })
  const moveStage = (i, dir) => setForm(s => {
    const j = i + dir
    if (j < 0 || j >= s.stages.length) return s
    const stages = [...s.stages];
    [stages[i], stages[j]] = [stages[j], stages[i]]
    return { ...s, stages: stages.map((st, idx) => ({ ...st, order_index: idx })) }
  })

  const togglePerformer = (i, pid) => setForm(s => {
    const stages = [...s.stages]
    const set = new Set(stages[i].candidate_performer_ids)
    if (set.has(pid)) set.delete(pid); else set.add(pid)
    stages[i] = { ...stages[i], candidate_performer_ids: [...set] }
    return { ...s, stages }
  })

  // Для какого типа этапа — какие исполнители подходят
  const compatiblePerformers = (tplId) => {
    if (!tplId) return []
    return performers.filter(p => p.skills.some(sk => sk.stage_template_id === tplId) && p.active)
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const payload = {
        ...form,
        weight_g: parseFloat(form.weight_g) || 0,
        start_city_id: form.start_city_id ? parseInt(form.start_city_id) : null,
        stages: form.stages.map((st, idx) => ({
          ...st,
          order_index: idx,
          stage_template_id: parseInt(st.stage_template_id),
        })),
      }
      // Валидация
      if (!payload.name) throw new Error('Введите название изделия')
      if (!payload.deadline) throw new Error('Укажите дедлайн')
      if (payload.stages.length === 0) throw new Error('Добавьте хотя бы один этап')
      for (const [i, st] of payload.stages.entries()) {
        if (!st.stage_template_id) throw new Error(`Этап #${i + 1}: выберите тип`)
        if (!st.name) throw new Error(`Этап #${i + 1}: введите название`)
        if (st.candidate_performer_ids.length === 0)
          throw new Error(`Этап #${i + 1}: выберите хотя бы одного возможного исполнителя`)
      }
      const o = isEdit ? await api.updateOrder(id, payload) : await api.createOrder(payload)
      nav(`/orders/${o.id}`)
    } catch (e) {
      setErr(e.message)
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{isEdit ? 'Редактирование заказа' : 'Новый заказ'}</h1>
        <Link to="/orders" className="text-sm text-slate-600 hover:underline">← к списку</Link>
      </div>
      {err && <div className="card text-rose-700">{err}</div>}

      <div className="card grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">Название изделия *</label>
          <input className="input" value={form.name} onChange={e => updField('name', e.target.value)} />
        </div>
        <div>
          <label className="label">Клиент</label>
          <input className="input" value={form.customer} onChange={e => updField('customer', e.target.value)} />
        </div>
        <div>
          <label className="label">Дедлайн *</label>
          <input type="date" className="input" value={form.deadline} onChange={e => updField('deadline', e.target.value)} />
        </div>
        <div>
          <label className="label">Стартовый город</label>
          <select className="input" value={form.start_city_id || ''} onChange={e => updField('start_city_id', e.target.value || null)}>
            <option value="">— не указан —</option>
            {cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Материал</label>
          <input className="input" value={form.material} onChange={e => updField('material', e.target.value)} placeholder="Au 585, Pt 950 и т.п." />
        </div>
        <div>
          <label className="label">Вес, г</label>
          <input type="number" step="0.1" className="input" value={form.weight_g} onChange={e => updField('weight_g', e.target.value)} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Описание</label>
          <textarea rows={2} className="input" value={form.description} onChange={e => updField('description', e.target.value)} />
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Производственный процесс</h2>
          <button type="button" onClick={addStage} className="btn-secondary">+ Добавить этап</button>
        </div>
        {form.stages.length === 0 && (
          <div className="text-sm text-slate-500 text-center py-6">
            Этапов пока нет. Нажмите «Добавить этап», чтобы собрать индивидуальный техпроцесс.
          </div>
        )}
        <div className="space-y-3">
          {form.stages.map((st, i) => {
            const compatible = compatiblePerformers(parseInt(st.stage_template_id))
            return (
              <div key={i} className="border border-slate-200 rounded-md p-3 bg-slate-50/50">
                <div className="flex items-start gap-2 mb-3">
                  <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-sm font-medium shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="label">Тип этапа *</label>
                      <select className="input" value={st.stage_template_id || ''}
                              onChange={e => updStage(i, 'stage_template_id', parseInt(e.target.value))}>
                        <option value="">— выбрать —</option>
                        {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="label">Название этапа *</label>
                      <input className="input" value={st.name} onChange={e => updStage(i, 'name', e.target.value)} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="label">Атрибуты (JSON, опционально)</label>
                      <input
                        className="input font-mono text-xs"
                        value={JSON.stringify(st.attributes)}
                        onChange={e => {
                          try { updStage(i, 'attributes', JSON.parse(e.target.value || '{}')) }
                          catch { /* игнор пока пользователь печатает */ }
                        }}
                        placeholder='{"metal":"Au 585"}'
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button type="button" onClick={() => moveStage(i, -1)} className="text-slate-400 hover:text-slate-700 text-sm">↑</button>
                    <button type="button" onClick={() => moveStage(i, 1)} className="text-slate-400 hover:text-slate-700 text-sm">↓</button>
                    <button type="button" onClick={() => removeStage(i)} className="text-rose-500 hover:text-rose-700 text-sm">✕</button>
                  </div>
                </div>

                <div>
                  <div className="label">Возможные исполнители * {st.stage_template_id && compatible.length === 0 && (
                    <span className="text-rose-600">— нет исполнителей с этим навыком</span>)}</div>
                  <div className="flex flex-wrap gap-2">
                    {compatible.map(p => {
                      const checked = st.candidate_performer_ids.includes(p.id)
                      return (
                        <label key={p.id} className={`cursor-pointer text-xs px-2 py-1 rounded-md border ${checked ? 'bg-slate-900 text-white border-slate-900' : 'bg-white border-slate-300 text-slate-700'}`}>
                          <input type="checkbox" className="hidden" checked={checked}
                                 onChange={() => togglePerformer(i, p.id)} />
                          {p.name} <span className="opacity-70">· {p.city.name}</span>
                        </label>
                      )
                    })}
                    {st.stage_template_id && compatible.length === 0 && (
                      <div className="text-xs text-slate-500">
                        Чтобы появились варианты, заведите исполнителей с этим навыком в разделе «Исполнители».
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="flex gap-2 justify-end">
        <Link to="/orders" className="btn-secondary">Отмена</Link>
        <button type="submit" disabled={busy} className="btn-primary disabled:opacity-50">
          {busy ? 'Сохранение…' : (isEdit ? 'Сохранить изменения' : 'Создать заказ')}
        </button>
      </div>
    </form>
  )
}
