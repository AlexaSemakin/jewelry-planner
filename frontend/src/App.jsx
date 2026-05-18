import React from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import OrdersList from './pages/OrdersList.jsx'
import OrderEditor from './pages/OrderEditor.jsx'
import OrderView from './pages/OrderView.jsx'
import PerformersList from './pages/PerformersList.jsx'
import PerformerEditor from './pages/PerformerEditor.jsx'
import RoutesList from './pages/RoutesList.jsx'
import History from './pages/History.jsx'

const NavItem = ({ to, children }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `px-3 py-2 rounded-md text-sm font-medium transition ${
        isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-200'
      }`
    }
  >
    {children}
  </NavLink>
)

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-amber-300 to-gold flex items-center justify-center text-white font-bold text-sm">
              JP
            </div>
            <div className="font-semibold text-slate-800">Jewelry Planner</div>
          </div>
          <nav className="flex gap-1">
            <NavItem to="/">Дашборд</NavItem>
            <NavItem to="/orders">Заказы</NavItem>
            <NavItem to="/performers">Исполнители</NavItem>
            <NavItem to="/routes">Маршруты</NavItem>
            <NavItem to="/history">История</NavItem>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/orders" element={<OrdersList />} />
          <Route path="/orders/new" element={<OrderEditor />} />
          <Route path="/orders/:id/edit" element={<OrderEditor />} />
          <Route path="/orders/:id" element={<OrderView />} />
          <Route path="/performers" element={<PerformersList />} />
          <Route path="/performers/new" element={<PerformerEditor />} />
          <Route path="/performers/:id/edit" element={<PerformerEditor />} />
          <Route path="/routes" element={<RoutesList />} />
          <Route path="/history" element={<History />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 py-3 text-center text-xs text-slate-400">
        Jewelry Production Planner · прототип · {new Date().getFullYear()}
      </footer>
    </div>
  )
}
