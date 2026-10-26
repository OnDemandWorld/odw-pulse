// TypeScript types mirroring the pulse-api Pydantic schemas.
// Keep these in sync with pulse-api/src/pulse/api/schemas/ and
// pulse-api/src/pulse/generation/models.py.

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: string;
  workspace_id?: string | null;
  email?: string | null;
}

export interface RegisterRequest {
  workspace_name: string;
  email: string;
  password: string;
}

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  workspace_id: string;
}

// ---------------------------------------------------------------------------
// Content (schemas/content.py)
// ---------------------------------------------------------------------------

export type ContentStatus = 'draft' | 'review' | 'approved' | 'rejected' | 'archived';

export interface ContentPiece {
  id: string;
  workspace_id: string;
  slug: string;
  title: string;
  body: string | null;
  metadata: Record<string, unknown> | null;
  status: ContentStatus;
  market_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentVersion {
  id: string;
  content_piece_id: string;
  version_number: number;
  body: string | null;
  metadata: Record<string, unknown> | null;
  status: ContentStatus;
  change_note: string | null;
  created_at: string;
  created_by: string | null;
}

// ---------------------------------------------------------------------------
// Generation (generation/models.py)
// ---------------------------------------------------------------------------

export interface GenerateRequest {
  content_type: string;
  target_market: string;
  prompt: string;
  brand_voice_id?: string | null;
  vault_sources?: string[];
  glossary?: Record<string, unknown>[];
  llm_params?: Record<string, unknown>;
  cultural_overrides?: Record<string, unknown>;
}

export interface GenerateResponse {
  content: string;
  quality_score: number;
  quality_flags: string[];
  cultural_directive: Record<string, unknown>;
  llm_model: string;
  llm_usage: Record<string, number>;
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// Bulk jobs (schemas/bulk_job.py)
// ---------------------------------------------------------------------------

export type BulkJobStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface BulkJob {
  id: string;
  workspace_id: string;
  status: BulkJobStatus;
  total: number;
  progress: number;
  input_file: string | null;
  output_file: string | null;
  errors: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Experiments (schemas/experiment.py)
// ---------------------------------------------------------------------------

export type ExperimentStatus = 'draft' | 'running' | 'paused' | 'completed' | 'archived';

export interface ExperimentVariant {
  id: string;
  experiment_id: string;
  name: string;
  weight: number;
  configuration: Record<string, unknown> | null;
  position: number;
}

export interface Experiment {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: ExperimentStatus;
  hypothesis: string | null;
  configuration: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  variants: ExperimentVariant[];
  tracking_urls: Record<string, string> | null;
}

export interface ExperimentVariantCreate {
  name: string;
  weight: number;
  configuration: Record<string, unknown> | null;
  is_control: boolean;
}

export interface ExperimentCreate {
  name: string;
  description?: string | null;
  hypothesis?: string | null;
  configuration?: Record<string, unknown> | null;
  variants: ExperimentVariantCreate[];
}

export interface VariantResult {
  variant_id: string;
  variant_name: string;
  is_control: boolean;
  visitor_count: number;
  impressions: number;
  clicks: number;
  conversions: number;
  conversion_rate: number;
}

export interface StatisticalAnalysis {
  control_variant: string;
  treatment_variant: string;
  p_value: number;
  confidence_level: number;
  effect_size: number;
  is_significant: boolean;
}

export interface WinnerRecommendation {
  recommended_variant: string | null;
  confidence: number;
  reason: string;
}

export interface ExperimentResults {
  experiment_id: string;
  experiment_name: string;
  variant_results: VariantResult[];
  statistical_analyses: StatisticalAnalysis[];
  winner_recommendation: WinnerRecommendation;
}

// ---------------------------------------------------------------------------
// Webhooks (api/v1/integrations.py)
// ---------------------------------------------------------------------------

export interface WebhookConfigRead {
  id: string;
  workspace_id: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

/** List endpoints return { items, total } wrappers, never bare arrays. */
export interface ListResponse<T> {
  items: T[];
  total: number;
}
