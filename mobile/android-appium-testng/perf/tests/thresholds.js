import http from 'k6/http';

export const options = {
  vus: 2,
  iterations: 2,
  thresholds:{
  http_req_failed: ['rate<0.01'],         // moins de 1% d’échecs
  http_req_duration: ['p(95)<200'],        // 95% des requêtes < 200ms
}
}

const url = "https://k6.io";

export default function () {
  http.get(url);
}
