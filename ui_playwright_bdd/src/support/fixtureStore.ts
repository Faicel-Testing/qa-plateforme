import fs from 'fs';
import path from 'path';
import { TestUser } from './testData';

const fixtureDir = path.resolve('src/fixtures');
const fixturePath = path.join(fixtureDir, 'user.json');

export function saveUser(user: TestUser): void {
  if (!fs.existsSync(fixtureDir)) {
    fs.mkdirSync(fixtureDir, { recursive: true });
  }

  fs.writeFileSync(fixturePath, JSON.stringify(user, null, 2), 'utf-8');
}

export function loadUser(): TestUser | null {
  if (!fs.existsSync(fixturePath)) {
    return null;
  }

  const raw = fs.readFileSync(fixturePath, 'utf-8');
  return JSON.parse(raw) as TestUser;
}

export function clearUser(): void {
  if (fs.existsSync(fixturePath)) {
    fs.unlinkSync(fixturePath);
  }
}