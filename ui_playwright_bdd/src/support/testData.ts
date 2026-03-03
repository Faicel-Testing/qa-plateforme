import { UserCreds } from './fixtureStore';

export function randomUser(): UserCreds {
  const ts = Date.now();
  return {
    name: `FG_User_${ts}`,
    email: `fg_${ts}@mailinator.com`,
    password: `P@ssw0rd_${ts}`,
  };
}