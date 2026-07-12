// Génère un utilisateur unique par itération — évite les collisions d'email
// entre VUs concurrents (chaque VU/iteration a un __VU/__ITER distinct dans k6).
export function randomUser() {
  const id = `${Date.now()}_${__VU}_${__ITER}_${Math.floor(Math.random() * 100000)}`;
  return {
    firstName: 'K6',
    lastName: 'LoadTest',
    email: `k6.perf.${id}@qacart-test.com`,
    password: 'K6Perf!2026',
  };
}
