/**
 * Thin typed client for the AI Media Watch API.
 *
 * Flow: POST /analyze (multipart) -> 202 JobAccepted; poll GET /status/{job_id};
 * once completed, fetch GET /report|risk|timeline|evidence/{id}.
 */

import { API_PREFIX } from '@/constants/config';
import { getApiBaseUrl } from '@/storage/settings';
import type {
  ErrorResponse,
  JobAccepted,
  JobStatusResponse,
  ReportResponse,
  RiskResponse,
} from './types';

export class ApiError extends Error {
  status: number;
  detail?: string | null;
  constructor(message: string, status: number, detail?: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function apiUrl(path: string): Promise<string> {
  const base = await getApiBaseUrl();
  return `${base}${API_PREFIX}${path}`;
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  let detail: string | null | undefined;
  try {
    const body = (await res.json()) as ErrorResponse;
    message = body.error || message;
    detail = body.detail;
  } catch {
    // non-JSON body; keep generic message
  }
  return new ApiError(message, res.status, detail);
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(await apiUrl(path), { headers: { Accept: 'application/json' } });
  } catch (e) {
    throw new ApiError(
      `Cannot reach the API. Check the server is running and the URL in Settings.`,
      0,
      e instanceof Error ? e.message : String(e),
    );
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

export interface AnalyzeUrlInput {
  kind: 'url';
  sourceUrl: string;
  sourcePlatform: string;
  webhookUrl?: string;
}

export interface AnalyzeFileInput {
  kind: 'file';
  uri: string;
  name: string;
  mimeType?: string;
  sourcePlatform?: string;
}

export type AnalyzeInput = AnalyzeUrlInput | AnalyzeFileInput;

export async function submitAnalyze(input: AnalyzeInput): Promise<JobAccepted> {
  const form = new FormData();
  if (input.kind === 'url') {
    form.append('source_url', input.sourceUrl);
    form.append('source_platform', input.sourcePlatform || 'upload');
    if (input.webhookUrl) form.append('webhook_url', input.webhookUrl);
  } else {
    // React Native FormData file shape.
    form.append('file', {
      uri: input.uri,
      name: input.name,
      type: input.mimeType || 'video/mp4',
    } as unknown as Blob);
    form.append('source_platform', input.sourcePlatform || 'upload');
  }

  let res: Response;
  try {
    // Do NOT set Content-Type; fetch sets the multipart boundary itself.
    res = await fetch(await apiUrl('/analyze'), { method: 'POST', body: form });
  } catch (e) {
    throw new ApiError(
      `Cannot reach the API. Check the server is running and the URL in Settings.`,
      0,
      e instanceof Error ? e.message : String(e),
    );
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as JobAccepted;
}

export function getStatus(jobId: string): Promise<JobStatusResponse> {
  return getJson<JobStatusResponse>(`/status/${encodeURIComponent(jobId)}`);
}

export function getReport(id: string): Promise<ReportResponse> {
  return getJson<ReportResponse>(`/report/${encodeURIComponent(id)}`);
}

export function getRisk(id: string): Promise<RiskResponse> {
  return getJson<RiskResponse>(`/risk/${encodeURIComponent(id)}`);
}
