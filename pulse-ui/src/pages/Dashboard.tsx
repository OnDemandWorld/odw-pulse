import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { BulkJob, ContentPiece, Experiment, ListResponse } from '@/types';

// limit=1 keeps payloads tiny — we only need `total` for the stat cards.
function fetchTotals() {
  return Promise.all([
    apiClient.get<ListResponse<ContentPiece>>('/content', { params: { limit: 1 } }),
    apiClient.get<ListResponse<Experiment>>('/experiments', { params: { limit: 1 } }),
    apiClient.get<ListResponse<BulkJob>>('/bulk-jobs', { params: { limit: 1 } }),
  ]).then(([content, experiments, jobs]) => ({
    content: content.data.total,
    experiments: experiments.data.total,
    bulkJobs: jobs.data.total,
  }));
}

function fetchRecentContent() {
  return apiClient
    .get<ListResponse<ContentPiece>>('/content', { params: { limit: 5 } })
    .then((res) => res.data.items);
}

export default function Dashboard() {
  const { data: totals, isLoading, error } = useQuery({
    queryKey: ['dashboard-totals'],
    queryFn: fetchTotals,
  });

  const { data: recent } = useQuery({
    queryKey: ['dashboard-recent'],
    queryFn: fetchRecentContent,
  });

  const stats = [
    { label: 'Content Pieces', value: totals?.content },
    { label: 'Experiments', value: totals?.experiments },
    { label: 'Bulk Jobs', value: totals?.bulkJobs },
  ];

  return (
    <div className="max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Welcome to Pulse</h1>
        <p className="text-gray-600 mt-2">
          Your AI-powered content generation and optimization platform.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
          >
            <p className="text-sm font-medium text-gray-500">{stat.label}</p>
            <p className="text-3xl font-bold text-gray-900 mt-2">
              {isLoading ? '…' : (stat.value ?? '—')}
            </p>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          Failed to load dashboard data. Is the API running and are you signed in?
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-4">
          <Link
            to="/generate"
            className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <span className="mr-2">✨</span>
            Generate Content
          </Link>
          <Link
            to="/experiments"
            className="inline-flex items-center px-6 py-3 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium"
          >
            <span className="mr-2">🧪</span>
            Create Experiment
          </Link>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Content</h2>
        {recent && recent.length > 0 ? (
          <ul className="divide-y divide-gray-100">
            {recent.map((item) => (
              <li key={item.id} className="py-2 flex justify-between items-center text-sm">
                <Link to={`/content/${item.id}`} className="text-blue-600 hover:underline">
                  {item.title}
                </Link>
                <span className="text-gray-400 text-xs">
                  {new Date(item.updated_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-gray-500 text-sm">
            No content yet —{' '}
            <Link to="/generate" className="text-blue-600 hover:underline">
              generate your first piece
            </Link>
            .
          </div>
        )}
      </div>
    </div>
  );
}
