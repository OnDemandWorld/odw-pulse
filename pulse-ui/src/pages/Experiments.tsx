import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { Experiment } from '@/types';

function fetchExperiments() {
  return apiClient.get<Experiment[]>('/experiments').then((res) => res.data);
}

export default function Experiments() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [variants, setVariants] = useState([{ name: 'Control', content: '', traffic_percentage: 50 }]);
  const [error, setError] = useState<string | null>(null);

  const { data: experiments, isLoading } = useQuery({
    queryKey: ['experiments'],
    queryFn: fetchExperiments,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      return apiClient.post('/experiments', {
        name,
        description,
        variants,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setName('');
      setDescription('');
      setVariants([{ name: 'Control', content: '', traffic_percentage: 50 }]);
      setShowForm(false);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const addVariant = () => {
    setVariants((prev) => [
      ...prev,
      { name: `Variant ${prev.length}`, content: '', traffic_percentage: 0 },
    ]);
  };

  const updateVariant = (index: number, field: string, value: string | number) => {
    setVariants((prev) =>
      prev.map((v, i) => (i === index ? { ...v, [field]: value } : v))
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-700',
      running: 'bg-blue-100 text-blue-700',
      completed: 'bg-green-100 text-green-700',
      paused: 'bg-yellow-100 text-yellow-700',
    };
    return (
      <span
        className={`px-2 py-1 text-xs font-medium rounded-full ${colors[status] || 'bg-gray-100 text-gray-700'}`}
      >
        {status}
      </span>
    );
  };

  return (
    <div className="max-w-6xl">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Experiments</h1>
          <p className="text-gray-600 mt-1">
            A/B test content variants to optimize performance.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          {showForm ? 'Cancel' : '+ New Experiment'}
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Create Experiment</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-medium text-gray-700">Variants</label>
                <button
                  type="button"
                  onClick={addVariant}
                  className="text-sm text-blue-600 hover:underline"
                >
                  + Add Variant
                </button>
              </div>
              <div className="space-y-3">
                {variants.map((variant, index) => (
                  <div key={index} className="flex gap-3 items-start">
                    <input
                      type="text"
                      value={variant.name}
                      onChange={(e) => updateVariant(index, 'name', e.target.value)}
                      placeholder="Variant name"
                      className="w-1/4 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <textarea
                      value={variant.content}
                      onChange={(e) => updateVariant(index, 'content', e.target.value)}
                      placeholder="Variant content"
                      rows={1}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <input
                      type="number"
                      value={variant.traffic_percentage}
                      onChange={(e) =>
                        updateVariant(index, 'traffic_percentage', Number(e.target.value))
                      }
                      placeholder="Traffic %"
                      className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      min={0}
                      max={100}
                    />
                  </div>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Experiment'}
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </form>
        </div>
      )}

      {/* Experiments List */}
      <div className="space-y-4">
        {isLoading && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
            Loading experiments...
          </div>
        )}

        {experiments && experiments.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
            No experiments yet. Create one to get started.
          </div>
        )}

        {experiments?.map((exp) => (
          <div
            key={exp.id}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{exp.name}</h3>
                <p className="text-sm text-gray-600 mt-1">{exp.description}</p>
              </div>
              {statusBadge(exp.status)}
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-medium text-gray-700">Variants</h4>
              {exp.variants.map((variant) => (
                <div
                  key={variant.id}
                  className="flex justify-between items-center bg-gray-50 rounded-lg px-4 py-2 text-sm"
                >
                  <span className="font-medium text-gray-900">{variant.name}</span>
                  <span className="text-gray-500">{variant.traffic_percentage}% traffic</span>
                </div>
              ))}
            </div>

            {exp.results && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Results</h4>
                <div className="space-y-2">
                  {exp.results.variant_results.map((vr) => (
                    <div
                      key={vr.variant_id}
                      className="flex justify-between items-center text-sm"
                    >
                      <span className="text-gray-900">{vr.variant_name}</span>
                      <div className="flex gap-4 text-gray-500">
                        <span>{vr.impressions} impressions</span>
                        <span>{vr.conversions} conversions</span>
                        <span className="font-medium text-gray-700">
                          {(vr.conversion_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
