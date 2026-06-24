import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useAuth } from '@/auth/auth-context';
import { ThemedText } from '@/components/themed-text';
import { Screen } from '@/components/screen';
import { Button, TextField } from '@/components/ui';
import { Accent, Spacing } from '@/constants/theme';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit() {
    setError(null);
    setLoading(true);
    try {
      await signIn(email, password);
      // Root navigator redirects to "/" on auth.
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <View style={styles.body}>
        <ThemedText type="smallBold" style={{ color: Accent }}>
          ◇ MEDIA WATCH
        </ThemedText>
        <View style={styles.heading}>
          <ThemedText style={styles.title}>Welcome</ThemedText>
          <ThemedText style={[styles.title, { color: Accent }]}>back.</ThemedText>
        </View>
        <ThemedText themeColor="textSecondary" style={styles.subtitle}>
          Sign in to scan profiles and videos for financial risk.
        </ThemedText>

        <View style={styles.form}>
          <TextField
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
          />
          <TextField
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            secureTextEntry
          />
          {error ? (
            <ThemedText type="small" style={styles.error}>
              {error}
            </ThemedText>
          ) : null}
          <Button title="Log in" onPress={onSubmit} loading={loading} />
        </View>

        <View style={styles.footer}>
          <ThemedText type="small" themeColor="textSecondary">
            New here?{' '}
          </ThemedText>
          <Link href="/register">
            <ThemedText type="smallBold" style={{ color: Accent }}>
              Create an account
            </ThemedText>
          </Link>
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, justifyContent: 'center', gap: Spacing.three },
  heading: { marginTop: Spacing.three },
  title: { fontSize: 40, lineHeight: 46, fontWeight: '800' },
  subtitle: { fontSize: 15, lineHeight: 22 },
  form: { gap: Spacing.three, marginTop: Spacing.two },
  error: { color: '#FF6A5E' },
  footer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
});
