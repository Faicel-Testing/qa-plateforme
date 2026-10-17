import { PoolConfig } from 'pg';
import dotenv from 'dotenv';
import path from 'node:path';

// Direct Cucumber runs use the same local configuration as the Python pipeline.
dotenv.config({ path: path.resolve(__dirname, '../../.env'), quiet: true });

export function dataProvider(env = process.env): 'memory' | 'postgres' {
  const value = env.TEST_DATA_PROVIDER || 'memory';
  if (value !== 'memory' && value !== 'postgres') throw new Error('TEST_DATA_PROVIDER must be memory or postgres');
  return value;
}

export function postgresConfig(env = process.env): PoolConfig {
  for (const key of ['TEST_DATA_PGDATABASE', 'TEST_DATA_PGUSER', 'TEST_DATA_PGPASSWORD']) {
    if (!env[key]) throw new Error(`Missing ${key}; configure the dedicated test database in .env`);
  }
  const database = env.TEST_DATA_PGDATABASE!;
  if (['postgres', 'template0', 'template1'].includes(database)) throw new Error('Use a dedicated test database');
  const port = Number(env.TEST_DATA_PGPORT || '5432');
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid TEST_DATA_PGPORT');
  const host = env.TEST_DATA_PGHOST || 'localhost';
  const local = ['localhost', '127.0.0.1', '::1'].includes(host);
  return { host, port, database, user: env.TEST_DATA_PGUSER,
    password: env.TEST_DATA_PGPASSWORD, max: 2, connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 1000, statement_timeout: 15000,
    ssl: local ? undefined : { rejectUnauthorized: true },
    application_name: 'qa-test-data-agent' };
}
