import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient, { apiErrorMessage } from '@/api/client';
import { BulkJob, BulkJobStatus, ListResponse } from '@/types';

function fetchBulkJobs() {
  return apiClient
    .get<ListResponse<BulkJob>>('/bulk-jobs')
    .then((res) => res.data.items);
}

interface BulkJobForm {
  prompt_column: string;
  content_type: string;
  target_market: string;
}

const STATUS_COLORS: Record<BulkJobStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  succeeded: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
};

export default function BulkJobs() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState<BulkJobForm>({
    prompt_column: 'prompt',
    content_type: 'blog_post',
    target_market: 'en-US',
  });
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: jobs, isLoading, error: queryError } = useQuery({
    queryKey: ['bulk-jobs'],
    queryFn: fetchBulkJobs,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      if (file) formData.append('file', file);
      formData.append('prompt_column', form.prompt_column);
      formData.append('content_type', form.content_type);
      formData.append('target_market', form.target_market);
      // Let axios/the browser set the multipart boundary — do NOT set
      // Content-Type manually here.
      return apiClient.post('/bulk-jobs', formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulk-jobs'] });
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setError(null);
    },
    onError: (err: unknown) => {
      setError(apiErrorMessage(err, 'Failed to create bulk job'));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    createMutation.mutate();
  };

  const downloadResults = async (job: BulkJob) => {
    const response = await apiClient.get(`/bulk-jobs/${job.id}/download`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data as Blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `bulk_job_${job.id}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Bulk Jobs</h1>
      <p className="text-gray-600 mb-8">
        Upload CSV files to generate content in bulk.
      </p>

      {/* Create Job Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Create New Job</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CSV File</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 file:font-medium file:text-sm"
              required
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Prompt Column
              </label>
              <input
                type="text"
                value={form.prompt_column}
                onChange={(e) => setForm((f) => ({ ...f, prompt_column: e.target.value }))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Content Type
              </label>
              <input
                type="text"
                value={form.content_type}
                onChange={(e) => setForm((f) => ({ ...f, content_type: e.target.value }))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Market
              </label>
              <input
                type="text"
                value={form.target_market}
                onChange={(e) => setForm((f) => ({ ...f, target_market: e.target.value }))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
          >
            {createMutation.isPending ? 'Uploading...' : 'Create Job'}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
      </div>

      {/* Jobs List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">All Jobs</h2>
        </div>

        {isLoading && (
          <div className="p-8 text-center text-gray-500">Loading jobs...</div>
        )}

        {queryError && (
          <div className="p-8 text-center text-red-600">
            Failed to load bulk jobs. Make sure the API is running and you are signed in.
          </div>
        )}

        {jobs && jobs.length === 0 && (
          <div className="p-8 text-center text-gray-500">No bulk jobs yet.</div>
        )}

        {jobs && jobs.length > 0 && (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Job
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Output
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-mono text-xs text-gray-700">
                    {job.id.slice(0, 8)}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        STATUS_COLORS[job.status] ?? 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {job.status}
                    </span>
                    {job.errors && Object.keys(job.errors).length > 0 && (
                      <span className="ml-2 text-xs text-red-600">
                        {Object.keys(job.errors).length} row error(s)
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    {job.progress} / {job.total}
                    {job.total > 0 && (
                      <span className="text-gray-400 ml-1">
                        ({Math.round((job.progress / job.total) * 100)}%)
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {job.output_file ? (
                      <button
                        onClick={() => downloadResults(job)}
                        className="text-blue-600 hover:underline"
                      >
                        Download CSV
                      </button>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
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
