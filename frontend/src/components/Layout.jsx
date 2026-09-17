import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  Play,
  BarChart3,
  Settings,
  Cpu,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/ingest', icon: Upload, label: 'Ingest Data' },
  { to: '/pipeline', icon: Play, label: 'Pipeline' },
  { to: '/results', icon: BarChart3, label: 'Results' },
  { to: '/config', icon: Settings, label: 'Configuration' },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-page">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside className="flex flex-col w-64 min-w-64 h-full bg-bg-page border-r border-border-default">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-border-default">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-accent text-white">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide text-text-primary">HUIM Pipeline</h1>
            <p className="text-[10px] font-medium text-text-muted tracking-widest uppercase">Incremental Mining</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent text-white'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
                }`
              }
            >
              <Icon className="w-[18px] h-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border-default">
          <p className="text-[10px] text-text-muted">v0.1.0 · FastAPI + React</p>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-bg-card">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
