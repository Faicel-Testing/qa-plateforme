const p = require('./agents/plane-fetcher').client();
const timer = setTimeout(() => { console.error('Plane view operation timed out'); process.exit(1); }, 25000);
(async () => {
  const data = await p.request('views/');
  const rows = Array.isArray(data) ? data : data.results;
  const name = 'QA - Ordre croissant';
  const old = rows.find(v => v.name === name);
  console.log('Existing views checked');
  const body = {name, display_filters:{layout:'list',order_by:'created_at',group_by:null,sub_group_by:null,sub_issue:true},display_properties:{key:true,state:true,labels:true,priority:true}};
  const view = await p.request(old ? `views/${old.id}/` : 'views/', old ? 'PATCH' : 'POST', body);
  const saved = await p.request(`views/${view.id}/`);
  if (saved.display_filters?.order_by !== 'created_at') throw Error('Order not persisted');
  console.log(JSON.stringify({id:saved.id,name:saved.name,display_filters:saved.display_filters,verified:true}));
})().catch(e => {console.error(e.message);process.exitCode=1;}).finally(() => clearTimeout(timer));
