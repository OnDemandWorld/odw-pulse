import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import apiClient from '@/api/client';
import { ContentPiece, ContentStatus, ListResponse } from '@/types';

function fetchContent() {
  return apiClient
    .get<ListResponse<ContentPiece>>('/content')
    .then((res) => res.data.items);
}

const STATUS_COLORS: Record<ContentStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  review: 'bg-purple-100 text-purple-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  archived: 'bg-yellow-100 text-yellow-700',
};

export default function ContentList() {
  const { data: content, isLoading, error } = useQuery({
    queryKey: ['content'],
    queryFn: fetchContent,
  });

  return (
    <div className="max-w-6xl">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Content</h1>
          <p className="text-gray-600 mt-1">All your generated content in one place.</p>
        </div>
        <Link
          to="/generate"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          + New Content
        </Link>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {isLoading && (
          <div className="p-8 text-center text-gray-500">Loading content...</div>
        )}

        {error && (
          <div className="p-8 text-center text-red-600">
            Failed to load content. Make sure the API is running and you are signed in.
          </div>
        )}

        {content && content.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            No content yet.{' '}
            <Link to="/generate" className="text-blue-600 hover:underline">
              Generate your first piece
            </Link>
            .
          </div>
        )}

        {content && content.length > 0 && (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Title
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Market
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {content.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <Link
                      to={`/content/${item.id}`}
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {item.title}
                    </Link>
                    <p className="text-xs text-gray-400 mt-0.5">{item.slug}</p>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        STATUS_COLORS[item.status] ?? 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    {item.market_code ?? '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(item.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
