// ============================================================
// K6 Stress Test — AutomationExercise API
// Trouve le point de rupture — charge au-delà du nominal
// Usage: k6 run perf/scripts/stress.js
// ============================================================
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://automationexercise.com';

export const errorRate = new Rate('error_rate');

export const options = {
  stages: [
    { duration: '30s', target: 50  },   // Charge normale
    { duration: '30s', target: 100 },   // Au-delà du nominal
    { duration: '1m',  target: 200 },   // Stress : 200 VUs
    { duration: '30s', target: 0   },   // Récupération
  ],
  thresholds: {
    http_req_failed:   ['rate<0.1'],    // On tolère jusqu'à 10% d'erreurs en stress
    http_req_duration: ['p(95)<10000'], // 95% < 10s en stress
    error_rate:        ['rate<0.15'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/api/productsList`);
  const ok = check(res, {
    '[stress] status 200':        r => r.status === 200,
    '[stress] duration < 10s':    r => r.timings.duration < 10000,
    '[stress] has products':      r => {
      try { return r.json('products').length > 0; }
      catch { return false; }
    },
  });
  errorRate.add(!ok);
  sleep(0.5);
}
