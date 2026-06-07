export class RetryManager {
  private static retries: Record<string, number> = {};

  static getRetries(scenarioName: string): number {
    return this.retries[scenarioName] || 0;
  }

  static increment(scenarioName: string): void {
    this.retries[scenarioName] =
      (this.retries[scenarioName] || 0) + 1;
  }

  static reset(scenarioName: string): void {
    delete this.retries[scenarioName];
  }
}