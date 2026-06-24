import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { ContentPiece, ContentVersion } from '@/types';

function fetchContent(id: string) {
  return apiClient.get<ContentPiece>(`/content/${id}`).then((res) => res.data);
}

function fetchVersions(id: string) {
  return apiClient
    .get<ContentVersion[]>(`/content/${id}/versions`)
    .then((res) => res.data);
}

export default function ContentDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: content, isLoading: contentLoading } = useQuery({
    queryKey: ['content', id],
    queryFn: () => fetchContent(id!),
    enabled: !!id,
  });

  const { data: versions } = useQuery({
    queryKey: ['content-versions', id],
    queryFn: () => fetchVersions(id!),
    enabled: !!id,
  });

  if (contentLoading) {
    return <div className="text-gray-500">Loading...</div>;
  }

  if (!content) {
    return <div className="text-gray-500">Content not found.</div>;
  }

  return (
    <div className="max-w-4xl">
      <Link to="/content" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to Content
      </Link>

      <h1 className="text-3xl font-bold text-gray-900 mb-2">{content.title}</h1>

      <div className="flex gap-4 mb-8 text-sm text-gray-500">
        <span>Type: {content.content_type.replace(/_/g, ' ')}</span>
        <span>•</span>
        <span>Market: {content.target_market}</span>
        <span>•</span>
        <span>Tone: {content.tone}</span>
        <span>•</span>
        <span>Status: {content.status}</span>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Content</h2>
        <div className="whitespace-pre-wrap text-gray-800 text-sm leading-relaxed">
          {content.content}
        </div>
      </div>

      {versions && versions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Versions ({versions.length})
          </h2>
          <div className="space-y-4">
            {versions.map((version) => (
              <div
                key={version.id}
                className="border border-gray-200 rounded-lg p-4"
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-gray-900">
                    Version {version.version}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(version.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="whitespace-pre-wrap text-gray-700 text-sm">
                  {version.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
