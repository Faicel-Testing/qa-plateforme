const fs = require('fs');
const path = require('path');

const sources = [
  path.resolve('allure-results-chromium'),
  path.resolve('allure-results-firefox')
];
const target = path.resolve('allure-results');

fs.mkdirSync(target, { recursive: true });

for (const source of sources) {
  if (!fs.existsSync(source)) continue;

  for (const file of fs.readdirSync(source)) {
    fs.copyFileSync(
      path.join(source, file),
      path.join(target, `${path.basename(source)}-${file}`)
    );
  }
}