type ScenarioExecution = {
  scenarioName: string;
  attempts: number;
  retried: boolean;
  finalStatus: 'passed' | 'failed' | 'unknown';
};

export class ExecutionMetrics {
  private static data: Record<string, ScenarioExecution> = {};

  static initScenario(scenarioName: string): void {
    if (!this.data[scenarioName]) {
      this.data[scenarioName] = {
        scenarioName,
        attempts: 0,
        retried: false,
        finalStatus: 'unknown'
      };
    }
  }

  static incrementAttempt(scenarioName: string): void {
    this.initScenario(scenarioName);
    this.data[scenarioName].attempts += 1;
    this.data[scenarioName].retried = this.data[scenarioName].attempts > 1;
  }

  static markFinalStatus(
    scenarioName: string,
    status: 'passed' | 'failed' | 'unknown'
  ): void {
    this.initScenario(scenarioName);
    this.data[scenarioName].finalStatus = status;
  }

  static getScenario(scenarioName: string): ScenarioExecution | undefined {
    return this.data[scenarioName];
  }

  static getAll(): ScenarioExecution[] {
    return Object.values(this.data);
  }
}
