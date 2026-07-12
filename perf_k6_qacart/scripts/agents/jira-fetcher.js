// ============================================
// Jira Fetcher — module partagé entre agents
// ============================================
// Importable par tout agent qui a besoin des données Jira.
//
// Usage:
//   const jira = require('./jira-fetcher');
//   await jira.assertJira();
//   const stories = await jira.fetchStories();
//   const issue   = await jira.fetchIssue('SCRUM-5');
//   await jira.createStory({ summary, description });
// ============================================

require('dotenv').config();
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

const https = require('https');

const JIRA_EMAIL    = process.env.JIRA_EMAIL;
const JIRA_TOKEN    = process.env.JIRA_TOKEN;
const JIRA_BASE_URL = (process.env.JIRA_BASE_URL || '').replace(/\/$/, '');
const JIRA_PROJECT  = process.env.JIRA_PROJECT || 'SCRUM';
const JIRA_BASE     = `${JIRA_BASE_URL}/rest/api/3`;
const JIRA_AUTH     = Buffer.from(`${JIRA_EMAIL}:${JIRA_TOKEN}`).toString('base64');

// ── HTTP GET ──────────────────────────────────────────────────────────────────
function jiraGet(path) {
  return new Promise((resolve, reject) => {
    https.get(`${JIRA_BASE}${path}`, {
      headers: { Authorization: `Basic ${JIRA_AUTH}`, Accept: 'application/json' }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { reject(new Error(`JSON parse error: ${data.slice(0, 200)}`)); }
      });
    }).on('error', reject);
  });
}

// ── HTTP POST ─────────────────────────────────────────────────────────────────
function jiraPost(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const url  = new URL(`${JIRA_BASE}${path}`);
    const req  = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        Authorization: `Basic ${JIRA_AUTH}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(d) }); }
        catch { reject(new Error(`JSON parse error: ${d.slice(0, 200)}`)); }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

// ── Extrait le texte du format ADF (Atlassian Document Format) ────────────────
function extractText(adf) {
  if (!adf) return '';
  if (typeof adf === 'string') return adf;
  const texts = [];
  function walk(node) {
    if (!node) return;
    if (node.type === 'text') texts.push(node.text);
    if (node.content) node.content.forEach(walk);
  }
  walk(adf);
  return texts.join(' ').slice(0, 500);
}

// ── Construit un ADF simple à partir d'un texte ───────────────────────────────
function toAdf(text) {
  return {
    type: 'doc', version: 1,
    content: [{ type: 'paragraph', content: [{ type: 'text', text: String(text) }] }]
  };
}

// ── Vérifie la connexion Jira ─────────────────────────────────────────────────
async function assertJira() {
  if (!JIRA_EMAIL || !JIRA_TOKEN || !JIRA_BASE_URL) {
    throw new Error('Config Jira manquante dans .env (JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN)');
  }
  const { status, body } = await jiraGet('/myself');
  if (status === 401 || status === 403) {
    throw new Error(`Jira auth échouée (${status}): ${body.message || JSON.stringify(body)}`);
  }
  return { displayName: body.displayName, email: body.emailAddress };
}

// ── Récupère les stories du projet ────────────────────────────────────────────
async function fetchStories(project = JIRA_PROJECT, maxResults = 50) {
  const jql = encodeURIComponent(`project = ${project} AND issuetype = Story ORDER BY created DESC`);
  const { body } = await jiraGet(`/search/jql?jql=${jql}&maxResults=${maxResults}&fields=summary,description,status,priority,assignee`);
  if (!body.issues) return [];
  return body.issues.map(issue => ({
    key: issue.key,
    summary: issue.fields.summary,
    status: issue.fields.status?.name || 'Unknown',
    priority: issue.fields.priority?.name || 'Medium',
    description: extractText(issue.fields.description),
    url: `${JIRA_BASE_URL}/browse/${issue.key}`
  }));
}

// ── Récupère une issue par clé ────────────────────────────────────────────────
async function fetchIssue(key) {
  const { body } = await jiraGet(`/issue/${key}?fields=summary,description,status,priority,comment`);
  return {
    key: body.key,
    summary: body.fields?.summary,
    status: body.fields?.status?.name,
    description: extractText(body.fields?.description),
    url: `${JIRA_BASE_URL}/browse/${body.key}`
  };
}

// ── Crée une story dans le projet ─────────────────────────────────────────────
async function createStory({ summary, description, project = JIRA_PROJECT }) {
  const { status, body } = await jiraPost('/issue', {
    fields: {
      project: { key: project },
      issuetype: { id: '10004' },
      summary,
      description: toAdf(description || summary)
    }
  });
  if (status !== 201) throw new Error(`Jira createStory failed (${status}): ${JSON.stringify(body)}`);
  return { key: body.key, url: `${JIRA_BASE_URL}/browse/${body.key}` };
}

// ── Ajoute un commentaire sur une issue ───────────────────────────────────────
async function addComment(key, text) {
  const { status, body } = await jiraPost(`/issue/${key}/comment`, { body: toAdf(text) });
  if (status !== 201) throw new Error(`addComment failed (${status}): ${JSON.stringify(body)}`);
  return body.id;
}

// ── Crée un Epic et y rattache des stories ────────────────────────────────────
async function createEpic({ summary, description, project = JIRA_PROJECT }) {
  const { status, body } = await jiraPost('/issue', {
    fields: {
      project:     { key: project },
      issuetype:   { id: '10001' },
      summary,
      description: toAdf(description || summary)
    }
  });
  if (status !== 201) throw new Error(`createEpic failed (${status}): ${JSON.stringify(body)}`);
  return { key: body.key, url: `${JIRA_BASE_URL}/browse/${body.key}` };
}

async function linkToEpic(epicKey, storyKeys = []) {
  const results = [];
  for (const key of storyKeys) {
    const { status, body } = await jiraPut(`/issue/${key}`, {
      fields: { parent: { key: epicKey } }
    });
    results.push({ key, ok: status === 204, error: status !== 204 ? body : null });
  }
  return results;
}

// ── HTTP PUT ──────────────────────────────────────────────────────────────────
function jiraPut(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const url  = new URL(`${JIRA_BASE}${path}`);
    const req  = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'PUT',
      headers: {
        Authorization: `Basic ${JIRA_AUTH}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: d ? JSON.parse(d) : {} }); }
        catch { resolve({ status: res.statusCode, body: d }); }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

module.exports = {
  assertJira,
  fetchStories,
  fetchIssue,
  createStory,
  createEpic,
  linkToEpic,
  addComment,
  JIRA_PROJECT,
  JIRA_BASE_URL
};
