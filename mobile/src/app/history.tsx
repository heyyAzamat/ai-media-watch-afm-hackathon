import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { JobRow } from '@/components/job-row';
import { Header, Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Button } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { clearJobs, listJobs, type TrackedJob } from '@/storage/jobs';

export default function HistoryScreen() {
  const router = useRouter();
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const reload = useCallback(async () => {
    setJobs(await listJobs());
  }, []);

  useFocusEffect(
    useCallback(() => {
      reload();
    }, [reload]),
  );

  async function onRefresh() {
    setRefreshing(true);
    await reload();
    setRefreshKey((k) => k + 1);
    setRefreshing(false);
  }

  async function onClear() {
    await clearJobs();
    setJobs([]);
  }

  return (
    <Screen scroll={false}>
      <Header title="Scan history" onBack={() => router.back()} />
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#9AA0AC" />
        }>
        {jobs.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary" style={styles.empty}>
            No scans yet.
          </ThemedText>
        ) : (
          <>
            <View style={{ gap: Spacing.two }}>
              {jobs.map((job) => (
                <JobRow key={job.jobId} job={job} refreshKey={refreshKey} />
              ))}
            </View>
            <View style={styles.clear}>
              <Button title="Clear history" variant="danger" onPress={onClear} />
            </View>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: Spacing.five },
  empty: { marginTop: Spacing.four },
  clear: { marginTop: Spacing.four },
});
