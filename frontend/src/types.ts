export type Role = "learner" | "supervisor" | "sme" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  division_id: number | null;
  frac_role_id: number | null;
  service_years: number;
  totp_enabled: boolean;
  fluency_scoring_enabled: boolean;
}

export interface CompetencyLevel {
  competency_id: number;
  competency_code: string;
  competency_name: string;
  domain: string;
  level: number;
  evidence_count: number;
  evidence_weight: number;
  strongest_source: string | null;
  last_evidence_at: string | null;
  /** False where the evidence is too thin to hold an opinion worth acting on. */
  is_confident: boolean;
}

export interface SkillTwin {
  user: User;
  role_name: string | null;
  role_readiness: number;
  competencies: CompetencyLevel[];
}

export type GapStatus = "critical" | "at_risk" | "near_target" | "met";

export interface Gap {
  competency_id: number;
  competency_code: string;
  competency_name: string;
  domain: string;
  current_level: number;
  required_level: number;
  gap: number;
  criticality: string;
  status: GapStatus;
  evidence_count: number;
  strongest_source: string | null;
  last_evidence_at: string | null;
}

export interface Divergence {
  competency_id: number;
  competency_name: string;
  self_rated_level: number;
  assessed_level: number;
  divergence: number;
}

export interface Evidence {
  id: number;
  user_id: number;
  competency_id: number;
  level_estimate: number;
  confidence: number;
  source: string;
  source_ref: string | null;
  note: string | null;
  created_at: string;
}

export interface FracRole {
  id: number;
  code: string;
  name: string;
  grade: string;
  level_order: number;
  min_service_years: number;
}

export interface Competency {
  id: number;
  code: string;
  name: string;
  domain: string;
  description: string | null;
}

export interface OfficerSummary {
  user_id: number;
  full_name: string;
  email: string;
  role_name: string | null;
  service_years: number;
  readiness: number;
  widest_gap_competency: string | null;
  widest_gap: number;
  critical_gaps: number;
  evidence_count: number;
  fluency_scoring_enabled: boolean;
}

export interface TeamResponse {
  scope: string;
  officers: OfficerSummary[];
  summary: { officers: number; with_critical_gaps: number; mean_readiness: number };
}

export interface AdminOverview {
  officers: number;
  evidence_records: number;
  divisions: number;
  demonstrated_evidence_pct: number;
  by_division: {
    code: string;
    name: string;
    state: string;
    officers: number;
    mean_level: number;
    at_target_pct: number;
  }[];
  by_competency: {
    code: string;
    name: string;
    domain: string;
    mean_level: number;
    mean_required: number;
    at_target_pct: number;
    officers_below_target: number;
  }[];
  by_role: { code: string; name: string; officers: number }[];
  evidence_mix: { source: string; count: number }[];
}

export interface Heatmap {
  divisions: { code: string; name: string }[];
  competencies: { code: string; name: string }[];
  cells: {
    division: string;
    competency: string;
    mean_level: number;
    at_target_pct: number;
    officers: number;
  }[];
}

export interface CompetencyLift {
  competency_id: number;
  competency_code: string;
  competency_name: string;
  level_then: number;
  level_now: number;
  change: number;
  evidence_then: number;
  evidence_added: number;
  direction: "improved" | "declined" | "steady";
}

export interface LiftSummary {
  window_days: number;
  competencies: CompetencyLift[];
  summary: {
    measured: number;
    improved: number;
    declined: number;
    steady: number;
    mean_change: number;
    evidence_added: number;
  };
  note: string;
}

export interface Course {
  id: number;
  external_id: string;
  source: string;
  title: string;
  description: string;
  provider: string | null;
  competency_id: number | null;
  level_from: number;
  level_to: number;
  duration_hours: number;
}

