/**
 * Client HTTP léger basé sur cy.request() (built-in Cypress, zéro dépendance ajoutée).
 * Équivalent Cypress de src/api/QACartApiClient.ts (ui_playwright_bdd) qui utilisait
 * playwright/test's request.newContext().
 *
 * Pattern Senior : les préconditions de test ne passent jamais par l'UI signup.
 *   POST /api/v1/users/register  → crée l'utilisateur en base, retourne JWT
 *   POST /api/v1/users/login     → authentifie un user existant, retourne JWT
 *
 * Retourne un Cypress.Chainable<string> (le token) — s'utilise avec .then(token => ...).
 */
class QACartApiClient {
  register(user) {
    return cy
      .request({
        method: 'POST',
        url: '/api/v1/users/register',
        body: {
          firstName: user.firstName,
          lastName: user.lastName,
          email: user.email,
          password: user.password
        },
        failOnStatusCode: false
      })
      .then((response) => {
        if (response.status < 200 || response.status >= 300) {
          throw new Error(`POST /api/v1/users/register → HTTP ${response.status}\n${JSON.stringify(response.body)}`);
        }
        return response.body?.token ?? '';
      });
  }

  login(user) {
    return cy
      .request({
        method: 'POST',
        url: '/api/v1/users/login',
        body: { email: user.email, password: user.password },
        failOnStatusCode: false
      })
      .then((response) => {
        if (response.status < 200 || response.status >= 300) {
          throw new Error(`POST /api/v1/users/login → HTTP ${response.status}\n${JSON.stringify(response.body)}`);
        }
        return response.body?.token ?? '';
      });
  }
}

module.exports = { QACartApiClient };
