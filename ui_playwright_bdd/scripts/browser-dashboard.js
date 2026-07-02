const fs = require('fs');
const path = require('path');

const RESULTS_DIR = path.resolve('allure-results');
const OUTPUT_TXT = path.resolve(RESULTS_DIR, 'browser-dashboard.txt');
const OUTPUT_JSON = path.resolve(RESULTS_DIR, 'browser-dashboard.json');
const ENV_FILE = path.resolve(RESULTS_DIR, 'environment.properties');

function readJSON(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch {
    return null;
  }
}

function readAttachment(fileName) {
  try {
    return fs.readFileSync(path.join(RESULTS_DIR, fileName), 'utf-8');
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

function extractDataFromAttachments(result, containerAttachmentsByUuid) {
  // allure-cucumberjs writes the Before-hook attachments (Browser, Attempts...) into a
  // separate *-container.json (befores[].steps[].attachments), linked via children: [uuid].
  // result.attachments is always empty; result.steps only holds the Gherkin steps' own attachments.
  const attachments = [
    ...collectAttachments(result),
    ...(containerAttachmentsByUuid.get(result.uuid) || [])
  ];

  let browser = 'unknown';
  let attempts = 1;

  for (const att of attachments) {
    if (!att.source) continue;

    const content = readAttachment(att.source);
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
      map.set(childUuid, attachments);
    }
  }

  return map;
}

function buildDashboard(results, containerAttachmentsByUuid) {
  const dashboard = {};

  for (const result of results) {
    const status = result.status || 'unknown';
    const { browser, attempts } = extractDataFromAttachments(result, containerAttachmentsByUuid);

    if (!dashboard[browser]) {
      dashboard[browser] = {
        total: 0,
        passed: 0,
        failed: 0,
        broken: 0,
        skipped: 0,
        retried: 0
      };
    }

    const d = dashboard[browser];

    d.total++;

    if (status === 'passed') d.passed++;
    else if (status === 'failed') d.failed++;
    else if (status === 'broken') d.broken++;
    else if (status === 'skipped') d.skipped++;

    if (attempts > 1) {
      d.retried++;
    }
  }

  for (const browser of Object.keys(dashboard)) {
    const d = dashboard[browser];

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
    lines.push('');
  }

  return lines.join('\n');
}

function writeEnvironment(dashboard) {
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
      lines.push(`${browser}_retried=${d.retried}`);
      lines.push(`${browser}_pass_rate=${d.passRate}%`);
      lines.push(`${browser}_failure_rate=${d.failureRate}%`);
      lines.push(`${browser}_retry_rate=${d.retryRate}%`);
      lines.push('');
    }
  }

  fs.writeFileSync(ENV_FILE, lines.join('\n'), 'utf-8');
}

function main() {
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
  const dashboard = buildDashboard(results, containerAttachmentsByUuid);
  const textReport = toText(dashboard);

  fs.writeFileSync(OUTPUT_JSON, JSON.stringify(dashboard, null, 2), 'utf-8');
  fs.writeFileSync(OUTPUT_TXT, textReport, 'utf-8');
  writeEnvironment(dashboard);

  console.log('\n===== BROWSER DASHBOARD =====\n');
  console.log(textReport);
}
main();