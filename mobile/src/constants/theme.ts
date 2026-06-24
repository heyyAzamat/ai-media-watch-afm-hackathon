/**
 * App theme — dark-first "premium fintech" aesthetic:
 * near-black canvas with a blue glow, glassy cards, and a vivid blue gradient
 * accent. The app is dark regardless of system scheme (Colors.light === dark).
 */

import '@/global.css';

import { Platform } from 'react-native';

const palette = {
  text: '#F5F7FA',
  background: '#07090D',
  // glassy translucent surfaces layered over the dark canvas / glow
  backgroundElement: 'rgba(255, 255, 255, 0.05)',
  backgroundSelected: 'rgba(255, 255, 255, 0.10)',
  textSecondary: '#9AA0AC',
} as const;

export const Colors = {
  light: palette,
  dark: palette,
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

// ── Accent + gradients ────────────────────────────────────────────────────────
export const Accent = '#2F80ED';
export const AccentSoft = '#5AA6FF';
/** Diagonal gradient for the primary pill button. */
export const ButtonGradient = ['#5AA6FF', '#2F80ED', '#1E63D6'] as const;
/** Vertical blue glow painted behind screens (top -> dark). */
export const GlowGradient = ['#13294D', '#0B1424', '#07090D'] as const;
export const CardBorder = 'rgba(255, 255, 255, 0.08)';

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
