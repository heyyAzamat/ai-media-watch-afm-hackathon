import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * LOCAL-ONLY mock auth. Credentials live on-device in AsyncStorage (plaintext —
 * NOT secure). This exists so the login/registration flow works end-to-end now;
 * swap signIn/signUp to real /auth API calls once the backend exposes them.
 */

export interface Session {
  name: string;
  email: string;
}

interface Account extends Session {
  password: string;
}

const USERS_KEY = 'aimw.users';
const SESSION_KEY = 'aimw.session';

async function readUsers(): Promise<Account[]> {
  const raw = await AsyncStorage.getItem(USERS_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Account[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normEmail(email: string): string {
  return email.trim().toLowerCase();
}

export async function getSession(): Promise<Session | null> {
  const raw = await AsyncStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export async function signUp(name: string, email: string, password: string): Promise<Session> {
  const e = normEmail(email);
  if (!name.trim()) throw new Error('Please enter your name.');
  if (!e) throw new Error('Please enter an email.');
  if (password.length < 4) throw new Error('Password must be at least 4 characters.');

  const users = await readUsers();
  if (users.some((u) => u.email === e)) {
    throw new Error('An account with this email already exists.');
  }
  const account: Account = { name: name.trim(), email: e, password };
  await AsyncStorage.setItem(USERS_KEY, JSON.stringify([...users, account]));
  const session: Session = { name: account.name, email: account.email };
  await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export async function signIn(email: string, password: string): Promise<Session> {
  const e = normEmail(email);
  const users = await readUsers();
  const account = users.find((u) => u.email === e);
  if (!account || account.password !== password) {
    throw new Error('Incorrect email or password.');
  }
  const session: Session = { name: account.name, email: account.email };
  await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export async function signOut(): Promise<void> {
  await AsyncStorage.removeItem(SESSION_KEY);
}
