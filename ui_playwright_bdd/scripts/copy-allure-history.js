const fs = require('fs');
const path = require('path');

const source = path.resolve('allure-report', 'history');
const target = path.resolve('allure-results', 'history');

if (fs.existsSync(source)) {
  fs.mkdirSync(path.resolve('allure-results'), { recursive: true });
  fs.cpSync(source, target, { recursive: true, force: true });
  console.log('Allure history copied successfully.');
} else {
  console.log('No previous allure history found. First run maybe.');
}