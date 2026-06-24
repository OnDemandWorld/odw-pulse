export interface ContentPiece {
  id: string;
  title: string;
  content_type: string;
  target_market: string;
  tone: string;
  model: string;
  status: 'draft' | 'approved' | 'published' | 'archived';
  content: string;
  brief: string;
  created_at: string;
  updated_at: string;
  versions?: ContentVersion[];
}

export interface ContentVersion {
  id: string;
  content_id: string;
  version: number;
  content: string;
  created_at: string;
}

export interface Experiment {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'running' | 'completed' | 'paused';
  variants: Variant[];
  created_at: string;
  updated_at: string;
  results?: ExperimentResults;
}

export interface Variant {
  id: string;
  experiment_id: string;
  name: string;
  content: string;
  traffic_percentage: number;
}

export interface ExperimentResults {
  experiment_id: string;
  variant_results: VariantResult[];
  winner?: string;
}

export interface VariantResult {
  variant_id: string;
  variant_name: string;
  impressions: number;
  conversions: number;
  conversion_rate: number;
}

export interface BulkJob {
  id: string;
  name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_items: number;
  processed_items: number;
  failed_items: number;
  created_at: string;
  updated_at: string;
  csv_file?: string;
}

export interface GenerateRequest {
  content_type: string;
  target_market: string;
  brief: string;
  tone: string;
  model: string;
}

export interface GenerateResponse {
  content: string;
  metadata: {
    model: string;
    tokens_used: number;
    duration_ms: number;
  };
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}
