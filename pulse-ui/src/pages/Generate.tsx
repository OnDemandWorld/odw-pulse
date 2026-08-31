import { useState } from 'react';
import apiClient, { apiErrorMessage } from '@/api/client';
import { GenerateResponse } from '@/types';

const CONTENT_TYPES = [
  'blog_post',
  'social_media',
  'ad_copy',
  'email',
  'product_description',
  'landing_page',
];

interface GenerateForm {
  content_type: string;
  target_market: string;
  prompt: string;
  model: string;
}

export default function Generate() {
  const [form, setForm] = useState<GenerateForm>({
    content_type: 'blog_post',
    target_market: 'en-US',
    prompt: '',
    model: '',
  });
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Matches pulse.generation.models.GenerationRequest.
      const response = await apiClient.post<GenerateResponse>('/generate', {
        content_type: form.content_type,
        target_market: form.target_market,
        prompt: form.prompt,
        llm_params: form.model ? { model: form.model } : {},
      });
      setResult(response.data);
    } catch (err) {
      setError(apiErrorMessage(err, 'Generation failed'));
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
              {CONTENT_TYPES.map((type) => (
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
              placeholder="e.g., en-US, de-DE, fr-FR"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Prompt</label>
            <textarea
              name="prompt"
              value={form.prompt}
              onChange={handleChange}
              rows={5}
              placeholder="Describe what you want to generate..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model (optional)
            </label>
            <select
              name="model"
              value={form.model}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Default (fallback router)</option>
              <option value="gpt-4o">gpt-4o (OpenAI)</option>
              <option value="gpt-4o-mini">gpt-4o-mini (OpenAI)</option>
              <option value="claude-sonnet-4-5">claude-sonnet-4-5 (Anthropic)</option>
              <option value="claude-haiku-4-5">claude-haiku-4-5 (Anthropic)</option>
            </select>
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
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-gray-700">
                  Quality score: {result.quality_score}/100
                </span>
                <span className="text-xs text-gray-500">
                  {(result.latency_ms / 1000).toFixed(1)}s
                </span>
              </div>
              {result.quality_flags.length > 0 && (
                <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-xs space-y-1">
                  {result.quality_flags.map((flag) => (
                    <p key={flag}>⚠ {flag}</p>
                  ))}
                </div>
              )}
              <div className="whitespace-pre-wrap text-gray-800 text-sm leading-relaxed">
                {result.content}
              </div>
              <div className="mt-6 pt-4 border-t border-gray-200">
                <div className="flex gap-6 text-xs text-gray-500">
                  <span>Model: {result.llm_model}</span>
                  {result.llm_usage.total_tokens !== undefined && (
                    <span>Tokens: {result.llm_usage.total_tokens}</span>
                  )}
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
