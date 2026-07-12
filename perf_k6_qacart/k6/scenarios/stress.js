// Stress — recherche du point de dégradation, volontairement conservateur.
// QACart Todo est une démo publique partagée (utilisée par d'autres apprenants),
// pas un environnement dédié : on ne pousse pas au point de rupture réel.
// En engagement client, ce scénario viserait un environnement de staging isolé
// avec des paliers bien plus élevés (100+ VUs).
import { sleep } from 'k6';
import { randomUser } from '../lib/testData.js';
import { registerUser, loginUser, getHomepage } from '../lib/api.js';

export const options = {
  stages: [
    { duration: '20s', target: 10 },
    { duration: '30s', target: 20 },
    { duration: '20s', target: 20 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1500'],
    http_req_failed: ['rate<0.05'],
  },
  tags: { scenario: 'stress' },
};

export default function () {
  getHomepage();
  const user = randomUser();
  registerUser(user);
  loginUser(user);
  sleep(0.5);
}
