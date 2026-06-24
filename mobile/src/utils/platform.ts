/** Infer a source_platform tag from a pasted URL. */
export function inferPlatform(url: string): string {
  const u = url.toLowerCase();
  if (u.includes('tiktok')) return 'tiktok';
  if (u.includes('instagram')) return 'instagram';
  if (u.includes('youtube') || u.includes('youtu.be')) return 'youtube';
  if (u.includes('facebook') || u.includes('fb.watch')) return 'facebook';
  if (u.includes('t.me') || u.includes('telegram')) return 'telegram';
  return 'web';
}

export function isLikelyUrl(value: string): boolean {
  return /^https?:\/\/.+/i.test(value.trim());
}

/** Short, display-friendly form of a URL (host + truncated path). */
export function shortenUrl(url: string, max = 42): string {
  const trimmed = url.replace(/^https?:\/\//i, '').replace(/\/$/, '');
  return trimmed.length > max ? `${trimmed.slice(0, max - 1)}…` : trimmed;
}
