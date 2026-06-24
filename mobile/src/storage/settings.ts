import AsyncStorage from '@react-native-async-storage/async-storage';

import { DEFAULT_API_BASE_URL } from '@/constants/config';

const KEY = 'aimw.apiBaseUrl';

function normalize(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

export async function getApiBaseUrl(): Promise<string> {
  const stored = await AsyncStorage.getItem(KEY);
  return stored ? normalize(stored) : DEFAULT_API_BASE_URL;
}

export async function setApiBaseUrl(url: string): Promise<string> {
  const value = normalize(url) || DEFAULT_API_BASE_URL;
  await AsyncStorage.setItem(KEY, value);
  return value;
}

export async function resetApiBaseUrl(): Promise<string> {
  await AsyncStorage.removeItem(KEY);
  return DEFAULT_API_BASE_URL;
}
