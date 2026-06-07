const fs = require('fs');
const path = require('path');

const sources = [
  path.resolve('allure-results-chromium'),
  path.resolve('allure-results-firefox')
];

const target = path.resolve('allure-results');

if (!fs.existsSync(target)) {
  fs.mkdirSync(target, { recursive: true });
}

for (const source of sources) {
  if (!fs.existsSync(source)) {
    console.log(`Source not found: ${source}`);
    continue;
  }

  const folderName = path.basename(source);

  for (const file of fs.readdirSync(source)) {
    const sourceFile = path.join(source, file);
    const targetFile = path.join(target, `${folderName}-${file}`);

    fs.copyFileSync(sourceFile, targetFile);
  }
}

console.log('Allure results merged successfully.');