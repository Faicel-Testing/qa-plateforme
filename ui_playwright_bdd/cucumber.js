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
  // parallel: chaque scénario a son propre Browser/World (voir src/core/world.ts) et
  // ses fixtures sont créées via API par scénario (plus de cache disque partagé) → safe
  // 2 workers : machine à 2 coeurs physiques / RAM limitée — 4 provoquait des crashs intermittents
  // retry: 1 — qacart-todo.herokuapp.com (démo publique) timeout parfois sous charge concurrente
  headless: {
    ...base,
    tags: '@regression and not @wip',
    parallel: 2,
    retry: 1
  },

  // Profil smoke
  smoke: {
    ...base,
    tags: '@smoke',
    parallel: 2,
    retry: 1
  },

  // Profil API Setup
  'api-setup': {
    ...base,
    tags: '@api-setup'
  }
};
