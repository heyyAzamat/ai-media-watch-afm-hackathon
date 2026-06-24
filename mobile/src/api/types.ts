/**
 * Wire types mirroring the AI Media Watch backend contract
 * (src/aimw/domain/schemas.py + domain/models.py + domain/enums.py).
 *
 * Kept in sync by hand — if the backend schema changes, update this file.
 */

// ── Enums ──────────────────────────────────────────────────────────────────
export type JobStatus =
  | 'queued'
  | 'ingesting'
  | 'extracting'
  | 'analyzing'
  | 'fusing'
  | 'judging'
  | 'reporting'
  | 'completed'
  | 'failed';

export const TERMINAL_STATUSES: JobStatus[] = ['completed', 'failed'];

export type RiskCategory =
  | 'illegal_gambling'
  | 'casino_advertising'
  | 'sports_betting'
  | 'pyramid_scheme'
  | 'ponzi_scheme'
  | 'guaranteed_income'
  | 'referral_scam'
  | 'fake_investment'
  | 'financial_manipulation'
  | 'hidden_advertising'
  | 'suspicious_financial'
  | 'none';

export type Severity = 'low' | 'medium' | 'high';

export type EvidenceSource = 'ocr' | 'speech' | 'visual';

// ── Responses ───────────────────────────────────────────────────────────────
export interface JobAccepted {
  job_id: string;
  video_id: string;
  status: JobStatus;
  poll_url: string;
  created_at: string;
}

export interface JobStatusResponse {
  job_id: string;
  video_id: string;
  status: JobStatus;
  progress: number; // 0..100
  stage_detail: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface RiskResponse {
  video_id: string;
  risk_score: number; // 0..100
  category: RiskCategory;
  confidence: number; // 0..1
  summary: string;
  fallback_used: boolean;
}

// ── Report sub-models ─────────────────────────────────────────────────────────
export interface VideoMetadata {
  video_id: string;
  filename: string;
  source_platform: string;
  source_url: string | null;
  duration_seconds: number;
  fps: number;
  width: number;
  height: number;
  size_bytes: number;
  container: string;
  uploaded_at: string;
}

export interface TimelineEvent {
  start: number;
  end: number;
  severity: Severity;
  category: RiskCategory;
  confidence: number;
  evidence: string[];
  sources: EvidenceSource[];
}

export interface EvidencePlayerMarker {
  timestamp: number;
  label: string;
  severity: Severity;
  icon: string; // 🔴 / 🟠 / 🟡
  display_time: string; // "00:32"
}

export interface VisualDetection {
  timestamp: number;
  frame_id: string | null;
  scores: Record<string, number>;
  evidence: string[];
}

export interface TextRiskEvidence {
  timestamp: number;
  end: number | null;
  source: EvidenceSource;
  category: RiskCategory;
  confidence: number;
  text: string;
  matched_terms: string[];
}

export interface EvidenceBundle {
  visual: VisualDetection[];
  audio: TextRiskEvidence[];
  ocr: TextRiskEvidence[];
}

export interface AnalysisReport {
  video_id: string;
  risk_score: number;
  category: RiskCategory;
  confidence: number;
  summary: string;
  explanation: string;
  timeline: TimelineEvent[];
  player_markers: EvidencePlayerMarker[];
  evidence: EvidenceBundle;
  metadata: VideoMetadata | null;
  fallback_used: boolean;
  llm_called: boolean;
  generated_at: string;
}

export interface ReportResponse {
  video_id: string;
  report: AnalysisReport;
  metadata: VideoMetadata | null;
}

export interface ErrorResponse {
  error: string;
  detail?: string | null;
  request_id?: string | null;
}
