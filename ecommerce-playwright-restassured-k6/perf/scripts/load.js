// ============================================================
// K6 Load Test — AutomationExercise API
// Simule la charge normale de production (50 users simultanés)
// Usage: k6 run perf/scripts/load.js
// ============================================================
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://automationexercise.com';

export const errorRate        = new Rate('error_rate');
export const successRequests  = new Counter('success_requests');
export const p95Duration      = new Trend('p95_duration');

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Montée progressive à 10 VUs
    { duration: '1m',  target: 50 },   // Charge nominale : 50 VUs pendant 1 min
    { duration: '30s', target: 0  },   // Descente progressive
  ],
  thresholds: {
    http_req_failed:   ['rate<0.05'],   // < 5% d'erreurs HTTP
    http_req_duration: ['p(95)<5000'],  // 95% des requêtes < 5s
    http_req_duration: ['p(99)<8000'],  // 99% des requêtes < 8s
    error_rate:        ['rate<0.1'],    // < 10% erreurs custom
  },
};

export default function () {
  const userId = __VU;

  // Scénario 1 — Navigation catalogue (60% du trafic)
  if (userId % 5 !== 0) {
    const res = http.get(`${BASE_URL}/api/productsList`);
    p95Duration.add(res.timings.duration);
    const ok = check(res, {
      '[load] products 200':           r => r.status === 200,
      '[load] products responseCode':  r => r.json('responseCode') === 200,
      '[load] products duration < 5s': r => r.timings.duration < 5000,
    });
    errorRate.add(!ok);
    if (ok) successRequests.add(1);
  }

  sleep(Math.random() * 2 + 1);

  // Scénario 2 — Recherche produit (30% du trafic)
  const queries = ['top', 'dress', 'jean', 'shirt', 'men'];
  const query   = queries[Math.floor(Math.random() * queries.length)];
  const searchRes = http.post(
    `${BASE_URL}/api/searchProduct`,
    { search_product: query },
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  const searchOk = check(searchRes, {
    '[load] search 200':          r => r.status === 200,
    '[load] search has results':  r => r.json('products') !== null,
  });
  errorRate.add(!searchOk);

  sleep(Math.random() * 1 + 0.5);
}
