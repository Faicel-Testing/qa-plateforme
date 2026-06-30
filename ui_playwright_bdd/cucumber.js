const base = {
  requireModule: ['ts-node/register'],
  require: [
    'src/core/world.ts',
    'src/hooks/**/*.ts',
    'src/steps/**/*.ts'
  ],
  paths: ['src/features/**/*.feature'],
  format: ['progress', 'allure-cucumberjs/reporter'],
  formatOptions: { resultsDir: 'allure-results' }
};

module.exports = {
  // Profil par défaut — tous les tests
  default: base,

  // Profil headless — @regression uniquement, tags gérés ici (pas en CLI)
  headless: {
    ...base,
    tags: '@regression and not @wip'
  },

  // Profil smoke
  smoke: {
    ...base,
    tags: '@smoke'
  },

  // Profil API Setup
  'api-setup': {
    ...base,
    tags: '@api-setup'
  }
};
