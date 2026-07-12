// Smoke — sanity check minimal : le parcours auth répond-il correctement, à faible charge ?
import { sleep } from 'k6';
import { randomUser } from '../lib/testData.js';
import { registerUser, loginUser, getHomepage } from '../lib/api.js';

export const options = {
  vus: 1,
  iterations: 5,
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
  tags: { scenario: 'smoke' },
};

export default function () {
  getHomepage();
  const user = randomUser();
  registerUser(user);
  loginUser(user);
  sleep(1);
}
