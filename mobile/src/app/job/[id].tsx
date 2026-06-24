import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { ApiError, getReport, getStatus } from '@/api/client';
import type { AnalysisReport, JobStatusResponse } from '@/api/types';
import { TERMINAL_STATUSES } from '@/api/types';
import { Header, Screen } from '@/components/screen';
import { ScoreRing } from '@/components/score-ring';
import { ThemedText } from '@/components/themed-text';
import { Badge, Button, Card, SectionTitle } from '@/components/ui';
import {
  categoryLabel,
  formatSeconds,
  severityIcon,
  severityStyle,
  sourceLabel,
  statusStyle,
} from '@/constants/risk';
import { POLL_INTERVAL_MS } from '@/constants/config';
import { Accent, Spacing as Space } from '@/constants/theme';

export default function JobScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const jobId = String(id);

  const [status, setStatus] = useState<JobStatusResponse | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    let haveReport = false; // local control flag — avoids stale-closure on `report` state

    async function tick() {
      try {
        const s = await getStatus(jobId);
        if (cancelled) return;
        setStatus(s);
        setError(null);

        if (s.status === 'failed') return; // terminal — no report to fetch

        if (s.status === 'completed') {
          if (!haveReport) {
            try {
              const r = await getReport(jobId);
              if (cancelled) return;
              setReport(r.report);
              haveReport = true;
            } catch {
              /* report not ready yet — retry on next tick */
            }
          }
          if (haveReport) return; // done — stop polling
        }

        timer.current = setTimeout(tick, POLL_INTERVAL_MS);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : 'Could not reach the API. Pull to retry.');
        timer.current = setTimeout(tick, POLL_INTERVAL_MS * 2);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [jobId]);

  const isRunning = status != null && !TERMINAL_STATUSES.includes(status.status);
  const failed = status?.status === 'failed';

  return (
    <Screen>
      <Header title="Analysis" onBack={() => router.back()} />

      {error && !status ? (
        <Card style={styles.center}>
          <ThemedText style={{ color: '#FF6A5E' }}>{error}</ThemedText>
        </Card>
      ) : null}

      {status == null && !error ? (
        <View style={styles.center}>
          <ActivityIndicator color="#FFFFFF" />
        </View>
      ) : null}

      {/* In-progress */}
      {(isRunning || (status?.status === 'completed' && !report)) && status ? (
        <ProgressCard status={status} />
      ) : null}

      {/* Failed */}
      {failed ? (
        <Card style={styles.gap}>
          <Badge label="Failed" fg="#B42318" bg="#FEF3F2" />
          <ThemedText type="smallBold">Analysis failed</ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {status?.error ?? 'The job could not be completed.'}
          </ThemedText>
          <Button title="Back home" variant="secondary" onPress={() => router.replace('/')} />
        </Card>
      ) : null}

      {/* Completed report */}
      {report ? <ReportView report={report} /> : null}
    </Screen>
  );
}

