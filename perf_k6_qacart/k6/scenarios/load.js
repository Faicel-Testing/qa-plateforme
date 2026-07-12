// Load — charge nominale : simule un trafic quotidien réaliste sur le parcours auth.
import { sleep } from 'k6';
import { randomUser } from '../lib/testData.js';
import { registerUser, loginUser, loginWrongPassword, getHomepage } from '../lib/api.js';

export const options = {
  stages: [
    { duration: '20s', target: 5 },
    { duration: '40s', target: 8 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.98'],
  },
  tags: { scenario: 'load' },
};

export default function () {
  getHomepage();
  const user = randomUser();
  registerUser(user);
  loginUser(user);
  if (Math.random() < 0.1) loginWrongPassword(user.email, 'WrongPass!');
  sleep(1);
}
