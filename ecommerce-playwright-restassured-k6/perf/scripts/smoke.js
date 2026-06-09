// ============================================================
// K6 Smoke Test — AutomationExercise API
// Vérifie que les endpoints principaux répondent correctement
// Usage: k6 run perf/scripts/smoke.js
// ============================================================
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://automationexercise.com';

export const errorRate  = new Rate('error_rate');
export const productDuration = new Trend('products_duration');
export const searchDuration  = new Trend('search_duration');

export const options = {
  vus: 1,
  iterations: 5,
  thresholds: {
    http_req_failed:   ['rate<0.01'],       // < 1% d'erreurs
    http_req_duration: ['p(95)<3000'],      // 95% < 3s
    error_rate:        ['rate<0.05'],       // < 5% erreurs custom
  },
};

export default function () {
  // TC-PERF-001 — GET /api/productsList
  const productsRes = http.get(`${BASE_URL}/api/productsList`);
  productDuration.add(productsRes.timings.duration);
  const productsOk = check(productsRes, {
    '[smoke] products status 200':        r => r.status === 200,
    '[smoke] products responseCode 200':  r => r.json('responseCode') === 200,
    '[smoke] products list not empty':    r => r.json('products').length > 0,
    '[smoke] products response < 3s':     r => r.timings.duration < 3000,
  });
  errorRate.add(!productsOk);

  sleep(1);

  // TC-PERF-002 — GET /api/brandsList
  const brandsRes = http.get(`${BASE_URL}/api/brandsList`);
  const brandsOk = check(brandsRes, {
    '[smoke] brands status 200':       r => r.status === 200,
    '[smoke] brands responseCode 200': r => r.json('responseCode') === 200,
    '[smoke] brands list not empty':   r => r.json('brands').length > 0,
  });
  errorRate.add(!brandsOk);

  sleep(1);

  // TC-PERF-003 — POST /api/searchProduct
  const searchRes = http.post(
    `${BASE_URL}/api/searchProduct`,
    { search_product: 'top' },
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  searchDuration.add(searchRes.timings.duration);
  const searchOk = check(searchRes, {
    '[smoke] search status 200':       r => r.status === 200,
    '[smoke] search responseCode 200': r => r.json('responseCode') === 200,
    '[smoke] search results not empty': r => r.json('products').length > 0,
  });
  errorRate.add(!searchOk);

  sleep(1);
}
