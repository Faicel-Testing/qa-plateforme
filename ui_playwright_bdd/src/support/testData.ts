export interface TestUser {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}

function randomPassword(length: number): string {
  const lower = 'abcdefghijklmnopqrstuvwxyz';
  const upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const digits = '0123456789';
  const all = lower + upper + digits;

  const getRandomChar = (chars: string) => chars[Math.floor(Math.random() * chars.length)];

  const passwordChars = [
    getRandomChar(lower),
    getRandomChar(upper),
    getRandomChar(digits)
  ];

  while (passwordChars.length < length) {
    passwordChars.push(getRandomChar(all));
  }

  return passwordChars
    .map((char) => ({ char, sort: Math.random() }))
    .sort((a, b) => a.sort - b.sort)
    .map((entry) => entry.char)
    .join('');
}

const firstNames = ['John', 'Mark', 'Anne', 'Luca', 'Mia', 'Noah', 'Emma', 'Owen'];
const lastNames = ['Doe', 'Kane', 'Benn', 'Reed', 'Tate', 'Ross', 'Lane', 'Wade'];

export function randomUser(): TestUser {
  // Date.now() seul peut collisionner entre workers parallèles tombant sur la même ms
  const id = `${Date.now()}${Math.floor(Math.random() * 1_000_000)}`;
  const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
  const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];

  return {
    firstName,
    lastName,
    email: `user${id}@mail.com`,
    password: randomPassword(8)
  };
}
