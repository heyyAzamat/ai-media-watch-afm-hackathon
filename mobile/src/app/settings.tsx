import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useAuth } from '@/auth/auth-context';
import { Header, Screen } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Button, Card, SectionTitle, TextField } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { getApiBaseUrl, resetApiBaseUrl, setApiBaseUrl } from '@/storage/settings';

export default function SettingsScreen() {
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [url, setUrl] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getApiBaseUrl().then(setUrl);
  }, []);

  async function onSave() {
    const value = await setApiBaseUrl(url);
    setUrl(value);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function onReset() {
    setUrl(await resetApiBaseUrl());
    setSaved(false);
  }

  return (
    <Screen>
      <Header title="Settings" onBack={() => router.back()} />

      <SectionTitle>Account</SectionTitle>
      <Card style={styles.card}>
        <ThemedText type="smallBold">{user?.name ?? '—'}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {user?.email ?? ''}
        </ThemedText>
      </Card>

      <View style={styles.section}>
        <SectionTitle>API server</SectionTitle>
        <Card style={styles.card}>
          <TextField
            label="Base URL"
            value={url}
            onChangeText={setUrl}
            placeholder="http://localhost:8000"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <ThemedText type="small" themeColor="textSecondary">
            iOS simulator: localhost · Android emulator: 10.0.2.2 · physical device: your computer&apos;s
            LAN IP. The {'/api/v1'} prefix is added automatically.
          </ThemedText>
          <View style={styles.row}>
            <View style={styles.flex}>
              <Button title={saved ? 'Saved ✓' : 'Save'} onPress={onSave} />
            </View>
            <View style={styles.flex}>
              <Button title="Reset" variant="secondary" onPress={onReset} />
            </View>
          </View>
        </Card>
      </View>

      <View style={styles.section}>
        <Button title="Sign out" variant="danger" onPress={signOut} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { gap: Spacing.three },
  section: { marginTop: Spacing.four },
  row: { flexDirection: 'row', gap: Spacing.three },
  flex: { flex: 1 },
});
