import { Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import NavLink from './NavLink';
import { UserProfile } from '@/types';

function fetchMe() {
  return apiClient.get<UserProfile>('/auth/me').then((res) => res.data);
}

export default function Layout() {
  const navigate = useNavigate();
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
  });

  const handleLogout = () => {
    localStorage.removeItem('pulse_token');
    navigate('/login', { replace: true });
  };

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
          {me ? (
            <div className="text-xs text-gray-500 mb-3">
              <p className="truncate" title={me.email}>
                {me.email}
              </p>
              <p className="mt-1 capitalize">{me.role}</p>
            </div>
          ) : (
            <div className="text-xs text-gray-500 mb-3">Workspace: Default</div>
          )}
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Log out
          </button>
          <p className="text-xs text-gray-400 mt-3">v0.1.0</p>
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
