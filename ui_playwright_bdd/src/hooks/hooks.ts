import fs from 'fs';
import { Before, After, Status, setDefaultTimeout } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { writeExecutorFile } from '../utils/allure-executor';
import { SmartRetry } from '../utils/smart-retry';
import { ExecutionMetrics } from '../utils/execution-metrics';
import { TestDataService } from '../data/TestDataService';

setDefaultTimeout(60 * 1000);

Before(async function (this: CustomWorld, scenario) {
  this.dataService = new TestDataService(scenario.pickle.id);
  writeExecutorFile();

  const scenarioName = scenario.pickle.name;
  this.scenarioName = scenarioName;

  ExecutionMetrics.incrementAttempt(scenarioName);

  await this.init();

  fs.mkdirSync('test-results', { recursive: true });

  this.traceName = `${scenarioName.replace(/[^a-zA-Z0-9-_]/g, '_')}-trace.zip`;

  const attempts = ExecutionMetrics.getScenario(scenarioName)?.attempts || 1;
  this.tracingEnabled = attempts > 1 || process.env.TEST_TRACE === 'true';

  if (this.tracingEnabled) {
    await this.context.tracing.start({
      screenshots: true,
      snapshots: true,
      sources: true
    });
  }

  this.attach(`Browser: ${this.browserName}`, 'text/plain');
  this.attach(`Scenario Name: ${scenarioName}`, 'text/plain');
  this.attach(`Base URL: ${this.baseUrl}`, 'text/plain');
  this.attach(`Environment: ${this.browserName}`, 'text/plain');
  this.attach(
    `Execution: ${this.browserName} | ${process.env.NODE_ENV}`,
    'text/plain'
  );

  this.consoleLogs = [];
  this.pageErrors = [];
  this.failedRequests = [];

  if (this.page) {
    this.page.on('console', (msg) => {
      this.consoleLogs.push(`[${msg.type().toUpperCase()}] ${msg.text()}`);
    });

    this.page.on('pageerror', (error) => {
      this.pageErrors.push(
        `[PAGE ERROR] ${error.message}\n${error.stack || ''}`
      );
    });

    this.page.on('requestfailed', (request) => {
      const failure = request.failure();
      this.failedRequests.push(
        `[REQUEST FAILED] ${request.method()} ${request.url()} - ${
          failure?.errorText || 'unknown error'
        }`
      );
    });
  }
});

After(async function (this: CustomWorld, scenario) {
  this.dataOutcome = scenario.result?.status || 'unknown';
  const scenarioName = this.scenarioName || 'Unknown scenario';
  let traceStopped = false;

  try {
    const errorMessage =
      scenario.result?.message || this.pageErrors.join('\n') || '';

    const isRetryable = SmartRetry.isRetryable(errorMessage);
    const retryReason = SmartRetry.getDecisionReason(errorMessage);

    const attempts = ExecutionMetrics.getScenario(scenarioName)?.attempts || 1;

    this.attach(
      [
        `Browser: ${this.browserName}`,
        `Scenario Name: ${scenarioName}`,
        `Attempts: ${attempts}`,
        `Final Status: ${scenario.result?.status || 'unknown'}`
      ].join('\n'),
      'text/plain'
    );

    if (scenario.result?.status === Status.PASSED) {
      ExecutionMetrics.markFinalStatus(scenarioName, 'passed');

      this.attach(
        `Recovered after retry: ${attempts > 1 ? 'YES' : 'NO'}`,
        'text/plain'
      );
    }

    if (scenario.result?.status === Status.FAILED) {
      ExecutionMetrics.markFinalStatus(scenarioName, 'failed');

      this.attach(`Retryable Error: ${isRetryable}`, 'text/plain');
      this.attach(`Retry Decision Reason: ${retryReason}`, 'text/plain');

      if (isRetryable) {
        ExecutionMetrics.markRetried(scenarioName, retryReason);
      }

      if (this.page) {
        const screenshot = await this.page.screenshot({ fullPage: true });
        this.attach(screenshot, 'image/png');

        this.attach(`Current URL: ${this.page.url()}`, 'text/plain');

        const pageSource = await this.page.content();
        this.attach(pageSource, 'text/html');

        const consoleLogs = this.consoleLogs.join('\n');
        this.attach(
          consoleLogs || 'No console logs captured.',
          'text/plain'
        );

        const pageErrors = this.pageErrors.join('\n\n');
        this.attach(
          pageErrors || 'No page errors captured.',
          'text/plain'
        );

        const failedRequests = this.failedRequests.join('\n');
        this.attach(
          failedRequests || 'No failed requests captured.',
          'text/plain'
        );
      }

      if (this.tracingEnabled) {
        const tracePath = `test-results/${this.traceName || 'trace.zip'}`;
        await this.context.tracing.stop({ path: tracePath });
        traceStopped = true;
        const traceBuffer = fs.readFileSync(tracePath);
        this.attach(traceBuffer, 'application/zip');
      } else {
        traceStopped = true;
      }
    }
  } finally {
    if (!traceStopped && this.tracingEnabled) {
      try {
        await this.context.tracing.stop();
      } catch {
        // trace déjà stoppée ou contexte indisponible
      }
    }

    await this.dispose();
  }
});
