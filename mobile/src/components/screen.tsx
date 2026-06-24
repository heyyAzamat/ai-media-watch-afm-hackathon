import { LinearGradient } from 'expo-linear-gradient';
import { type ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { Colors, GlowGradient, MaxContentWidth, Spacing } from '@/constants/theme';

/**
 * Full-screen dark canvas with a blue glow painted at the top — the base for
 * every screen in the app.
 */
export function Screen({
  children,
  scroll = true,
  contentStyle,
}: {
  children: ReactNode;
  scroll?: boolean;
  contentStyle?: ViewStyle;
}) {
  const insets = useSafeAreaInsets();
  const pad: ViewStyle = {
    paddingTop: insets.top,
    paddingBottom: insets.bottom,
  };

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={GlowGradient as unknown as [string, string, string]}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 0.55 }}
        style={StyleSheet.absoluteFill}
      />
      {scroll ? (
        <ScrollView
          contentContainerStyle={[styles.scrollContent, pad, contentStyle]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          <View style={styles.inner}>{children}</View>
        </ScrollView>
      ) : (
        <View style={[styles.flexContent, pad, contentStyle]}>
          <View style={styles.inner}>{children}</View>
        </View>
      )}
    </View>
  );
}

/** Lightweight screen header: optional back chevron, title, optional right slot. */
export function Header({
  title,
  onBack,
  right,
}: {
  title?: string;
  onBack?: () => void;
  right?: ReactNode;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerSide}>
        {onBack ? (
          <Pressable onPress={onBack} hitSlop={12} accessibilityRole="button">
            <ThemedText style={styles.chevron}>‹</ThemedText>
          </Pressable>
        ) : null}
      </View>
      <ThemedText type="smallBold" style={styles.headerTitle} numberOfLines={1}>
        {title ?? ''}
      </ThemedText>
      <View style={[styles.headerSide, styles.headerRight]}>{right}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.dark.background },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
  },
  flexContent: {
    flex: 1,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
  },
  inner: { width: '100%', maxWidth: MaxContentWidth, flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 44,
    marginBottom: Spacing.two,
  },
  headerSide: { width: 60, justifyContent: 'center' },
  headerRight: { alignItems: 'flex-end' },
  headerTitle: { flex: 1, textAlign: 'center' },
  chevron: { fontSize: 34, lineHeight: 36, fontWeight: '300' },
});
