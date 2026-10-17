import { Pool } from 'pg';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { postgresConfig } from '../config/data.config';

export interface Allocation {
  id: string;
  email: string;
  payload: { firstName: string; lastName: string };
}

export class PostgresDataRepository {
  private pool: Pool;
  constructor() {
    this.pool = new Pool(postgresConfig());
    // Never emit connection configuration or passwords in process logs.
    this.pool.on('error', () => console.error('[Data] PostgreSQL idle connection unavailable'));
  }
  async close(): Promise<void> { await this.pool.end(); }
  async migrate(): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query(fs.readFileSync(path.resolve(__dirname, '../../database/migrations/001_test_data.sql'), 'utf8'));
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally { client.release(); }
  }
  async seed(): Promise<void> {
    await this.pool.query(fs.readFileSync(path.resolve(__dirname, '../../database/queries/seed.sql'), 'utf8'));
  }
  async prepare(runId: string): Promise<void> {
    if (!runId || runId.length > 200) throw new Error('Invalid data run ID');
    await this.pool.query(`INSERT INTO qa_test_data.test_runs(run_id,environment)
      VALUES($1,$2) ON CONFLICT (run_id) DO NOTHING`, [runId, process.env.ENV || 'local']);
    const result = await this.pool.query<{status: string}>(`SELECT status FROM qa_test_data.test_runs WHERE run_id=$1`, [runId]);
    if (result.rows[0].status !== 'prepared') throw new Error('Data run is already completed; use a new run ID');
    const datasets = await this.pool.query<{available: boolean}>(`SELECT EXISTS(SELECT 1 FROM qa_test_data.data_sets WHERE kind='user' AND active) AS available`);
    if (!datasets.rows[0].available) throw new Error('No user profiles: run data:seed');
  }
  async reserve(runId: string, scenarioId: string): Promise<Allocation> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      // Protect against completion while a scenario is reserving data.
      const run = await client.query<{status: string}>(`SELECT status FROM qa_test_data.test_runs WHERE run_id=$1 FOR SHARE`, [runId]);
      if (run.rows[0]?.status !== 'prepared') throw new Error('Prepare the data run before reserving');
      const selected = await client.query<{id: string; payload: unknown}>(`SELECT d.id,d.payload FROM qa_test_data.data_sets d
        WHERE d.kind='user' AND d.active AND NOT EXISTS
          (SELECT 1 FROM qa_test_data.data_allocations a WHERE a.dataset_id=d.id AND a.status='reserved')
        ORDER BY d.id FOR UPDATE OF d SKIP LOCKED LIMIT 1`);
      const row = selected.rows[0];
      if (!row) throw new Error('No test data available; seed more profiles or release a stopped run');
      const payload = row.payload;
      if (!payload || typeof payload !== 'object' || !('firstName' in payload) || !('lastName' in payload) ||
          typeof payload.firstName !== 'string' || !payload.firstName.trim() ||
          typeof payload.lastName !== 'string' || !payload.lastName.trim()) throw new Error('Invalid user dataset');
      const id = randomUUID();
      const email = `qa${id.replace(/-/g, '')}@mail.com`;
      await client.query(`INSERT INTO qa_test_data.data_allocations(id,run_id,scenario_id,dataset_id,email)
        VALUES($1,$2,$3,$4,$5)`, [id,runId,scenarioId,row.id,email]);
      await client.query('COMMIT');
      return { id,email,payload: { firstName: payload.firstName, lastName: payload.lastName } };
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  }
  async markApplication(id: string, runId: string, state: 'created' | 'creation_failed' | 'unknown'): Promise<void> {
    await this.pool.query(`UPDATE qa_test_data.data_allocations SET application_state=$3
      WHERE id=$1 AND run_id=$2 AND status='reserved'`, [id,runId,state]);
  }
  async release(id: string, runId: string, outcome: string): Promise<void> {
    await this.pool.query(`UPDATE qa_test_data.data_allocations SET status='released',released_at=now(),outcome=$3
      WHERE id=$1 AND run_id=$2 AND status='reserved'`, [id,runId,outcome]);
  }
  async complete(runId: string): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(`SELECT run_id FROM qa_test_data.test_runs WHERE run_id=$1 FOR UPDATE`, [runId]);
      await client.query(`UPDATE qa_test_data.data_allocations SET status='released',released_at=now(),
        outcome=COALESCE(outcome,'run_finished') WHERE run_id=$1 AND status='reserved'`, [runId]);
      await client.query(`UPDATE qa_test_data.test_runs SET status='completed',finished_at=now() WHERE run_id=$1`, [runId]);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  }
  async status(): Promise<Record<string, unknown>> {
    const datasets = await this.pool.query(`SELECT kind,count(*)::int AS count FROM qa_test_data.data_sets GROUP BY kind`);
    const allocations = await this.pool.query(`SELECT status,count(*)::int AS count FROM qa_test_data.data_allocations GROUP BY status`);
    return { connected: true, datasets: datasets.rows, allocations: allocations.rows };
  }
  async negativeValue(caseKey: string, field: string): Promise<string> {
    const result = await this.pool.query<{payload: Record<string, unknown>}>(`SELECT payload FROM qa_test_data.data_sets
      WHERE case_key=$1 AND kind='negative' AND active`, [caseKey]);
    const value = result.rows[0]?.payload?.[field];
    if (typeof value !== 'string') throw new Error('Negative data case or field missing');
    return value;
  }
}
