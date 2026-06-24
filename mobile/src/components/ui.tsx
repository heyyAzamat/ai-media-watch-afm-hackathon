/** Small shared UI primitives in the dark "premium fintech" style. */

import { LinearGradient } from 'expo-linear-gradient';
import { type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
  type ViewProps,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Accent, ButtonGradient, CardBorder, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// ── Card (glassy) ─────────────────────────────────────────────────────────────
export function Card({ style, children, ...rest }: ViewProps & { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View
      style={[styles.card, { backgroundColor: theme.backgroundElement }, style]}
      {...rest}>
      {children}
    </View>
  );
}

// ── Button ──────────────────────────────────────────────────────────────────
export function Button({
  title,
  onPress,
  loading = false,
  disabled = false,
  variant = 'primary',
}: {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
}) {
  const theme = useTheme();
  const isDisabled = disabled || loading;

  if (variant === 'primary') {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={onPress}
        disabled={isDisabled}
        style={({ pressed }) => [styles.glow, { opacity: isDisabled ? 0.5 : pressed ? 0.9 : 1 }]}>
        <LinearGradient
          colors={ButtonGradient as unknown as [string, string, string]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.button}>
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <ThemedText style={[styles.buttonText, { color: '#FFFFFF' }]}>{title}</ThemedText>
          )}
        </LinearGradient>
      </Pressable>
    );
  }

  const bg = variant === 'danger' ? 'rgba(180, 35, 24, 0.16)' : theme.backgroundSelected;
  const fg = variant === 'danger' ? '#FF6A5E' : theme.text;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.button,
        styles.outlined,
        { backgroundColor: bg, opacity: isDisabled ? 0.5 : pressed ? 0.85 : 1 },
      ]}>
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <ThemedText style={[styles.buttonText, { color: fg }]}>{title}</ThemedText>
      )}
    </Pressable>
  );
}

// ── TextField ────────────────────────────────────────────────────────────────
export function TextField({ label, style, ...rest }: TextInputProps & { label?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: Spacing.two }}>
      {label ? (
        <ThemedText type="smallBold" themeColor="textSecondary">
          {label}
        </ThemedText>
      ) : null}
      <TextInput
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          { color: theme.text, backgroundColor: theme.backgroundElement },
          style,
        ]}
        {...rest}
      />
    </View>
  );
}

// ── Badge ────────────────────────────────────────────────────────────────────
export function Badge({ label, fg, bg }: { label: string; fg: string; bg: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <ThemedText type="smallBold" style={{ color: fg }}>
        {label}
      </ThemedText>
    </View>
  );
}

// ── Segmented control (blue active pill) ──────────────────────────────────────
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.segmented, { backgroundColor: theme.backgroundElement }]}>
      {options.map((opt) => {
        const active = opt.value === value;
        const Inner = (
          <ThemedText
            type="smallBold"
            style={{ color: active ? '#FFFFFF' : theme.textSecondary }}>
            {opt.label}
          </ThemedText>
        );
        return (
          <Pressable key={opt.value} onPress={() => onChange(opt.value)} style={styles.segment}>
            {active ? (
              <LinearGradient
                colors={ButtonGradient as unknown as [string, string, string]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.segmentActive}>
                {Inner}
              </LinearGradient>
            ) : (
              <View style={styles.segmentInner}>{Inner}</View>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

// ── Section header ────────────────────────────────────────────────────────────
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionTitle}>
      {children}
    </ThemedText>
  );
}

export const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    padding: Spacing.three,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: CardBorder,
  },
  glow: {
    borderRadius: 16,
    shadowColor: Accent,
    shadowOpacity: 0.5,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  button: {
    minHeight: 54,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.three,
  },
  outlined: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: CardBorder,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '700',
  },
  input: {
    minHeight: 52,
    borderRadius: 14,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    fontSize: 16,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: CardBorder,
  },
  badge: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  segmented: {
    flexDirection: 'row',
    borderRadius: 14,
    padding: 4,
    gap: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: CardBorder,
  },
  segment: { flex: 1 },
  segmentInner: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
  },
  segmentActive: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 11,
  },
  sectionTitle: {
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: Spacing.two,
  },
});
