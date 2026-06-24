import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { getRisk, getStatus } from '@/api/client';
import type { JobStatus, RiskResponse } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import { Badge, Card } from '@/components/ui';
import { scoreStyle, statusStyle } from '@/constants/risk';
import { Spacing } from '@/constants/theme';
import type { TrackedJob } from '@/storage/jobs';

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' · ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function JobRow({ job, refreshKey = 0 }: { job: TrackedJob; refreshKey?: number }) {
  const router = useRouter();
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const s = await getStatus(job.jobId);
      setStatus(s.status);
      if (s.status === 'completed') {
        try {
          setRisk(await getRisk(job.videoId));
        } catch {
          /* report not ready yet */
        }
      }
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [job.jobId, job.videoId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; state updates happen after the awaited request resolves
    load();
  }, [load, refreshKey]);

  const showScore = status === 'completed' && risk;
  const band = showScore ? scoreStyle(risk!.risk_score) : null;
  const sStyle = status ? statusStyle(status) : null;

  return (
    <Pressable
      onPress={() => router.push({ pathname: '/job/[id]', params: { id: job.jobId } })}
      style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}>
      <Card style={styles.card}>
        <View style={styles.left}>
          <ThemedText type="smallBold" numberOfLines={1}>
            {job.label}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
            {job.sourcePlatform} · {formatDate(job.createdAt)}
          </ThemedText>
        </View>
        <View style={styles.right}>
          {loading && !status ? (
            <ActivityIndicator color="#9AA0AC" />
          ) : showScore && band ? (
            <Badge label={`${risk!.risk_score}`} fg={band.fg} bg={band.bg} />
          ) : sStyle ? (
            <Badge label={sStyle.label} fg={sStyle.fg} bg={sStyle.bg} />
          ) : (
            <Badge label="—" fg="#9AA0AC" bg="rgba(255,255,255,0.06)" />
          )}
        </View>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
  },
  left: { flex: 1, gap: 2 },
  right: { alignItems: 'flex-end' },
});
