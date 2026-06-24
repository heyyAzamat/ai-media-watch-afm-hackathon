import { Platform } from 'react-native';

/**
 * Default API base URL. Override at runtime in the Settings screen (persisted).
 *
 * Device/emulator note:
 *  - iOS simulator: http://localhost:8000 works.
 *  - Android emulator: use http://10.0.2.2:8000 (localhost = the emulator).
 *  - Physical device: use your machine's LAN IP, e.g. http://192.168.x.x:8000.
 */
export const DEFAULT_API_BASE_URL =
  Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';

/** Matches Settings.api_prefix on the backend. */
export const API_PREFIX = '/api/v1';

/** Status polling cadence (ms) on the job detail screen. */
export const POLL_INTERVAL_MS = 2000;
