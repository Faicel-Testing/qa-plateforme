import { randomUUID } from 'node:crypto';
import { dataProvider } from '../config/data.config';
import { TestUser, randomUser } from '../support/testData';
import { PostgresDataRepository } from './PostgresDataRepository';
import { negativeCases } from './negativeCases';

export class TestDataService {
  private repository?: PostgresDataRepository;
  private allocations: string[] = [];
  readonly runId = process.env.QA_RUN_ID || `local-${randomUUID()}`;
  constructor(readonly scenarioId: string) {
    if (dataProvider() === 'postgres') this.repository = new PostgresDataRepository();
  }
  async createUser(): Promise<TestUser> {
    const generated = randomUser();
    if (!this.repository) return generated;
    await this.repository.prepare(this.runId);
    const allocation = await this.repository.reserve(this.runId, this.scenarioId);
    this.allocations.push(allocation.id);
    return { ...generated, firstName: allocation.payload.firstName,
      lastName: allocation.payload.lastName, email: allocation.email };
  }
  async markCreated(): Promise<void> {
    for (const id of this.allocations) await this.repository?.markApplication(id, this.runId, 'created');
  }
  async markAttempted(): Promise<void> {
    for (const id of this.allocations) await this.repository?.markApplication(id, this.runId, 'unknown');
  }
  async negativeValue(caseKey: string, field: string): Promise<string> {
    if (this.repository) return this.repository.negativeValue(caseKey, field);
    const value = negativeCases[caseKey]?.[field];
    if (typeof value !== 'string') throw new Error('Negative data case or field missing');
    return value;
  }
  async dispose(outcome: string): Promise<void> {
    if (!this.repository) return;
    try {
      for (const id of this.allocations) await this.repository.release(id, this.runId, outcome);
    } finally { await this.repository.close(); }
  }
}
