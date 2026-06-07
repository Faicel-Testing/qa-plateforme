module.exports = {
  default: {
    formatOptions: {
      resultsDir: 'allure-results'
    },
    requireModule: ['ts-node/register'],
    require: [
      'src/core/world.ts',
      'src/hooks/**/*.ts',
      'src/steps/**/*.ts'
    ],
    paths: ['src/features/**/*.feature'],
    format: ['progress', 'allure-cucumberjs/reporter'],
    formatOptions: {
      resultsDir: 'allure-results'
    }
  }
};