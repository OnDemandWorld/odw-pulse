import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient, { apiErrorMessage } from '@/api/client';
import { UserProfile, WebhookConfigRead } from '@/types';

function fetchMe() {
  return apiClient.get<UserProfile>('/auth/me').then((res) => res.data);
}

function fetchWebhooks() {
  return apiClient.get<WebhookConfigRead[]>('/webhooks').then((res) => res.data);
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [events, setEvents] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data: me } = useQuery({ queryKey: ['me'], queryFn: fetchMe });

  const { data: webhooks, isLoading, error: webhooksError } = useQuery({
    queryKey: ['webhooks'],
    queryFn: fetchWebhooks,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/webhooks', {
        url,
        signing_secret: secret,
        events: events
          .split(',')
          .map((e) => e.trim())
          .filter(Boolean),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setUrl('');
      setSecret('');
      setEvents('');
      setFormError(null);
    },
    onError: (err: unknown) => {
      setFormError(apiErrorMessage(err, 'Failed to register webhook'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/webhooks/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });

  const testMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.post<{ status_code: number; ok: boolean }>(
        `/webhooks/${id}/test`
      );
      return response.data;
    },
    onSuccess: (result) => {
      setNotice(
        result.ok
          ? `Test delivered (HTTP ${result.status_code}).`
          : `Test failed — subscriber returned HTTP ${result.status_code}.`
      );
    },
    onError: (err: unknown) => {
      setNotice(apiErrorMessage(err, 'Test dispatch failed'));
    },
  });

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Settings</h1>
      <p className="text-gray-600 mb-8">
        Manage your workspace configuration and integrations.
      </p>

      <div className="space-y-6">
        {/* Workspace */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Workspace</h2>
          {me ? (
            <dl className="space-y-2 text-sm">
              <div className="flex gap-2">
                <dt className="font-medium text-gray-700 w-32">Signed in as</dt>
                <dd className="text-gray-600">{me.email}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="font-medium text-gray-700 w-32">Role</dt>
                <dd className="text-gray-600 capitalize">{me.role}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="font-medium text-gray-700 w-32">Workspace ID</dt>
                <dd className="text-gray-600 font-mono text-xs">{me.workspace_id}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-gray-500">Loading workspace info...</p>
          )}
        </div>

        {/* Webhooks */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Webhooks</h2>
          <p className="text-sm text-gray-500 mb-4">
            Subscribe external services to content lifecycle events. Payloads are
            HMAC-SHA256 signed with the secret you provide.
          </p>

          {isLoading && <p className="text-sm text-gray-500 mb-4">Loading webhooks...</p>}
          {webhooksError && (
            <p className="text-sm text-red-600 mb-4">Failed to load webhooks.</p>
          )}

          {webhooks && webhooks.length > 0 && (
            <ul className="divide-y divide-gray-100 mb-6">
              {webhooks.map((hook) => (
                <li key={hook.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{hook.url}</p>
                    <p className="text-xs text-gray-400">
                      {hook.events.length > 0 ? hook.events.join(', ') : 'all events'}
                      {!hook.is_active && ' · inactive'}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => testMutation.mutate(hook.id)}
                      className="px-3 py-1 text-xs border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      Test
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(hook.id)}
                      className="px-3 py-1 text-xs border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="space-y-3"
          >
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Subscriber URL
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/hooks/pulse"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Signing Secret (min 8 chars)
              </label>
              <input
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                minLength={8}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Events (comma-separated, empty = all)
              </label>
              <input
                type="text"
                value={events}
                onChange={(e) => setEvents(e.target.value)}
                placeholder="content.approved, content.published"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? 'Registering...' : 'Register Webhook'}
            </button>
            {formError && <p className="text-sm text-red-600">{formError}</p>}
            {notice && <p className="text-sm text-gray-600">{notice}</p>}
          </form>
        </div>

        {/* Team Members */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Team Members</h2>
          <p className="text-sm text-gray-500">
            Team management is on the roadmap — user provisioning and role
            assignment are not implemented yet.
          </p>
        </div>
      </div>
    </div>
  );
}
