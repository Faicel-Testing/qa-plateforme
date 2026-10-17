require('dotenv').config({ quiet:true });
const path = require('node:path'), fs = require('node:fs');
const root = path.resolve(__dirname,'..');
(async()=>{
  const args=process.argv.slice(2);
  if (!args.includes('--apply') && !args.includes('--dry-run')) throw Error('Use --dry-run or --apply');
  const run = JSON.parse(fs.readFileSync(path.join(root,'logs/latest-test-run.json'),'utf8')).runId;
  if (!/^[a-zA-Z0-9-]+$/.test(run)) throw Error('Invalid run ID');
  const report = await require('./agents/shared/plane-results').syncResults(require('./agents/plane-fetcher').client(),path.join(root,'allure-runs',run,'results'),{ apply:args.includes('--apply'), pace:1100 });
  console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
