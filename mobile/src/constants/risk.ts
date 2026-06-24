/**
 * Risk presentation helpers: human labels, colors and time formatting for the
 * categories / severities / scores defined by the backend taxonomy.
 */

import type { JobStatus, RiskCategory, Severity } from '@/api/types';

// Thresholds mirror the backend's REVIEW=40 / ESCALATE=70 bands.
export const REVIEW_THRESHOLD = 40;
export const ESCALATE_THRESHOLD = 70;

export type RiskBand = 'clear' | 'review' | 'escalate';

export function riskBand(score: number): RiskBand {
  if (score >= ESCALATE_THRESHOLD) return 'escalate';
  if (score >= REVIEW_THRESHOLD) return 'review';
  return 'clear';
}

interface BandStyle {
  fg: string;
  bg: string;
  label: string;
}

export const BAND_STYLES: Record<RiskBand, BandStyle> = {
  clear: { fg: '#067647', bg: '#ECFDF3', label: 'Clear' },
  review: { fg: '#B54708', bg: '#FFFAEB', label: 'Review' },
  escalate: { fg: '#B42318', bg: '#FEF3F2', label: 'Escalate' },
};

export function scoreStyle(score: number): BandStyle {
  return BAND_STYLES[riskBand(score)];
}

const SEVERITY_STYLES: Record<Severity, BandStyle> = {
  low: BAND_STYLES.clear,
  medium: BAND_STYLES.review,
  high: BAND_STYLES.escalate,
};

export function severityStyle(severity: Severity): BandStyle {
  return SEVERITY_STYLES[severity];
}

export function severityIcon(severity: Severity): string {
  return severity === 'high' ? '🔴' : severity === 'medium' ? '🟠' : '🟡';
}

const CATEGORY_LABELS: Record<RiskCategory, string> = {
  illegal_gambling: 'Illegal gambling',
  casino_advertising: 'Casino advertising',
  sports_betting: 'Sports betting',
  pyramid_scheme: 'Pyramid scheme',
  ponzi_scheme: 'Ponzi scheme',
  guaranteed_income: 'Guaranteed income',
  referral_scam: 'Referral scam',
  fake_investment: 'Fake investment',
  financial_manipulation: 'Financial manipulation',
  hidden_advertising: 'Hidden advertising',
  suspicious_financial: 'Suspicious financial',
  none: 'No risk detected',
};

export function categoryLabel(category: RiskCategory): string {
  return CATEGORY_LABELS[category] ?? category;
}

interface StatusStyle {
  fg: string;
  bg: string;
  label: string;
}

const STATUS_STYLES: Record<JobStatus, StatusStyle> = {
  queued: { fg: '#475467', bg: '#F2F4F7', label: 'Queued' },
  ingesting: { fg: '#1849A9', bg: '#EFF8FF', label: 'Ingesting' },
  extracting: { fg: '#1849A9', bg: '#EFF8FF', label: 'Extracting' },
  analyzing: { fg: '#1849A9', bg: '#EFF8FF', label: 'Analyzing' },
  fusing: { fg: '#1849A9', bg: '#EFF8FF', label: 'Fusing' },
  judging: { fg: '#5925DC', bg: '#F4F3FF', label: 'Judging' },
  reporting: { fg: '#5925DC', bg: '#F4F3FF', label: 'Reporting' },
  completed: { fg: '#067647', bg: '#ECFDF3', label: 'Completed' },
  failed: { fg: '#B42318', bg: '#FEF3F2', label: 'Failed' },
};

export function statusStyle(status: JobStatus): StatusStyle {
  return STATUS_STYLES[status] ?? STATUS_STYLES.queued;
}

export function sourceLabel(source: string): string {
  if (source === 'ocr') return 'On-screen text';
  if (source === 'speech') return 'Speech';
  if (source === 'visual') return 'Visual';
  return source;
}

/** Seconds (float) -> "m:ss" or "h:mm:ss". */
export function formatSeconds(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
