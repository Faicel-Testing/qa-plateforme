import { request } from '@playwright/test';
import { TestUser } from '../support/testData';

/**
 * Client HTTP léger basé sur playwright/test request (built-in, zéro dépendance ajoutée).
 * ignoreHTTPSErrors: true → bypass proxy corporate SSL (même raison que le framework Java).
 *
 * Pattern Senior : les préconditions de test ne passent jamais par l'UI signup.
 *   POST /api/v1/users/register  → crée l'utilisateur en base, retourne JWT
 *   POST /api/v1/users/login     → authentifie un user existant, retourne JWT
 */
export class QACartApiClient {
  private readonly baseUrl: string;

  constructor() {
    this.baseUrl = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';
  }

  async register(user: TestUser): Promise<string> {
    const ctx = await request.newContext({
      baseURL: this.baseUrl,
      ignoreHTTPSErrors: true,
    });

    try {
      const response = await ctx.post('/api/v1/users/register', {
        data: {
          firstName: user.firstName,
          lastName:  user.lastName,
          email:     user.email,
          password:  user.password,
        },
        timeout: 30_000,
      });

      if (!response.ok()) {
        const body = await response.text();
        throw new Error(
          `POST /api/v1/users/register → HTTP ${response.status()}\n${body}`
        );
      }

      const json = await response.json() as { token?: string };
      return json.token ?? '';
    } finally {
      await ctx.dispose();
    }
  }

  async login(user: Pick<TestUser, 'email' | 'password'>): Promise<string> {
    const ctx = await request.newContext({
      baseURL: this.baseUrl,
      ignoreHTTPSErrors: true,
    });

    try {
      const response = await ctx.post('/api/v1/users/login', {
        data: { email: user.email, password: user.password },
        timeout: 30_000,
      });

      if (!response.ok()) {
        const body = await response.text();
        throw new Error(
          `POST /api/v1/users/login → HTTP ${response.status()}\n${body}`
        );
      }

      const json = await response.json() as { token?: string };
      return json.token ?? '';
    } finally {
      await ctx.dispose();
    }
  }
}
