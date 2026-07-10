const { defineConfig } = require('cypress');
const createBundler = require('@bahmutov/cypress-esbuild-preprocessor');
const { addCucumberPreprocessorPlugin } = require('@badeball/cypress-cucumber-preprocessor');
const { createEsbuildPlugin } = require('@badeball/cypress-cucumber-preprocessor/esbuild');
const { allureCypress } = require('allure-cypress/reporter');
const path = require('path');
const { writeCategoriesJson, writeEnvironmentProperties, persistHistory, restoreHistory } = require('./cypress/support/reporting/allureKpi');

require('dotenv').config();

const FRAMEWORK_ROOT = __dirname;
const RESULTS_DIR = path.join(FRAMEWORK_ROOT, 'allure-results');

module.exports = defineConfig({
  e2e: {
    baseUrl: process.env.BASE_URL || 'https://qacart-todo.herokuapp.com',
    specPattern: 'cypress/e2e/features/**/*.feature',
    supportFile: 'cypress/support/e2e.js',
    defaultCommandTimeout: 10000,
    pageLoadTimeout: 30000,
    video: true,
    screenshotOnRunFailure: true,
    retries: {
      runMode: 2,
      openMode: 0
    },
    env: {
      allureResultsPath: 'allure-results'
    },
    async setupNodeEvents(on, config) {
      await addCucumberPreprocessorPlugin(on, config);
      allureCypress(on, config);

      on(
        'file:preprocessor',
        createBundler({
          plugins: [createEsbuildPlugin(config)]
        })
      );

      on('before:run', () => {
        writeCategoriesJson(RESULTS_DIR);
        restoreHistory(FRAMEWORK_ROOT, RESULTS_DIR);
      });

      on('after:run', (results) => {
        writeEnvironmentProperties(RESULTS_DIR, results, config);
      });

      return config;
    }
  }
});
