'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { randomBytes } = require('node:crypto');
const root = path.resolve(__dirname, '..');
const directory = path.join(root, '.langfuse');
fs.mkdirSync(directory, { recursive: true });
const secretsFile = path.join(directory, 'secrets.json');
let secrets;
if (fs.existsSync(secretsFile)) secrets = JSON.parse(fs.readFileSync(secretsFile, 'utf8'));
else {
  const secret = () => randomBytes(32).toString('hex');
  secrets = Object.fromEntries(['POSTGRES_PASSWORD', 'CLICKHOUSE_PASSWORD', 'REDIS_PASSWORD', 'MINIO_PASSWORD', 'SALT', 'ENCRYPTION_KEY', 'NEXTAUTH_SECRET', 'ADMIN_PASSWORD'].map(k => [k, secret()]));
  secrets.LANGFUSE_PUBLIC_KEY = 'pk-lf-' + secret();
  secrets.LANGFUSE_SECRET_KEY = 'sk-lf-' + secret();
  fs.writeFileSync(secretsFile, JSON.stringify(secrets, null, 2));
}
fs.writeFileSync(path.join(directory, 'compose.env'), Object.entries(secrets).map(([k, v]) => `${k}=${v}`).join('\n') + '\n');
fs.writeFileSync(path.join(directory, 'connexion.txt'), `URL: http://localhost:3000\nEmail: qa-admin@localhost.test\nPassword: ${secrets.ADMIN_PASSWORD}\n`);
const envFile = path.join(root, '.env');
let env = fs.existsSync(envFile) ? fs.readFileSync(envFile, 'utf8') : '';
for (const [key, value] of Object.entries({ LANGFUSE_ENABLED: 'true', LANGFUSE_BASE_URL: 'http://127.0.0.1:3000',
  LANGFUSE_PUBLIC_KEY: secrets.LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY: secrets.LANGFUSE_SECRET_KEY })) {
  const re = new RegExp('^' + key + '=.*$', 'gm');
  env = re.test(env) ? env.replace(re, `${key}=${value}`) : env + `\n${key}=${value}`;
}
fs.writeFileSync(envFile, env);
console.log('Langfuse local configuration prepared. Login details: .langfuse/connexion.txt (never commit).');
