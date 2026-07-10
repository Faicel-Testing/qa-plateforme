const { BasePage } = require('./BasePage');

/**
 * Équivalent Cypress de src/pages/Id01_SignupPage.ts (ui_playwright_bdd).
 * Le fallback multi-sélecteur Playwright (getByTestId().or(css).or(placeholder))
 * devient un sélecteur CSS unique séparé par virgules (sémantique OR).
 */
class SignupPage extends BasePage {
  open() {
    this.goto('/signup');
  }

  fillSignupForm(firstName, lastName, email, password, confirmPassword) {
    const confirm = confirmPassword ?? password;
    this._fillField('[data-testid="first-name"], input[name="firstName"], [placeholder*="first name" i]', firstName);
    this._fillField('[data-testid="last-name"], input[name="lastName"], [placeholder*="last name" i]', lastName);
    this._fillField('[data-testid="email"], input[name="email"], [placeholder*="email" i]', email);
    this._fillField('[data-testid="password"], input[name="password"], [placeholder="password" i]', password);
    this._fillField('[data-testid="confirm-password"], input[name="confirmPassword"], [placeholder*="confirm password" i]', confirm);
  }

  // cy.type() refuse les chaînes vides — on se contente du clear() pour simuler un champ laissé vide
  _fillField(selector, value) {
    const field = cy.get(selector).first().should('be.visible').clear();
    if (value) cy.get(selector).first().type(value);
    return field;
  }

  signup(firstName, lastName, email, password, confirmPassword) {
    this.fillSignupForm(firstName, lastName, email, password, confirmPassword);
    cy.get('[data-testid="submit"], button').contains(/sign up|signup|register|create account/i).click();
  }

  assertSignupError(expectedText) {
    const pattern = expectedText || /invalid|required|missing|weak|mismatch|already registered|email/i;
    cy.contains(pattern, { timeout: 15000 }).should('be.visible');
  }

  assertSignedUp() {
    cy.url({ timeout: 10000 }).should('match', /dashboard|home|todo|tasks/i);
  }
}

module.exports = { SignupPage };
