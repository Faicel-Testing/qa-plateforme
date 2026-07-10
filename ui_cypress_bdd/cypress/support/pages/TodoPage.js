const { BasePage } = require('./BasePage');

/** Équivalent Cypress de src/pages/Id03_TodoPage.ts (ui_playwright_bdd). */
class TodoPage extends BasePage {
  open() {
    this.goto('/todo');
  }

  addTodo(task) {
    cy.get('button:has(svg[data-testid="add"])', { timeout: 10000 }).first().should('be.visible').click();
    cy.url({ timeout: 10000 }).should('match', /\/todo\/new/);

    cy.get('input[data-testid="new-todo"]', { timeout: 10000 }).first().should('be.visible').clear().type(task);
    cy.get('button[data-testid="submit-newTask"]', { timeout: 10000 }).first().should('be.visible').click();

    cy.url({ timeout: 10000 }).should('match', /\/todo$/i);
    cy.contains('[data-testid="todo-item"]', task, { timeout: 10000 }).should('be.visible');
  }

  attemptAddTodo(task) {
    cy.get('button:has(svg[data-testid="add"])', { timeout: 10000 }).first().should('be.visible').click();
    cy.url({ timeout: 10000 }).should('match', /\/todo\/new/);

    // cy.type() refuse les chaînes vides — le clear() suffit à simuler un champ laissé vide
    cy.get('input[data-testid="new-todo"]', { timeout: 10000 }).first().should('be.visible').clear();
    if (task) cy.get('input[data-testid="new-todo"]').first().type(task);
    cy.get('button[data-testid="submit-newTask"]', { timeout: 10000 }).first().should('be.visible').click();
  }

  // Retourne (via alias '@deleted') true/false — miroir de tryDeleteTodo(): Promise<boolean> côté Playwright
  tryDeleteTodo(task) {
    cy.get('body').then(($body) => {
      const item = $body.find('[data-testid="todo-item"]').filter((_, el) => el.textContent.includes(task));
      if (item.length === 0) {
        cy.wrap(false).as('deleted');
        return;
      }
      cy.wrap(item.first()).find('button[data-testid="delete"]').should('be.visible').click();
      cy.wrap(true).as('deleted');
    });
  }

  deleteTodo(task) {
    this.tryDeleteTodo(task);
    cy.get('@deleted').then((deleted) => {
      if (!deleted) throw new Error(`Todo item not found: ${task}`);
    });
    cy.contains('[data-testid="todo-item"]', task, { timeout: 10000 }).should('not.exist');
  }

  assertTodoValidationError(expectedText) {
    const pattern = expectedText || /required|cannot be empty|empty|duplicate|limit|character|invalid/i;
    cy.contains(pattern, { timeout: 10000 }).should('be.visible');
  }

  assertDeleteError(expectedText) {
    const pattern = expectedText || /not found|unable|cannot delete|error|already deleted/i;
    cy.contains(pattern, { timeout: 10000 }).should('be.visible');
  }

  assertTodoExists(task) {
    cy.contains('[data-testid="todo-item"]', task, { timeout: 10000 }).should('be.visible');
  }

  assertTodoNotPresent(task) {
    cy.contains('[data-testid="todo-item"]', task, { timeout: 10000 }).should('not.exist');
  }

  assertEmptyList() {
    cy.get('[data-testid="todo-item"]').should('not.exist');
  }
}

module.exports = { TodoPage };
