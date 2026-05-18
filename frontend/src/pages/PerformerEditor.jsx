import React, { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { WEEKDAYS } from '../lib/format.js'

export default function PerformerEditor() {
  const { id } = useParams(); const nav = useNavigate()
  const isEdit = Boolean(id)
  const [cities, setCities] = useState([])
  const [templates, setTemplates] = useState([])
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    name: '', city_id: null, specialization: '', contact: '',
    active: true, workdays: [0, 1, 2, 3, 4], skills: [],
  })

  useEffect(() => {
    (async () => {
      try {
        const [c, t] = await Promise.all([api.cities(), api.stageTemplates()])
        setCities(c); setTemplates(t)
        if (isEdit) {
          const p = await api.performer(id)
          setForm({
            name: p.name, city_id: p.city_id, specialization: p.specialization,
            contact: p.contact, active: p.active, workdays: p.workdays,
            skills: p.skills.map(s => ({
              stage_template_id: s.stage_template_id, cost: s.cost, duration_hours: s.duration_hours,
            })),
          })
        }
      } catch (e) { setErr(e.message) }
    })()
  }, [id])

  const u = (k, v) => setForm(s => ({ ...s, [k]: v }))
  const toggleDay = (d) => setForm(s => ({
    ...s, workdays: s.workdays.includes(d) ? s.workdays.filter(x => x !== d) : [...s.workdays, d].sort()
  }))
  const addSkill = () => setForm(s => ({ ...s, skills: [...s.skills, { stage_template_id: '', cost: 0, duration_hours: 8 }] }))
  const updSkill = (i, k, v) => setForm(s => {
    const skills = [...s.skills]; skills[i] = { ...skills[i], [k]: v }; return { ...s, skills }
  })
  const delSkill = (i) => setForm(s => ({ ...s, skills: s.skills.filter((_, j) => j !== i) }))

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('')
    try {
      if (!form.name) throw new Error('Введите имя/название')
      if (!form.city_id) throw new Error('Выберите город')
      if (form.skills.length === 0) throw new Error('Добавьте хотя бы один навык')
      const payload = {
        ...form,
        city_id: parseInt(form.city_id),
        skills: form.skills.map(s => ({
          stage_template_id: parseInt(s.stage_template_id),
          cost: parseFloat(s.cost) || 0,
          duration_hours: parseFloat(s.duration_hours) || 0,
        })),
      }
      for (const s of payload.skills) if (!s.stage_template_id) throw new Error('У каждого навыка должен быть тип этапа')
      if (isEdit) await api.updatePerformer(id, payload); else await api.createPerformer(payload)
      nav('/performers')
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{isEdit ? 'Редактирование исполнителя' : 'Новый исполнитель'}</h1>
        <Link to="/performers" className="text-sm text-slate-600 hover:underline">← к списку</Link>
      </div>
      {err && <div className="card text-rose-700">{err}</div>}
      <div className="card grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">Имя / название *</label>
          <input className="input" value={form.name} onChange={e => u('name', e.target.value)} />
        </div>
        <div>
          <label className="label">Город *</label>
          <select className="input" value={form.city_id || ''} onChange={e => u('city_id', e.target.value)}>
            <option value="">— выбрать —</option>
            {cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Специализация</label>
          <input className="input" value={form.specialization} onChange={e => u('specialization', e.target.value)} />
        </div>
        <div>
          <label className="label">Контакт</label>
          <input className="input" value={form.contact} onChange={e => u('contact', e.target.value)} placeholder="телефон, e-mail" />
        </div>
        <div className="md:col-span-2">
          <label className="label">Рабочие дни</label>
          <div className="flex gap-2 flex-wrap">
            {WEEKDAYS.map((d, i) => {
              const checked = form.workdays.includes(i)
              return (
                <button type="button" key={i} onClick={() => toggleDay(i)}
                        className={`px-3 py-1 rounded-md border text-sm ${checked ? 'bg-slate-900 text-white border-slate-900' : 'bg-white border-slate-300 text-slate-700'}`}>
                  {d}
                </button>
              )
            })}
          </div>
        </div>
        <div className="md:col-span-2 flex items-center gap-2">
          <input type="checkbox" id="active" checked={form.active} onChange={e => u('active', e.target.checked)} />
          <label htmlFor="active" className="text-sm">Активен (учитывается в планировании)</label>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Навыки (типы этапов)</h2>
          <button type="button" onClick={addSkill} className="btn-secondary">+ Добавить навык</button>
        </div>
        {form.skills.length === 0 && (
          <div className="text-sm text-slate-500 text-center py-4">Добавьте хотя бы один навык.</div>
        )}
        <div className="space-y-2">
          {form.skills.map((s, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-6">
                <label className="label">Тип этапа</label>
                <select className="input" value={s.stage_template_id} onChange={e => updSkill(i, 'stage_template_id', e.target.value)}>
                  <option value="">— выбрать —</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="col-span-3">
                <label className="label">Стоимость, ₽</label>
                <input type="number" className="input" value={s.cost} onChange={e => updSkill(i, 'cost', e.target.value)} />
              </div>
              <div className="col-span-2">
                <label className="label">Длит., ч</label>
                <input type="number" step="0.5" className="input" value={s.duration_hours} onChange={e => updSkill(i, 'duration_hours', e.target.value)} />
              </div>
              <div className="col-span-1 text-right">
                <button type="button" onClick={() => delSkill(i)} className="text-rose-500 hover:text-rose-700">✕</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Link to="/performers" className="btn-secondary">Отмена</Link>
        <button type="submit" disabled={busy} className="btn-primary disabled:opacity-50">
          {busy ? 'Сохранение…' : (isEdit ? 'Сохранить' : 'Создать')}
        </button>
      </div>
    </form>
  )
}
