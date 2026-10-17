require('dotenv').config({ quiet: true });
const apply = process.argv.includes('--apply');
if (!apply && !process.argv.includes('--dry-run')) { console.error('Use --dry-run or --apply'); process.exitCode = 1; }
else require('./agents/shared/plane-testcases').sync(require('./agents/plane-fetcher').client(), { apply }).then(r => console.log(JSON.stringify(r, null, 2))).catch(e => { console.error(e.message); process.exitCode = 1; });
