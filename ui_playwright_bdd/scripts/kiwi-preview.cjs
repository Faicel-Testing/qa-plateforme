'use strict';
// Local preparation only: no credentials, network requests or test execution.
const fs = require('node:fs');
const path = require('node:path');
const { scenarios } = require('./agents/shared/plane-testcases');
const root = path.resolve(__dirname, '..');
const files = fs.readdirSync(path.join(root, 'src/features')).filter(f => f.endsWith('.feature')).sort();
const cases = files.flatMap(f => scenarios('src/features/' + f, root));
const directory = path.join(root, 'logs/kiwi');
fs.mkdirSync(directory, { recursive: true });
fs.writeFileSync(path.join(directory, 'testcases-preview.json'), JSON.stringify({ published: false, cases }, null, 2));
console.log(JSON.stringify({ files: files.length, cases: cases.length, preview: 'logs/kiwi/testcases-preview.json', published: false }));
