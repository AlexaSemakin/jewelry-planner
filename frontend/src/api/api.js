const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = ''
    try { detail = (await res.json()).detail || '' } catch {}
    throw new Error(`HTTP ${res.status}: ${detail || res.statusText}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // catalog
  cities:        () => request('/cities'),
  createCity:    (data) => request('/cities', { method: 'POST', body: JSON.stringify(data) }),
  deleteCity:    (id) => request(`/cities/${id}`, { method: 'DELETE' }),
  stageTemplates: () => request('/stage-templates'),
  createTemplate: (d) => request('/stage-templates', { method: 'POST', body: JSON.stringify(d) }),
  performers:    () => request('/performers'),
  performer:     (id) => request(`/performers/${id}`),
  createPerformer: (d) => request('/performers', { method: 'POST', body: JSON.stringify(d) }),
  updatePerformer: (id, d) => request(`/performers/${id}`, { method: 'PUT', body: JSON.stringify(d) }),
  deletePerformer: (id) => request(`/performers/${id}`, { method: 'DELETE' }),
  routes:        () => request('/routes'),
  createRoute:   (d) => request('/routes', { method: 'POST', body: JSON.stringify(d) }),
  deleteRoute:   (id) => request(`/routes/${id}`, { method: 'DELETE' }),
  // orders
  orders:        (status) => request(`/orders${status ? `?status=${status}` : ''}`),
  order:         (id) => request(`/orders/${id}`),
  createOrder:   (d) => request('/orders', { method: 'POST', body: JSON.stringify(d) }),
  updateOrder:   (id, d) => request(`/orders/${id}`, { method: 'PUT', body: JSON.stringify(d) }),
  deleteOrder:   (id) => request(`/orders/${id}`, { method: 'DELETE' }),
  estimateOrder: (id, persist=true) => request(`/orders/${id}/estimate?persist=${persist}`, { method: 'POST' }),
  confirmOrder:  (id) => request(`/orders/${id}/confirm`, { method: 'POST' }),
  startOrder:    (id) => request(`/orders/${id}/start`, { method: 'POST' }),
  replanOrder:   (id) => request(`/orders/${id}/replan`, { method: 'POST' }),
  replanAll:     () => request('/replan', { method: 'POST' }),
  updateStageStatus: (sid, d) => request(`/stages/${sid}/status`, { method: 'PATCH', body: JSON.stringify(d) }),
  plans:         (oid) => request(`/orders/${oid}/plans`),
  activePlan:    (oid) => request(`/orders/${oid}/plans/active`),
  orderHistory:  (oid) => request(`/orders/${oid}/history`),
  // misc
  dashboard:     () => request('/dashboard'),
  settings:      () => request('/settings'),
}
