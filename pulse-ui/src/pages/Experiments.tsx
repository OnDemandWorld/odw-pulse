import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient, { apiErrorMessage } from '@/api/client';
import {
  Experiment,
  ExperimentResults,
  ExperimentStatus,
  ExperimentVariantCreate,
  ListResponse,
} from '@/types';

function fetchExperiments() {
  return apiClient
    .get<ListResponse<Experiment>>('/experiments')
    .then((res) => res.data.items);
}

function fetchResults(experimentId: string) {
  return apiClient
    .get<ExperimentResults>(`/experiments/${experimentId}/results`)
    .then((res) => res.data);
}

// ---------------------------------------------------------------------------
// Create-form variant draft (relative weights; first variant is the control)
// ---------------------------------------------------------------------------

interface VariantDraft {
  key: string;
  name: string;
  weight: number;
  content: string;
}

function newVariantDraft(name: string, weight: number): VariantDraft {
  return { key: crypto.randomUUID(), name, weight, content: '' };
}

const STATUS_COLORS: Record<ExperimentStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  paused: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  archived: 'bg-gray-100 text-gray-400',
};

// ---------------------------------------------------------------------------
// Single experiment card with lifecycle actions + on-demand results
// ---------------------------------------------------------------------------


function ExperimentCard({ experiment }: { experiment: Experiment }) {
  const queryClient = useQueryClient();
  const [showResults, setShowResults] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const resultsQuery = useQuery({
    queryKey: ['experiment-results', experiment.id],
    queryFn: () => fetchResults(experiment.id),
    enabled: showResults,
  });

  const lifecycleMutation = useMutation({
    mutationFn: async (action: 'start' | 'pause' | 'stop') => {
      await apiClient.post(`/experiments/${experiment.id}/${action}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(apiErrorMessage(err, 'Action failed'));
    },
  });

  const totalWeight = experiment.variants.reduce((sum, v) => sum + v.weight, 0);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{experiment.name}</h3>
          {experiment.description && (
            <p className="text-sm text-gray-600 mt-1">{experiment.description}</p>
          )}
        </div>
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${
            STATUS_COLORS[experiment.status] ?? 'bg-gray-100 text-gray-700'
          }`}
        >
          {experiment.status}
        </span>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Variants</h4>
        {experiment.variants.map((variant) => (
          <div
            key={variant.id}
            className="flex justify-between items-center bg-gray-50 rounded-lg px-4 py-2 text-sm"
          >
            <span className="font-medium text-gray-900">{variant.name}</span>
            <span className="text-gray-500">
              weight {variant.weight}
              {totalWeight > 0 &&
                ` · ${Math.round((variant.weight / totalWeight) * 100)}% traffic`}
            </span>
          </div>
        ))}
      </div>

      {/* Lifecycle actions */}
      <div className="mt-4 flex flex-wrap gap-2">
        {experiment.status === 'draft' && (
          <button
            onClick={() => lifecycleMutation.mutate('start')}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            disabled={lifecycleMutation.isPending}
          >
            Start
          </button>
        )}
        {experiment.status === 'running' && (
          <button
            onClick={() => lifecycleMutation.mutate('pause')}
            className="px-4 py-1.5 text-sm bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50"
            disabled={lifecycleMutation.isPending}
          >
            Pause
          </button>
        )}
        {(experiment.status === 'running' || experiment.status === 'paused') && (
          <>
            <button
              onClick={() => lifecycleMutation.mutate('stop')}
              className="px-4 py-1.5 text-sm bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
              disabled={lifecycleMutation.isPending}
            >
              Stop
            </button>
            <button
              onClick={() => setShowResults(!showResults)}
              className="px-4 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              {showResults ? 'Hide Results' : 'View Results'}
            </button>
          </>
        )}
        {experiment.status === 'completed' && (
          <button
            onClick={() => setShowResults(!showResults)}
            className="px-4 py-1.5 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
          >
            {showResults ? 'Hide Results' : 'View Results'}
          </button>
        )}
      </div>
      {actionError && <p className="text-sm text-red-600 mt-2">{actionError}</p>}

      {showResults && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Results</h4>
          {resultsQuery.isLoading && (
            <p className="text-sm text-gray-500">Loading results...</p>
          )}
          {resultsQuery.error && (
            <p className="text-sm text-red-600">
              Failed to load results — performance events may not be tracked yet.
            </p>
          )}
          {resultsQuery.data && (
            <div className="space-y-2">
              {resultsQuery.data.variant_results.map((vr) => (
                <div
                  key={vr.variant_id}
                  className="flex justify-between items-center text-sm"
                >
                  <span className="text-gray-900">
                    {vr.variant_name}
                    {vr.is_control && (
                      <span className="ml-2 text-xs text-gray-400">(control)</span>
                    )}
                  </span>
                  <div className="flex gap-4 text-gray-500">
                    <span>{vr.visitor_count} visitors</span>
                    <span>{vr.conversions} conversions</span>
                    <span className="font-medium text-gray-700">
                      {(vr.conversion_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
              <div className="mt-2 p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-900">
                Recommendation:{' '}
                {resultsQuery.data.winner_recommendation.recommended_variant
                  ? `${resultsQuery.data.winner_recommendation.recommended_variant} (${Math.round(
                      resultsQuery.data.winner_recommendation.confidence * 100
                    )}% confidence)`
                  : 'No winner yet'}
                {resultsQuery.data.winner_recommendation.reason &&
                  ` — ${resultsQuery.data.winner_recommendation.reason}`}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------


export default function Experiments() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [variants, setVariants] = useState<VariantDraft[]>([
    newVariantDraft('Control', 1),
  ]);
  const [error, setError] = useState<string | null>(null);

  const { data: experiments, isLoading, error: queryError } = useQuery({
    queryKey: ['experiments'],
    queryFn: fetchExperiments,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const payloadVariants: ExperimentVariantCreate[] = variants.map((v, index) => ({
        name: v.name,
        weight: v.weight,
        configuration: v.content ? { content: v.content } : null,
        is_control: index === 0,
      }));
      return apiClient.post('/experiments', {
        name,
        description: description || null,
        hypothesis: hypothesis || null,
        variants: payloadVariants,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setName('');
      setDescription('');
      setHypothesis('');
      setVariants([newVariantDraft('Control', 1)]);
      setShowForm(false);
      setError(null);
    },
    onError: (err: unknown) => {
      setError(apiErrorMessage(err, 'Failed to create experiment'));
    },
  });

  const addVariant = () => {
    setVariants((prev) => [...prev, newVariantDraft(`Variant ${prev.length}`, 1)]);
  };

  const updateVariant = (key: string, field: keyof VariantDraft, value: string | number) => {
    setVariants((prev) =>
      prev.map((v) => (v.key === key ? { ...v, [field]: value } : v))
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Hypothesis
              </label>
              <input
                type="text"
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="e.g., Shorter headlines increase click-through rate"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-medium text-gray-700">
                  Variants (relative weights)
                </label>
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
                  <div key={variant.key} className="flex gap-3 items-start">
                    <input
                      type="text"
                      value={variant.name}
                      onChange={(e) => updateVariant(variant.key, 'name', e.target.value)}
                      placeholder="Variant name"
                      className="w-1/4 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <textarea
                      value={variant.content}
                      onChange={(e) => updateVariant(variant.key, 'content', e.target.value)}
                      placeholder="Variant content (stored in variant configuration)"
                      rows={1}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <input
                      type="number"
                      value={variant.weight}
                      onChange={(e) =>
                        updateVariant(variant.key, 'weight', Number(e.target.value))
                      }
                      title="Relative traffic weight"
                      className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      min={0}
                      step={0.5}
                    />
                    {index === 0 && (
                      <span className="text-xs text-gray-400 self-center whitespace-nowrap">
                        control
                      </span>
                    )}
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

        {queryError && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-red-600">
            Failed to load experiments. Make sure the API is running and you are signed in.
          </div>
        )}

        {experiments && experiments.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
            No experiments yet. Create one to get started.
          </div>
        )}

        {experiments?.map((exp) => <ExperimentCard key={exp.id} experiment={exp} />)}
      </div>
    </div>
  );
}
