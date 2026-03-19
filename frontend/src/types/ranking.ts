export interface CropSummary {
  id: number;
  crop_name: string;
  scientific_name: string | null;
}

export interface FieldExplanation {
  short_explanation: string;
  detailed_explanation: string;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
}

export interface ScoreComponentRead {
  key: string;
  label: string;
  weight: number;
  awarded_points: number;
  max_points: number;
  status:
    | "ideal"
    | "acceptable"
    | "limited"
    | "unconstrained"
    | "missing"
    | "blocked";
  reasons: string[];
}

export interface ScoreBlockerRead {
  code: string;
  dimension: string;
  message: string;
}

export interface RankedFieldRecommendation {
  rank: number;
  field_id: number;
  field_name: string;
  total_score: number;
  breakdown: Record<string, ScoreComponentRead>;
  blockers: ScoreBlockerRead[];
  reasons: string[];
  explanation: FieldExplanation;
}

export interface RankFieldsResponse {
  crop: CropSummary;
  total_fields_evaluated: number;
  ranked_results: RankedFieldRecommendation[];
}

export interface CropProfileRead extends CropSummary {
  ideal_ph_min: number;
  ideal_ph_max: number;
  tolerable_ph_min: number;
  tolerable_ph_max: number;
  water_requirement_level: string;
  drainage_requirement: string;
  frost_sensitivity: string;
  heat_sensitivity: string;
  salinity_tolerance: string | null;
  rooting_depth_cm: number | null;
  slope_tolerance: number | null;
  organic_matter_preference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
