/**
 * Page de base — méthodes partagées par tous les Page Objects.
 * Équivalent Cypress de src/pages/BasePage.ts (ui_playwright_bdd).
 * cy.get/.should ont un retry intégré — pas besoin de waitFor explicite comme Playwright.
 */
class BasePage {
  goto(path) {
    cy.visit(path);
  }

  refresh() {
    cy.reload();
  }

  logout() {
    cy.get('body').then(($body) => {
      const logoutSelector = 'button:contains("Logout"), button:contains("Sign out"), a:contains("Logout"), a:contains("Sign out")';
      if ($body.find(logoutSelector).length > 0) {
        cy.contains(/logout|sign out/i).click();
      } else {
        cy.visit('/logout');
      }
    });
  }

  assertOnLoginPage() {
    cy.url({ timeout: 10000 }).should('match', /\/login|\/signin|\/auth/i);
  }

  assertErrorMessage(expectedText) {
    const pattern = expectedText || /invalid|required|missing|weak|mismatch|already registered|not found|unable|cannot delete|error|duplicate|limit|character|please insert/i;
    cy.contains(pattern, { timeout: 15000 }).should('be.visible');
  }
}

module.exports = { BasePage };
