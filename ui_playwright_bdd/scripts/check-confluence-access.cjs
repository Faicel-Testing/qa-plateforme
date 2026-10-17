'use strict';
// Read-only diagnostics. Never prints credentials, page bodies or account details.
const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const tls = require('node:tls');
const root = path.resolve(__dirname, '..');
require('dotenv').config({ path: path.join(root, '.env'), quiet: true });
const bridge = require('./agents/shared/confluence-rag');
const config = bridge.config(root);
const host = new URL(config.baseUrl).hostname;
const env = process.env;
function request(route, authenticated, hostname = host) {
  return new Promise(resolve => {
    const ca = env.CONFLUENCE_CA_FILE ? [...tls.rootCertificates,
      fs.readFileSync(path.resolve(root, env.CONFLUENCE_CA_FILE), 'utf8')] : undefined;
    let raw = '';
    const req = https.request({ hostname, port: 443, path: route, method: 'GET',
      rejectUnauthorized: true, ...(ca ? { ca } : {}), headers: {
        Accept: 'application/json', ...(authenticated ? { Authorization: 'Basic ' +
          Buffer.from(env.CONFLUENCE_EMAIL + ':' + env.CONFLUENCE_API_TOKEN).toString('base64') } : {}),
      } }, res => {
      res.setEncoding('utf8');
      res.on('error', () => resolve({ route, errorCode: 'RESPONSE_INTERRUPTED' }));
      res.on('data', chunk => { raw += chunk; if (raw.length > 1048576) req.destroy(new Error('Response too large')); });
      res.on('end', () => {
        let body = {}; try { body = JSON.parse(raw); } catch { /* HTML error page. */ }
        const message = JSON.stringify(body.message || body.errors || body.errorMessages || body.error || '');
        const reasons = ['permission', 'permitted', 'unauthorized', 'not found', 'license', 'expired', 'scope', 'authenticated', 'access']
          .filter(word => message.toLowerCase().includes(word));
        resolve({ hostname, route, status: res.statusCode, contentType: res.headers['content-type'],
          ...(res.statusCode >= 400 ? { diagnostic: bridge.clean(message, env).slice(0, 500) } : {}),
          ...(body.cloudId ? { cloudId: body.cloudId } : {}),
          ...(route.includes('/pages/') && body.id ? { id: body.id, spaceId: body.spaceId, statusName: body.status } : {}),
          reasons });
      });
    });
    req.setTimeout(15000, () => req.destroy(new Error('Request timed out')));
    req.on('error', error => resolve({ route, errorCode: error.code || 'NETWORK_ERROR' }));
    req.end();
  });
}
(async () => {
  if (!env.CONFLUENCE_EMAIL || !env.CONFLUENCE_API_TOKEN) throw new Error('Confluence credentials missing');
  for (const [route, auth] of [['/_edge/tenant_info', false], ['/wiki/rest/api/user/current', true],
    ['/wiki/api/v2/spaces/' + config.spaceId, true],
    ['/wiki/api/v2/pages/' + config.rootPageId + '?body-format=storage', true]]) {
    console.log(JSON.stringify(await request(route, auth)));
  }
  if (process.argv.includes('--platform')) {
    const tenant = await request('/_edge/tenant_info', false);
    if (!/^[a-f0-9-]{36}$/i.test(tenant.cloudId || '')) throw new Error('Cloud identity unavailable');
    for (const route of ['/wiki/api/v2/spaces/' + config.spaceId,
      '/wiki/api/v2/pages/' + config.rootPageId + '?body-format=storage']) {
      console.log(JSON.stringify(await request('/ex/confluence/' + tenant.cloudId + route, true, 'api.atlassian.com')));
    }
  }
})().catch(() => { console.error('Confluence diagnostic failed; check local configuration.'); process.exitCode = 1; });