function ProgressCard({ status }: { status: JobStatusResponse }) {
  const s = statusStyle(status.status);
  return (
    <Card style={styles.gap}>
      <View style={styles.row}>
        <Badge label={s.label} fg={s.fg} bg={s.bg} />
        <ThemedText type="smallBold">{status.progress}%</ThemedText>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${Math.max(4, status.progress)}%` }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        {status.stage_detail ?? 'Working on it…'}
      </ThemedText>
    </Card>
  );
}

function ReportView({ report }: { report: AnalysisReport }) {
  const confidence = Math.round(report.confidence * 100);
  const markers = report.player_markers;
  const timeline = report.timeline;
  const ev = report.evidence;
  const textEvidence = [...ev.ocr, ...ev.audio].sort((a, b) => a.timestamp - b.timestamp);

  return (
    <View style={styles.report}>
      <View style={styles.heroScore}>
        <ScoreRing score={report.risk_score} category={report.category} />
        <ThemedText type="small" themeColor="textSecondary">
          {confidence}% confidence
          {report.fallback_used ? ' · fallback' : ''}
          {!report.llm_called ? ' · no evidence' : ''}
        </ThemedText>
      </View>

      <Card style={styles.gap}>
        <SectionTitle>Summary</SectionTitle>
        <ThemedText>{report.summary || 'No summary available.'}</ThemedText>
        {report.explanation ? (
          <ThemedText type="small" themeColor="textSecondary">
            {report.explanation}
          </ThemedText>
        ) : null}
      </Card>

      {markers.length > 0 ? (
        <View style={styles.section}>
          <SectionTitle>Evidence player</SectionTitle>
          <Card style={{ gap: Space.three }}>
            {markers.map((m, i) => {
              const st = severityStyle(m.severity);
              return (
                <View key={`${m.timestamp}-${i}`} style={styles.markerRow}>
                  <ThemedText style={styles.markerIcon}>{m.icon || severityIcon(m.severity)}</ThemedText>
                  <View style={styles.flex}>
                    <ThemedText type="smallBold">{m.label}</ThemedText>
                  </View>
                  <Badge label={m.display_time} fg={st.fg} bg={st.bg} />
                </View>
              );
            })}
          </Card>
        </View>
      ) : null}

      {timeline.length > 0 ? (
        <View style={styles.section}>
          <SectionTitle>Timeline</SectionTitle>
          <View style={{ gap: Space.two }}>
            {timeline.map((t, i) => {
              const st = severityStyle(t.severity);
              return (
                <Card key={i} style={styles.gapSm}>
                  <View style={styles.row}>
                    <ThemedText type="smallBold">
                      {formatSeconds(t.start)} – {formatSeconds(t.end)}
                    </ThemedText>
                    <Badge label={t.severity.toUpperCase()} fg={st.fg} bg={st.bg} />
                  </View>
                  <ThemedText type="small">{categoryLabel(t.category)}</ThemedText>
                  {t.evidence.slice(0, 3).map((line, j) => (
                    <ThemedText key={j} type="small" themeColor="textSecondary">
                      • {line}
                    </ThemedText>
                  ))}
                  <ThemedText type="small" themeColor="textSecondary">
                    {t.sources.map(sourceLabel).join(', ')}
                  </ThemedText>
                </Card>
              );
            })}
          </View>
        </View>
      ) : null}

      <View style={styles.section}>
        <SectionTitle>Evidence found</SectionTitle>
        <View style={styles.statsRow}>
          <Stat label="On-screen text" value={ev.ocr.length} />
          <Stat label="Speech" value={ev.audio.length} />
          <Stat label="Visual" value={ev.visual.length} />
        </View>
      </View>

      {textEvidence.length > 0 ? (
        <View style={styles.section}>
          <Card style={{ gap: Space.three }}>
            {textEvidence.slice(0, 8).map((t, i) => (
              <View key={i} style={styles.gapSm}>
                <View style={styles.row}>
                  <ThemedText type="smallBold" themeColor="textSecondary">
                    {sourceLabel(t.source)} · {formatSeconds(t.timestamp)}
                  </ThemedText>
                  <ThemedText type="small" themeColor="textSecondary">
                    {categoryLabel(t.category)}
                  </ThemedText>
                </View>
                <ThemedText type="small">“{t.text}”</ThemedText>
              </View>
            ))}
          </Card>
        </View>
      ) : null}

      {report.metadata ? (
        <View style={styles.section}>
          <SectionTitle>Video</SectionTitle>
          <Card style={styles.gapSm}>
            <ThemedText type="small" themeColor="textSecondary" numberOfLines={1}>
              {report.metadata.filename}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {report.metadata.source_platform}
              {report.metadata.duration_seconds
                ? ` · ${formatSeconds(report.metadata.duration_seconds)}`
                : ''}
              {report.metadata.width ? ` · ${report.metadata.width}×${report.metadata.height}` : ''}
            </ThemedText>
          </Card>
        </View>
      ) : null}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card style={styles.stat}>
      <ThemedText style={{ color: Accent, fontSize: 24, fontWeight: '800' }}>{value}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary" style={{ textAlign: 'center' }}>
        {label}
      </ThemedText>
    </Card>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center', paddingVertical: Space.five },
  gap: { gap: Space.three },
  gapSm: { gap: Space.one },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  flex: { flex: 1 },
  track: {
    height: 8,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.08)',
    overflow: 'hidden',
  },
  fill: { height: 8, borderRadius: 999, backgroundColor: Accent },
  report: { gap: Space.two },
  heroScore: { alignItems: 'center', gap: Space.two, marginVertical: Space.four },
  section: { marginTop: Space.three },
  markerRow: { flexDirection: 'row', alignItems: 'center', gap: Space.two },
  markerIcon: { fontSize: 16 },
  statsRow: { flexDirection: 'row', gap: Space.two },
  stat: { flex: 1, alignItems: 'center', gap: Space.one, paddingVertical: Space.three },
});
