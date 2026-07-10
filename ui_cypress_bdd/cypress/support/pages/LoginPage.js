const { BasePage } = require('./BasePage');

/** Équivalent Cypress de src/pages/Id02_LoginPage.ts (ui_playwright_bdd). */
class LoginPage extends BasePage {
  open() {
    this.goto('/login');
  }

  login(email, password) {
    cy.get('[data-testid="email"], input[name="email"], [placeholder*="email" i]')
      .first().should('be.visible').clear();
    if (email) cy.get('[data-testid="email"], input[name="email"], [placeholder*="email" i]').first().type(email);
    cy.get('[data-testid="password"], input[name="password"], [placeholder="password" i]')
      .first().should('be.visible').clear();
    if (password) cy.get('[data-testid="password"], input[name="password"], [placeholder="password" i]').first().type(password);
    cy.get('[data-testid="submit"], button').contains(/login|sign in/i).click();
  }

  assertLoggedIn() {
    cy.url({ timeout: 10000 }).should('match', /todo|tasks|home|dashboard/i);
    cy.get('button:has(svg[data-testid="add"])', { timeout: 10000 }).should('be.visible');
  }

  assertLoginError() {
    cy.contains(/not correct|combination.*not|invalid|wrong|could not find|incorrect|email.*password|required|please/i, { timeout: 15000 })
      .should('be.visible');
  }
}

module.exports = { LoginPage };
