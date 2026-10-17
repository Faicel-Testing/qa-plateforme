const fs = require('fs');
const path = require('path');


function readJSON(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch {
    return null;
  }
}

function readAttachment(resultsDir, fileName) {
  try {
    return fs.readFileSync(path.join(resultsDir, fileName), 'utf-8');
  } catch {
    return '';
  }
}

function normalizeBrowser(value) {
  if (!value) return 'unknown';

  const browser = value.trim().toLowerCase();

  if (browser.includes('chrom')) return 'chromium';
  if (browser.includes('firefox')) return 'firefox';
  if (browser.includes('webkit')) return 'webkit';

  return browser;
}

function collectAttachments(node, acc = []) {
  if (!node) return acc;

  if (Array.isArray(node.attachments)) {
    acc.push(...node.attachments);
  }

  if (Array.isArray(node.steps)) {
    for (const step of node.steps) {
      collectAttachments(step, acc);
    }
  }

  return acc;
}

function extractDataFromAttachments(result, containerAttachmentsByUuid, resultsDir) {
  // allure-cucumberjs writes the Before-hook attachments (Browser, Attempts...) into a
  // separate *-container.json (befores[].steps[].attachments), linked via children: [uuid].
  // result.attachments is always empty; result.steps only holds the Gherkin steps' own attachments.
  const attachments = [
    ...collectAttachments(result),
    ...(containerAttachmentsByUuid.get(result.uuid) || [])
  ];

  let browser = normalizeBrowser([...(result.labels || []), ...(result.parameters || [])].find(item => item.name === 'browser')?.value);
  let attempts = 1;

  for (const att of attachments) {
    if (!att.source || (att.type && att.type !== 'text/plain')) continue;

    const content = readAttachment(resultsDir, att.source);
    if (!content) continue;

    const browserMatch = content.match(/Browser:\s*(.+)/i);
    if (browserMatch) {
      browser = normalizeBrowser(browserMatch[1]);
    }

    const attemptsMatch = content.match(/Attempts:\s*(\d+)/i);
    if (attemptsMatch) {
      attempts = Number(attemptsMatch[1]);
    }
  }

  return { browser, attempts };
}

function buildContainerAttachmentsByUuid(containers) {
  const map = new Map();

  for (const container of containers) {
    const attachments = [
      ...(container.befores || []).flatMap((b) => collectAttachments(b)),
      ...(container.afters || []).flatMap((a) => collectAttachments(a))
    ];

    for (const childUuid of container.children || []) {
      map.set(childUuid, [...(map.get(childUuid) || []), ...attachments]);
    }
  }

  return map;
}

function buildDashboard(results, containerAttachmentsByUuid, resultsDir) {
  const dashboard = {};
  const groups = new Map();
  for (const result of results) {
    const metadata = extractDataFromAttachments(result, containerAttachmentsByUuid, resultsDir);
    const key = JSON.stringify([metadata.browser, result.historyId || result.uuid]);
    const group = groups.get(key) || [];
    group.push({ result, ...metadata });
    groups.set(key, group);
  }

  for (const group of groups.values()) {
    // Allure displays the latest attempt as the test's final outcome.
    group.sort((a, b) => (b.result.start || 0) - (a.result.start || 0) || (b.result.stop || 0) - (a.result.stop || 0));
    const { result, browser, attempts } = group[0];
    const status = result.status || 'unknown';

    if (!dashboard[browser]) {
      dashboard[browser] = {
        total: 0,
        passed: 0,
        failed: 0,
        broken: 0,
        skipped: 0,
        retried: 0,
        unknown: 0,
        flaky: 0,
        durationTotalMs: 0,
        timedTests: 0,
        start: null,
        stop: null
      };
    }

    const d = dashboard[browser];

    d.total++;

    if (status === 'passed') d.passed++;
    else if (status === 'failed') d.failed++;
    else if (status === 'broken') d.broken++;
    else if (status === 'skipped') d.skipped++;
    else d.unknown++;
    if (group.some(a => a.result.status === 'passed') && group.some(a => ['failed', 'broken'].includes(a.result.status))) d.flaky++;
    if (Number.isFinite(result.start) && Number.isFinite(result.stop) && result.stop >= result.start) {
      d.durationTotalMs += result.stop - result.start;
      d.timedTests++;
    }

    for (const { result: attempt } of group) {
      if (Number.isFinite(attempt.start) && Number.isFinite(attempt.stop) && attempt.stop >= attempt.start) {
        d.start = d.start === null ? attempt.start : Math.min(d.start, attempt.start);
        d.stop = d.stop === null ? attempt.stop : Math.max(d.stop, attempt.stop);
      }
    }

    if (attempts > 1 || group.length > 1) {
      d.retried++;
    }
  }

  for (const browser of Object.keys(dashboard)) {
    const d = dashboard[browser];
    d.durationMs = d.start === null ? null : d.stop - d.start;

    d.passRate = d.total
      ? Number(((d.passed / d.total) * 100).toFixed(2))
      : 0;

    d.failureRate = d.total
      ? Number((((d.failed + d.broken) / d.total) * 100).toFixed(2))
      : 0;

    d.retryRate = d.total
      ? Number(((d.retried / d.total) * 100).toFixed(2))
      : 0;
  }

  return dashboard;
}

