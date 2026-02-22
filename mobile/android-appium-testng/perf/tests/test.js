import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 100,             // 🔹 100 utilisateurs virtuels
  iterations:200,
  duration: '30s',      // 🔹 Test sur 30 secondes
};

export default function () {
  const res = http.get('https://test.k6.io');
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}