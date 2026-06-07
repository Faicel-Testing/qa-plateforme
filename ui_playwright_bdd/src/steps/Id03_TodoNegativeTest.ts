import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

When('I try to add an empty todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.attemptAddTodo('');
});

When('I try to add a todo with only whitespace', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.attemptAddTodo('    ');
});

When('I try to add a todo exceeding the character limit', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const longTask = 'A'.repeat(250);
  await todo.attemptAddTodo(longTask);
});

When('I try to add a todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.open();
});

Then('I should see a validation error or the todo should not be added', async function (this: CustomWorld) {
  const errorVisible = await this.page
    .getByText(/required|cannot be empty|empty|duplicate|limit|character|invalid/i)
    .first()
    .isVisible()
    .catch(() => false);

  if (errorVisible) return;

  await this.page.waitForURL(/\/todo$/i, { timeout: 5000 }).catch(() => {});
  const items = this.page.locator('[data-testid="todo-item"]');
  const count = await items.count();
  for (let i = 0; i < count; i++) {
    const text = (await items.nth(i).textContent()) ?? '';
    if (text.trim() === '') {
      throw new Error('Whitespace-only todo was added — app should reject it');
    }
  }
});

Then('I should see a length validation error', async function (this: CustomWorld) {
  const errorVisible = await this.page
    .getByText(/limit|character|long|maximum|too long/i)
    .first()
    .isVisible()
    .catch(() => false);

  if (errorVisible) return;

  await this.page.waitForURL(/\/todo$/i, { timeout: 5000 }).catch(() => {});
  const longTask = 'A'.repeat(250);
  const todo = new TodoPage(this.page);
  await todo.assertTodoNotPresent(longTask);
});