function toText(dashboard) {
  const lines = ['===== BROWSER DASHBOARD =====', ''];
  const browsers = Object.keys(dashboard).sort();

  if (browsers.length === 0) {
    lines.push('No browser data found.');
    return lines.join('\n');
  }

  for (const browser of browsers) {
    const d = dashboard[browser];

    lines.push(browser);
    lines.push(`- Total: ${d.total}`);
    lines.push(`- Passed: ${d.passed}`);
    lines.push(`- Failed: ${d.failed}`);
    lines.push(`- Broken: ${d.broken}`);
    lines.push(`- Skipped: ${d.skipped}`);
    lines.push(`- Retried: ${d.retried}`);
    lines.push(`- Pass Rate: ${d.passRate}%`);
    lines.push(`- Failure Rate: ${d.failureRate}%`);
    lines.push(`- Retry Rate: ${d.retryRate}%`);
    lines.push(`- Execution time: ${formatDuration(d.durationMs)}`);
    lines.push('');
  }

  return lines.join('\n');
}

function formatDuration(durationMs) {
  return durationMs === null ? 'unavailable' : `${(durationMs / 1000).toFixed(3)} s`;
}

function writeEnvironment(dashboard, resultsDir) {
  const lines = [];
  const browsers = Object.keys(dashboard).sort();

  if (browsers.length === 0) {
    lines.push('browser_dashboard=No browser data found');
  } else {
    for (const browser of browsers) {
      const d = dashboard[browser];

      lines.push(`${browser}_total=${d.total}`);
      lines.push(`${browser}_passed=${d.passed}`);
      lines.push(`${browser}_failed=${d.failed}`);
      lines.push(`${browser}_broken=${d.broken}`);
      lines.push(`${browser}_skipped=${d.skipped}`);
      lines.push(`${browser}_unknown=${d.unknown}`);
      lines.push(`${browser}_execution_time=${formatDuration(d.durationMs)}`);
      lines.push(`${browser}_retried=${d.retried}`);
      lines.push(`${browser}_pass_rate=${d.passRate}%`);
      lines.push(`${browser}_failure_rate=${d.failureRate}%`);
      lines.push(`${browser}_retry_rate=${d.retryRate}%`);
      lines.push('');
    }
  }

  const timed = Object.values(dashboard).filter(d => d.durationMs !== null);
  const elapsed = timed.length ? Math.max(...timed.map(d => d.stop)) - Math.min(...timed.map(d => d.start)) : null;
  lines.push(`tests_execution_time=${formatDuration(elapsed)}`);
  const envFile = path.join(resultsDir, 'environment.properties');
  // Preserve user metadata; replace only entries owned by this dashboard.
  const existing = fs.existsSync(envFile) ? fs.readFileSync(envFile, 'utf8').split(/\r?\n/) : [];
  const owned = /^(?:browser_dashboard|tests_execution_time|\S+_(?:total|passed|failed|broken|skipped|unknown|retried|pass_rate|failure_rate|retry_rate|execution_time))\s*=/;
  const preserved = existing.filter(line => line.trim() && !owned.test(line));
  fs.writeFileSync(envFile, [...lines, ...preserved, ''].join('\n'), 'utf-8');
}

function main(resultsDir) {
  const RESULTS_DIR = resultsDir || require('./agents/shared/pipeline-runtime').resultDirectory(path.join(__dirname, '..'));
  if (!fs.existsSync(RESULTS_DIR)) {
    console.log('No allure-results found');
    return;
  }

  const files = fs.readdirSync(RESULTS_DIR);
  const resultFiles = files.filter((f) => f.endsWith('-result.json'));
  const containerFiles = files.filter((f) => f.endsWith('-container.json'));

  const results = resultFiles
    .map((f) => readJSON(path.join(RESULTS_DIR, f)))
    .filter(Boolean);

  const containers = containerFiles
    .map((f) => readJSON(path.join(RESULTS_DIR, f)))
    .filter(Boolean);

  const containerAttachmentsByUuid = buildContainerAttachmentsByUuid(containers);
  const dashboard = buildDashboard(results, containerAttachmentsByUuid, RESULTS_DIR);
  const textReport = toText(dashboard);

  fs.writeFileSync(path.join(RESULTS_DIR, 'browser-dashboard.json'), JSON.stringify(dashboard, null, 2), 'utf-8');
  fs.writeFileSync(path.join(RESULTS_DIR, 'browser-dashboard.txt'), textReport, 'utf-8');
  writeEnvironment(dashboard, RESULTS_DIR);

  console.log('\n===== BROWSER DASHBOARD =====\n');
  console.log(textReport);
  return dashboard;
}
if (require.main === module) main();
module.exports = { main };
