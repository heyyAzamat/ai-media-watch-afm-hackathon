import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * The backend has no "list jobs" endpoint, so the app remembers every job it
 * submits locally. Each entry is enough to render a history row and re-poll.
 */
export interface TrackedJob {
  jobId: string;
  videoId: string;
  label: string; // filename or source URL
  sourcePlatform: string;
  createdAt: string; // ISO
}

const KEY = 'aimw.jobs';

export async function listJobs(): Promise<TrackedJob[]> {
  const raw = await AsyncStorage.getItem(KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as TrackedJob[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function writeJobs(jobs: TrackedJob[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(jobs));
}

export async function addJob(job: TrackedJob): Promise<void> {
  const jobs = await listJobs();
  const next = [job, ...jobs.filter((j) => j.jobId !== job.jobId)];
  await writeJobs(next);
}

export async function removeJob(jobId: string): Promise<void> {
  const jobs = await listJobs();
  await writeJobs(jobs.filter((j) => j.jobId !== jobId));
}

export async function getJob(jobId: string): Promise<TrackedJob | undefined> {
  const jobs = await listJobs();
  return jobs.find((j) => j.jobId === jobId);
}

export async function clearJobs(): Promise<void> {
  await AsyncStorage.removeItem(KEY);
}
