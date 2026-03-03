import fs from 'fs';
import path from 'path';

export type UserCreds = { email: string; password: string; name: string };

const FIXTURE_PATH = path.resolve(__dirname, '..', 'fixtures', 'user.json');

export function saveUser(user: UserCreds): void {
  fs.mkdirSync(path.dirname(FIXTURE_PATH), { recursive: true });
  fs.writeFileSync(FIXTURE_PATH, JSON.stringify(user, null, 2), 'utf-8');
}

export function loadUser(): UserCreds | null {
  if (!fs.existsSync(FIXTURE_PATH)) return null;
  const raw = fs.readFileSync(FIXTURE_PATH, 'utf-8').trim();
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserCreds;
  } catch {
    return null;
  }
}