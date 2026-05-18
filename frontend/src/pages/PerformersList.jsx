import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/api.js'
import { fmtMoney, WEEKDAYS } from '../lib/format.js'

export default function PerformersList() {
  const [items, setItems] = useState([])
  const [err, setErr] = useState('')

  const reload = async () => {
    try { setErr(''); setItems(await api.performers()) }
    catch (e) { setErr(e.message) }
  }
  useEffect(() => { reload() }, [])

  const onDelete = async (id) => {
    if (!confirm('Удалить исполнителя?')) return
    try { await api.deletePerformer(id); await reload() }
    catch (e) { setErr(e.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Исполнители</h1>
        <Link to="/performers/new" className="btn-primary">+ Новый исполнитель</Link>
      </div>
      {err && <div className="card text-rose-700">{err}</div>}
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Имя / название</th>
              <th>Город</th>
              <th>Специализация</th>
              <th>Навыки (цена / срок)</th>
              <th>Рабочие дни</th>
              <th>Активен</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map(p => (
              <tr key={p.id} className="hover:bg-slate-50">
                <td>{p.name}</td>
                <td>{p.city.name}</td>
                <td className="text-xs">{p.specialization}</td>
                <td className="text-xs">
                  {p.skills.map(s => (
                    <div key={s.id}>
                      <b>{s.stage_template.name}</b> — {fmtMoney(s.cost)} / {s.duration_hours} ч
                    </div>
                  ))}
                </td>
                <td className="text-xs">{p.workdays.map(d => WEEKDAYS[d]).join(', ')}</td>
                <td>{p.active ? '✓' : '—'}</td>
                <td className="text-right whitespace-nowrap">
                  <Link to={`/performers/${p.id}/edit`} className="text-slate-600 hover:text-slate-900 mr-2">изменить</Link>
                  <button onClick={() => onDelete(p.id)} className="text-rose-500 hover:text-rose-700">удалить</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan="7" className="text-center text-slate-500 py-6">Пока нет исполнителей</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
