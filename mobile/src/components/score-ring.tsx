import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { categoryLabel, scoreStyle } from '@/constants/risk';
import type { RiskCategory } from '@/api/types';

/** Big circular risk score badge (0–100) tinted by band. */
export function ScoreRing({
  score,
  category,
  size = 132,
}: {
  score: number;
  category: RiskCategory;
  size?: number;
}) {
  const style = scoreStyle(score);
  return (
    <View style={styles.wrap}>
      <View
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderColor: style.fg,
            backgroundColor: style.bg,
          },
        ]}>
        <ThemedText style={[styles.score, { color: style.fg }]}>{score}</ThemedText>
        <ThemedText type="small" style={{ color: style.fg }}>
          / 100
        </ThemedText>
      </View>
      <ThemedText type="smallBold" style={[styles.bandLabel, { color: style.fg }]}>
        {style.label.toUpperCase()}
      </ThemedText>
      <ThemedText type="subtitle" style={styles.category}>
        {categoryLabel(category)}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: 8 },
  ring: {
    borderWidth: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  score: { fontSize: 44, fontWeight: '800', lineHeight: 48 },
  bandLabel: { letterSpacing: 1 },
  category: { fontSize: 22, lineHeight: 28, textAlign: 'center' },
});
