import { useState } from 'react';
import apiClient from '@/api/client';
import { GenerateRequest, GenerateResponse } from '@/types';

export default function Generate() {
  const [form, setForm] = useState<GenerateRequest>({
    content_type: 'blog_post',
    target_market: '',
    brief: '',
    tone: 'professional',
    model: 'gpt-4',
  });
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const contentTypes = [
    'blog_post',
    'social_media',
    'ad_copy',
    'email',
    'product_description',
    'landing_page',
  ];

  const tones = ['professional', 'casual', 'friendly', 'formal', 'humorous', 'persuasive'];
  const models = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-sonnet', 'claude-3-haiku'];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.post<GenerateResponse>('/generate', form);
      setResult(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Generate Content</h1>
      <p className="text-gray-600 mb-8">
        Use AI to generate high-quality content for your target markets.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Content Type
            </label>
            <select
              name="content_type"
              value={form.content_type}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {contentTypes.map((type) => (
                <option key={type} value={type}>
                  {type.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Target Market
            </label>
            <input
              type="text"
              name="target_market"
              value={form.target_market}
              onChange={handleChange}
              placeholder="e.g., US, UK, DE, FR"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Brief
            </label>
            <textarea
              name="brief"
              value={form.brief}
              onChange={handleChange}
              rows={5}
              placeholder="Describe what you want to generate..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tone
              </label>
              <select
                name="tone"
                value={form.tone}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {tones.map((tone) => (
                  <option key={tone} value={tone}>
                    {tone}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Model
              </label>
              <select
                name="model"
                value={form.model}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Generating...' : 'Generate Content'}
          </button>

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}
        </form>

        {/* Result */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Result</h2>
          {result ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="prose max-w-none">
                <div className="whitespace-pre-wrap text-gray-800 text-sm leading-relaxed">
                  {result.content}
                </div>
              </div>
              <div className="mt-6 pt-4 border-t border-gray-200">
                <div className="flex gap-6 text-xs text-gray-500">
                  <span>Model: {result.metadata.model}</span>
                  <span>Tokens: {result.metadata.tokens_used}</span>
                  <span>Duration: {(result.metadata.duration_ms / 1000).toFixed(1)}s</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-gray-500 text-sm">
              Generated content will appear here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
