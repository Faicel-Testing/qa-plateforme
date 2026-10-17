'use strict';
require('dotenv').config({ quiet: true });
const https = require('node:https');
const fs = require('node:fs');
const path = require('node:path');
function config(env = process.env) {
  const workspace = env.PLANE_WORKSPACE, project = env.PLANE_PROJECT_ID;
  if (!/^[a-z0-9-]+$/.test(workspace || '') || !/^[a-f0-9-]{36}$/i.test(project || '') || !env.PLANE_API_KEY) throw Error('Plane configuration missing or invalid');
  return { workspace, project, token: env.PLANE_API_KEY };
}
function client(env = process.env, transport = https.request) {
  const cfg = config(env);
  const ca = env.PLANE_CA_FILE ? [...require('node:tls').rootCertificates, fs.readFileSync(path.resolve(__dirname, '../..', env.PLANE_CA_FILE), 'utf8')] : undefined;
  const base = `/api/v1/workspaces/${cfg.workspace}/projects/${cfg.project}/`;
  async function request(route = '', method = 'GET', body) {
    if (!/^[a-zA-Z0-9_/?=&%.-]*$/.test(route) || route.includes('..') || route.startsWith('/')) throw Error('Invalid Plane route');
    return new Promise((resolve, reject) => {
      const data = body === undefined ? undefined : JSON.stringify(body);
      const req = transport({ hostname: 'api.plane.so', port: 443, path: base + route, method, rejectUnauthorized: true, ...(ca ? { ca } : {}),
        headers: { 'X-API-Key': cfg.token, Accept: 'application/json', ...(data ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } : {}) } }, res => {
        let raw = '';
        res.setEncoding?.('utf8');
        res.on('error', () => reject(Error('Plane response interrupted')));
        res.on('data', chunk => { raw += chunk; if (raw.length > 10000000) req.destroy(); });
        res.on('end', () => {
          if (res.statusCode < 200 || res.statusCode >= 300) return reject(Error(`Plane ${method} failed (HTTP ${res.statusCode})`));
          try { resolve(raw ? JSON.parse(raw) : {}); } catch { reject(Error('Invalid Plane response')); }
        });
      });
      req.setTimeout(30000, () => req.destroy(Error('timeout')));
      req.on('error', e => reject(Error('Plane network/TLS request failed' + (/^[A-Z_]+$/.test(e.code || '') ? ` (${e.code})` : ''))));
      if (data) req.write(data);
      req.end();
    });
  }
  async function list(route) {
    const rows = [], seen = new Set();
    let cursor;
    for (let page = 0; page < 100; page++) {
      const data = await request(route + (route.includes('?') ? '&' : '?') + 'per_page=100' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''));
      const items = Array.isArray(data) ? data : data.results;
      if (!Array.isArray(items)) throw Error('Invalid Plane list response');
      rows.push(...items);
      if (!data.next_page_results) return rows;
      if (!data.next_cursor || seen.has(data.next_cursor)) throw Error('Invalid Plane pagination');
      cursor = data.next_cursor; seen.add(cursor);
    }
    throw Error('Plane pagination limit exceeded');
  }
  function normalized(item, project, states = []) {
    return { key: `${project.identifier}-${item.sequence_id}`, id: item.id, summary: item.name,
      description: item.description_stripped || String(item.description_html || '').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>'),
      status: states.find(s => s.id === item.state)?.name || 'Unknown', priority: item.priority || 'none',
      url: `https://app.plane.so/${cfg.workspace}/projects/${cfg.project}/issues/${item.id}`,
      externalId: item.external_id, provider: 'plane' };
  }
  async function fetchStories() {
    const project = await request(), states = await list('states/'), items = await list('work-items/');
    const labels = await list('labels/');
    const storyLabels = labels.filter(l => /^(user story|story)$/i.test(l.name)).map(l => l.id);
    return items.filter(i => i.external_source === 'ui_playwright_bdd' || /^\[(?:SCRUM-|Id)/.test(i.name) || (i.labels || []).some(l => storyLabels.includes(l.id || l))).map(i => normalized(i, project, states));
  }
  async function fetchIssue(key) {
    const project = await request();
    const items = await list('work-items/');
    const item = items.find(i => i.id === key || `${project.identifier}-${i.sequence_id}` === key || i.external_id === key);
    if (!item) throw Error('Plane work item not found in configured project');
    return normalized(await request(`work-items/${item.id}/`), project, await list('states/'));
  }
  return { request, list, fetchStories, fetchIssue, assertConnection: () => request(), cfg };
}
module.exports = { client, config, assertConnection: () => client().request(), fetchStories: () => client().fetchStories(), fetchIssue: key => client().fetchIssue(key) };
