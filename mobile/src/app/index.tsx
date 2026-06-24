import * as DocumentPicker from 'expo-document-picker';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { submitAnalyze } from '@/api/client';
import { useAuth } from '@/auth/auth-context';
import { JobRow } from '@/components/job-row';
import { Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Button, Card, SectionTitle, Segmented, TextField } from '@/components/ui';
import { Accent, Spacing } from '@/constants/theme';
import { addJob, listJobs, type TrackedJob } from '@/storage/jobs';
import { inferPlatform, isLikelyUrl, shortenUrl } from '@/utils/platform';

type Mode = 'video' | 'profile';

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [mode, setMode] = useState<Mode>('video');
  const [link, setLink] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobs, setJobs] = useState<TrackedJob[]>([]);

  useFocusEffect(
    useCallback(() => {
      listJobs().then(setJobs);
    }, []),
  );

  async function saveAndOpen(jobId: string, videoId: string, label: string, platform: string) {
    await addJob({
      jobId,
      videoId,
      label,
      sourcePlatform: platform,
      createdAt: new Date().toISOString(),
    });
    setLink('');
    router.push({ pathname: '/job/[id]', params: { id: jobId } });
  }

  async function analyzeLink() {
    const url = link.trim();
    if (!isLikelyUrl(url)) {
      setError('Paste a valid link starting with http(s)://');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const platform = inferPlatform(url);
      const accepted = await submitAnalyze({
        kind: 'url',
        sourceUrl: url,
        sourcePlatform: platform,
      });
      await saveAndOpen(accepted.job_id, accepted.video_id, shortenUrl(url), `${mode} · ${platform}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit for analysis.');
    } finally {
      setSubmitting(false);
    }
  }

  async function uploadVideo() {
    setError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: 'video/*',
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    setSubmitting(true);
    try {
      const accepted = await submitAnalyze({
        kind: 'file',
        uri: asset.uri,
        name: asset.name,
        mimeType: asset.mimeType ?? undefined,
      });
      await saveAndOpen(accepted.job_id, accepted.video_id, asset.name, 'upload');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setSubmitting(false);
    }
  }

  const recent = jobs.slice(0, 3);

  return (
    <Screen>
      {/* top bar */}
      <View style={styles.topbar}>
        <ThemedText type="smallBold" style={{ color: Accent }}>
          ◇ MEDIA WATCH
        </ThemedText>
        <View style={styles.topActions}>
          <Pressable onPress={() => router.push('/history')} hitSlop={10}>
            <ThemedText type="small">History</ThemedText>
          </Pressable>
          <Pressable onPress={() => router.push('/settings')} hitSlop={10}>
            <ThemedText style={styles.gear}>⚙</ThemedText>
          </Pressable>
        </View>
      </View>

      {/* hero */}
      <View style={styles.hero}>
        <ThemedText themeColor="textSecondary" type="small">
          Hi{user?.name ? `, ${user.name}` : ''} 👋
        </ThemedText>
        <ThemedText style={styles.title}>Check a profile or</ThemedText>
        <ThemedText style={[styles.title, { color: Accent }]}>video for risk.</ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.subtitle}>
          Paste a link to scan it for gambling, scams and hidden ads.
        </ThemedText>
      </View>

      {/* scan card */}
      <Card style={styles.scanCard}>
        <Segmented<Mode>
          value={mode}
          onChange={setMode}
          options={[
            { value: 'video', label: 'Video' },
            { value: 'profile', label: 'Profile' },
          ]}
        />
        <TextField
          value={link}
          onChangeText={setLink}
          placeholder={mode === 'profile' ? 'Paste a profile link…' : 'Paste a video link…'}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          returnKeyType="go"
          onSubmitEditing={analyzeLink}
        />
        {error ? (
          <ThemedText type="small" style={styles.error}>
            {error}
          </ThemedText>
        ) : null}
        <Button title="Analyze" onPress={analyzeLink} loading={submitting} />
        <Pressable onPress={uploadVideo} disabled={submitting} style={styles.uploadLink}>
          <ThemedText type="small" themeColor="textSecondary">
            or upload a video file
          </ThemedText>
        </Pressable>
      </Card>

      {/* recent */}
      <View style={styles.recent}>
        <View style={styles.recentHeader}>
          <SectionTitle>Recent scans</SectionTitle>
          {jobs.length > 3 ? (
            <Pressable onPress={() => router.push('/history')} hitSlop={8}>
              <ThemedText type="small" style={{ color: Accent }}>
                See all
              </ThemedText>
            </Pressable>
          ) : null}
        </View>
        {recent.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No scans yet. Paste a link above to get started.
          </ThemedText>
        ) : (
          <View style={{ gap: Spacing.two }}>
            {recent.map((job) => (
              <JobRow key={job.jobId} job={job} />
            ))}
          </View>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 36,
  },
  topActions: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  gear: { fontSize: 18 },
  hero: { marginTop: Spacing.five, gap: 2 },
  title: { fontSize: 34, lineHeight: 40, fontWeight: '800' },
  subtitle: { fontSize: 15, lineHeight: 22, marginTop: Spacing.two },
  scanCard: { marginTop: Spacing.four, gap: Spacing.three },
  error: { color: '#FF6A5E' },
  uploadLink: { alignItems: 'center', paddingVertical: 4 },
  recent: { marginTop: Spacing.five },
  recentHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
});
