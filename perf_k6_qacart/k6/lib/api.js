import http from 'k6/http';
import { check } from 'k6';
import { BASE_URL } from '../config/env.js';

// Surface API réelle de QACart Todo — confirmée par sondage direct (curl) :
//   POST /api/v1/users/register  → 201, { access_token, userID, firstName }
//   POST /api/v1/users/login     → 200 (creds valides) / 401 (email connu, mdp faux)
// Le todo CRUD est 100% client-side (React) : GET/POST /api/v1/todos renvoient
// le shell SPA (catch-all route), pas une API REST. k6 ne peut donc pas le
// charger-tester au niveau protocole — voir README pour le détail.
//
// 401/400 sont des statuts métier ATTENDUS sur le chemin négatif, pas des pannes
// transport. Sans expectedStatuses, k6 les compte dans http_req_failed (taux
// d'erreur pollué par des tests négatifs volontaires) — on déclare donc
// explicitement quels codes sont "OK" au niveau protocole ; la validation
// métier réelle reste portée par les check() ci-dessous.
http.setResponseCallback(http.expectedStatuses(200, 201, 400, 401));

export function getHomepage() {
  const res = http.get(BASE_URL, { tags: { name: 'GET /' } });
  check(res, { 'homepage status 200': (r) => r.status === 200 });
  return res;
}

export function registerUser(user) {
  const res = http.post(
    `${BASE_URL}/api/v1/users/register`,
    JSON.stringify({
      firstName: user.firstName,
      lastName: user.lastName,
      email: user.email,
      password: user.password,
    }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'POST /api/v1/users/register' } }
  );
  check(res, { 'register status 201': (r) => r.status === 201 });
  return res;
}

export function loginUser(user) {
  const res = http.post(
    `${BASE_URL}/api/v1/users/login`,
    JSON.stringify({ email: user.email, password: user.password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'POST /api/v1/users/login' } }
  );
  check(res, { 'login status 200': (r) => r.status === 200 });
  return res;
}

// Email existant + mauvais mot de passe → 401 (confirmé par sondage direct).
// Email inconnu → 400 "email not found" (chemin différent, non testé ici).
export function loginWrongPassword(email, password) {
  const res = http.post(
    `${BASE_URL}/api/v1/users/login`,
    JSON.stringify({ email, password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'POST /api/v1/users/login (wrong password)' } }
  );
  check(res, { 'wrong password status 401': (r) => r.status === 401 });
  return res;
}