export interface Recommendation {
  id: number;
  course: Course;
  competency_id: number;
  competency_name: string;
  current_level: number;
  required_level: number;
  gap: number;
  score: number;
  /** Each contributing factor, kept separate so the reason can name them. */
  signals: {
    relevance?: number;
    level_fit?: number;
    urgency?: number;
    peers?: number;
    peer_count?: number;
    embedder?: string;
    semantic?: boolean;
  };
  reason: string;
}

export interface PathItem {
  sequence: number;
  status: "locked" | "available" | "in_progress" | "completed";
  included_because: string | null;
  course: Course;
}

export interface LearningPath {
  id: number;
  competency_id: number;
  competency_name: string;
  current_level: number;
  target_level: number;
  /** How far the sequence actually gets — below target when the catalogue
   *  cannot finish the job. */
  reaches_level: number;
  total_hours: number;
  estimated_weeks: number;
  reason: string;
  items: PathItem[];
}

export interface Question {
  id: number;
  material_id: number;
  competency_id: number | null;
  kind: string;
  stem: string;
  options: string[];
  correct_index: number | null;
  explanation: string | null;
  distractor_rationale: string[];
  bloom_level: string;
  citation: { chunk_id: number | null; page: number | null; quote: string | null };
  status: string;
  quality_flags: string[];
  review_note: string | null;
  generated_by_model: string | null;
  times_attempted: number;
  difficulty_p: number | null;
  discrimination: number | null;
  created_at: string;
}

export interface QuestionSource {
  question_id: number;
  material_title: string | null;
  page: number | null;
  quote: string;
  passage: string;
  citation_verified: boolean;
  verification_detail: string;
}

/** One course applied inside a promotion simulation. */
export interface SimulatedStep {
  course_id: number;
  title: string;
  competency_name: string;
  level_before: number;
  level_after: number;
  readiness_after: number;
  readiness_gain: number;
  duration_hours: number;
  /** Present only when the step is worth nothing, explaining why. */
  note: string | null;
}

/** A course the officer chose that does not count toward the target role. */
export interface ExcludedCourse {
  course_id: number;
  title: string | null;
  reason: string;
}

export interface PromotionSimulation {
  target_role: string | null;
  readiness_now: number;
  readiness_projected: number;
  gain: number;
  total_hours: number;
  estimated_weeks: number;
  steps: SimulatedStep[];
  excluded: ExcludedCourse[];
  assumptions: string;
  caveat: string;
  error?: string;
}

export interface ForecastProjection {
  competency_name: string;
  gap: number;
  monthly_rate: number;
  months_to_close: number | null;
  projected_date: string | null;
  note?: string;
}

export interface ReadinessForecast {
  target_role: string | null;
  window_days: number;
  readiness_now: number;
  monthly_rate: number;
  open_gaps: number;
  gaps_on_track: number;
  gaps_stalled: number;
  slowest: ForecastProjection | null;
  projections: ForecastProjection[];
  caveat: string;
}

/** Camera engagement aggregates. Computed in the browser; the only thing sent. */
export interface AttentionSummary {
  screen_gaze_ratio: number | null;
  longest_look_away_seconds: number | null;
  look_away_count: number | null;
  blink_rate_per_minute: number | null;
  head_stability: number | null;
  face_present_ratio: number | null;
  frames_analysed: number;
}

/** What comes back with an answer in the officer's own report. */
export interface AttentionReport extends AttentionSummary {
  quality: "good" | "partial" | "unusable";
  /** Always true — the API refuses to serve this block to anyone else. */
  for_officer: boolean;
  /** Always false. Present so the interface can state it rather than imply it. */
  scored: boolean;
}

/** The next question in an adaptive session. */
export interface NextQuestion {
  done: boolean;
  answer_id: number | null;
  sequence: number | null;
  question: string | null;
  competency_name: string | null;
  asked_because: string | null;
  is_generated: boolean;
  asked: number;
  max_questions: number;
}

/** Advice derived from the interview's own numbers. Never model-written. */
export interface Coaching {
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  practice: string[];
  focus_competency_ids: number[];
  note: string;
}
