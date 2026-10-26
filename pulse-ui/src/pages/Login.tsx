import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import apiClient, { apiErrorMessage } from '@/api/client';
import { RegisterRequest, TokenResponse } from '@/types';

type Mode = 'signin' | 'register';

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('signin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (localStorage.getItem('pulse_token')) {
    return <Navigate to="/" replace />;
  }

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response =
        mode === 'signin'
          ? await apiClient.post<TokenResponse>('/auth/login', { username, password })
          : await apiClient.post<TokenResponse>('/auth/register', {
              workspace_name: workspaceName,
              email,
              password: newPassword,
            } satisfies RegisterRequest);
      localStorage.setItem('pulse_token', response.data.access_token);
      navigate('/', { replace: true });
    } catch (err) {
      setError(
        apiErrorMessage(err, mode === 'signin' ? 'Login failed' : 'Could not create workspace')
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Pulse</h1>
          <p className="text-sm text-gray-500 mb-6">
            {mode === 'signin'
              ? 'Sign in to your content platform workspace.'
              : 'Create a workspace to get started.'}
          </p>

          <div className="grid grid-cols-2 gap-1 mb-6 bg-gray-100 rounded-lg p-1 text-sm font-medium">
            <button
              type="button"
              onClick={() => switchMode('signin')}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                mode === 'signin' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => switchMode('register')}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                mode === 'register' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
              }`}
            >
              Create workspace
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Workspace name
                </label>
                <input
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  placeholder="Acme Marketing"
                  autoComplete="organization"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={mode === 'signin' ? username : email}
                onChange={(e) => (mode === 'signin' ? setUsername(e.target.value) : setEmail(e.target.value))}
                placeholder="you@example.com"
                autoComplete="username"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={mode === 'signin' ? password : newPassword}
                onChange={(e) =>
                  mode === 'signin' ? setPassword(e.target.value) : setNewPassword(e.target.value)
                }
                placeholder="••••••••"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                minLength={mode === 'register' ? 8 : undefined}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
              {mode === 'register' && (
                <p className="text-xs text-gray-400 mt-1">At least 8 characters.</p>
              )}
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? mode === 'signin'
                  ? 'Signing in...'
                  : 'Creating workspace...'
                : mode === 'signin'
                  ? 'Sign in'
                  : 'Create workspace'}
            </button>
          </form>
        </div>

        <p className="text-xs text-gray-400 text-center mt-4">
          {mode === 'signin' ? (
            <>
              New here? Use{' '}
              <button
                type="button"
                onClick={() => switchMode('register')}
                className="text-blue-600 hover:underline font-medium"
              >
                Create workspace
              </button>{' '}
              to set up an account and workspace in one step.
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => switchMode('signin')}
                className="text-blue-600 hover:underline font-medium"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
