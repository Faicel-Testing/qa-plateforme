import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 10,
  iterations: 20,         // shared-iterations → vos 20 itérations finissent vite, c'est ok
  duration: '30s',        // ignorée si les itérations finissent avant
};

const BASE_URL = 'https://gorest.co.in/public/v2/users'; // essaie aussi avec / à la fin si besoin
const TOKEN = __ENV.API_TOKEN; // >>> passe ton token via variable d'env

const params = {
  headers: {
    ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    Accept: 'application/json',
  },
};

export default function () {
  const res = http.get(BASE_URL, params);

  // Log de diagnostic (affiche quelques réponses pour comprendre)
  console.log(`status=${res.status} length=${res.body ? res.body.length : 0}`);
  // Pour voir le message d'erreur, décommente :
  // console.log(res.body);

  check(res, {
    'status is 2xx': (r) => r.status >= 200 && r.status < 300,
    'body not empty': (r) => !!r.body && r.body.length > 0,
  });
}
