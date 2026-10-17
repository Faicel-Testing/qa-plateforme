require('dotenv').config({ quiet: true });
(async () => {
  const { collect, importStories } = require('./agents/shared/plane-stories');
  if (process.argv.includes('--dry-run')) { console.log(JSON.stringify(collect().map(({ externalId, summary, domain, priority, files }) => ({ externalId, summary, domain, priority, files })), null, 2)); return; }
  if (!process.argv.includes('--apply')) throw Error('Use --dry-run or --apply');
  console.log(JSON.stringify(await importStories(require('./agents/plane-fetcher').client()), null, 2));
})().catch(e => { console.error(e.message); process.exitCode = 1; });
