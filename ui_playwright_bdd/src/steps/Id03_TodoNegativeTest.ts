import { When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

// Règle cible proposée : 1 à 200 caractères après trim (docs/todo-validation.md).
const TODO_MAX_LENGTH = 200;

async function attemptInvalidTodo(world: CustomWorld, text: string): Promise<void> {
  const todo = new TodoPage(world.page);
  await expect(todo.noTodosMessage.or(todo.todoItems.first()).first()).toBeVisible({ timeout: 10000 });
  world.todoCountBeforeAttempt = await todo.todoItems.count();
  await todo.attemptAddTodo(text);
}

When('I try to add an empty todo item', async function (this: CustomWorld) {
  await attemptInvalidTodo(this, '');
});

When('I try to add a todo with only whitespace', async function (this: CustomWorld) {
  await attemptInvalidTodo(this, '    ');
});

When('I try to add a todo exceeding the character limit', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const longTask = 'A'.repeat(TODO_MAX_LENGTH + 1);
  await todo.attemptAddTodo(longTask);
});

When('I try to add a todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.open();
});

Then('I should see a validation error or the todo should not be added', async function (this: CustomWorld) {
  if (this.todoCountBeforeAttempt === undefined) {
    throw new Error('No todo creation attempt recorded in World context');
  }
  const errorLocator = this.page
    .getByText(/required|cannot be empty|empty|duplicate|limit|character|invalid/i)
    .first();

  const errorVisible = await errorLocator
    .waitFor({ state: 'visible', timeout: 8000 })
    .then(() => true)
    .catch(() => false);

  if (errorVisible) return;

  // Sans erreur visible, vérifier la liste rechargée et attendre sa fin de chargement.
  const todo = new TodoPage(this.page);
  await todo.open();
  await expect(todo.noTodosMessage.or(todo.todoItems.first()).first()).toBeVisible({ timeout: 10000 });
  await expect(todo.todoItems, 'An invalid todo must not be added').toHaveCount(this.todoCountBeforeAttempt);
});

Then('I should see a length validation error', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.assertTodoValidationError(/limit|character|long|maximum|too long/i);
});
