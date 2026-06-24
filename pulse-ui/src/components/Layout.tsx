import { Outlet } from 'react-router-dom';
import NavLink from './NavLink';

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-gray-900">Pulse</h1>
          <p className="text-sm text-gray-500 mt-1">Content Platform</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <NavLink to="/" icon="📊">
            Dashboard
          </NavLink>
          <NavLink to="/generate" icon="✨">
            Generate
          </NavLink>
          <NavLink to="/content" icon="📝">
            Content
          </NavLink>
          <NavLink to="/bulk-jobs" icon="📦">
            Bulk Jobs
          </NavLink>
          <NavLink to="/experiments" icon="🧪">
            Experiments
          </NavLink>
          <NavLink to="/settings" icon="⚙️">
            Settings
          </NavLink>
        </nav>

        <div className="p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500">
            <p>Workspace: Default</p>
            <p className="mt-1">v0.1.0</p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
