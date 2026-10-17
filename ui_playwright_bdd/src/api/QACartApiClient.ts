import { request, APIRequestContext } from '@playwright/test';
import { TestUser } from '../support/testData';

/**
 * Client HTTP léger basé sur playwright/test request (built-in, zéro dépendance ajoutée).
 * ignoreHTTPSErrors: true → bypass proxy corporate SSL (même raison que le framework Java).
 *
 * Pattern Senior : les préconditions de test ne passent jamais par l'UI signup.
 *   POST /api/v1/users/register  → crée l'utilisateur en base, retourne JWT
 *   POST /api/v1/users/login     → authentifie un user existant, retourne JWT
 */
export interface ApiDiagnostic {
  kind: 'qa-api-diagnostic';
  schemaVersion: 1;
  timestamp: string;
  target: string;
  method: 'POST';
  path: string;
  timeoutMs: number;
  maxRetries: number;
  mode: 'real-http';
  tlsVerification: false;
  durationMs: number;
  status: number | null;
  errorCode: string | null;
}

export function apiErrorCode(error: unknown): string {
  const known = /\b(ECONNRESET|ECONNREFUSED|ENOTFOUND|EAI_AGAIN|ETIMEDOUT|EPIPE|ERR_TLS_CERT_ALTNAME_INVALID|UNABLE_TO_VERIFY_LEAF_SIGNATURE)\b/;
  let current: unknown = error;
  for (let i = 0; i < 5 && current && typeof current === 'object'; i++) {
    const candidate = current as { code?: unknown; name?: unknown; message?: unknown; cause?: unknown };
    for (const value of [candidate.code, candidate.message]) {
      if (typeof value === 'string') { const match = value.match(known); if (match) return match[1]; }
    }
    if (candidate.name === 'TimeoutError' || (typeof candidate.message === 'string' && /timeout|timed out/i.test(candidate.message))) return 'TIMEOUT';
    current = candidate.cause;
  }
  return 'API_REQUEST_FAILED';
}

export class QACartApiClient {
  private readonly baseUrl: string;

  constructor(private readonly record?: (event: ApiDiagnostic) => void | Promise<void>) {
    this.baseUrl = process.env.BASE_URL || 'https://qacart-todo.herokuapp.com';
  }

  private async authenticate(path: string, user: object): Promise<string> {
    const url = new URL(this.baseUrl);
    const event: ApiDiagnostic = { kind: 'qa-api-diagnostic', schemaVersion: 1,
      timestamp: new Date().toISOString(), target: url.origin,
      method: 'POST', path, timeoutMs: 30_000, maxRetries: 0, mode: 'real-http',
      tlsVerification: false, durationMs: 0, status: null, errorCode: null };
    const started = Date.now();
    let ctx: APIRequestContext | undefined;
    try {
      ctx = await request.newContext({ baseURL: this.baseUrl, ignoreHTTPSErrors: true });
      const response = await ctx.post(path, { data: user, timeout: 30_000, maxRetries: 0 });
      event.status = response.status();
      if (!response.ok()) { event.errorCode = 'HTTP_ERROR'; throw new Error('HTTP error'); }
      const json: unknown = await response.json();
      const token = json && typeof json === 'object'
        ? ('access_token' in json ? json.access_token : 'token' in json ? json.token : undefined) : undefined;
      if (typeof token !== 'string' || !token) {
        event.errorCode = 'API_TOKEN_MISSING'; throw new Error('Missing API token');
      }
      return token;
    } catch (error) {
      event.errorCode ||= apiErrorCode(error);
      throw new Error(`POST ${path}: ${event.errorCode}${event.status !== null ? ` (HTTP ${event.status})` : ''}. See attached API diagnostic.`);
    } finally {
      event.durationMs = Date.now() - started;
      console.log(`[API diagnostic] ${JSON.stringify(event)}`);
      try { await this.record?.(event); }
      catch { console.warn('[API diagnostic] Attachment unavailable; diagnostic retained in runner output'); }
      try { await ctx?.dispose(); }
      catch { console.warn('[API diagnostic] API context disposal failed'); }
    }
  }

  async register(user: TestUser): Promise<string> {
    return this.authenticate('/api/v1/users/register', {
      firstName: user.firstName, lastName: user.lastName, email: user.email, password: user.password
    });
  }
  async login(user: Pick<TestUser, 'email' | 'password'>): Promise<string> {
    return this.authenticate('/api/v1/users/login', { email: user.email, password: user.password });
  }
}
