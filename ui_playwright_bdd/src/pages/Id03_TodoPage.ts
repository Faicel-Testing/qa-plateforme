import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class TodoPage extends BasePage {
  readonly addTodoButton: Locator;
  readonly newTodoInput: Locator;
  readonly submitNewTodoButton: Locator;
  readonly todoItems: Locator;
  readonly noTodosMessage: Locator;

  constructor(page: Page) {
    super(page);

    this.addTodoButton = page.locator('button:has(svg[data-testid="add"])').first();
    this.newTodoInput = page.locator('input[data-testid="new-todo"]').first();
    this.submitNewTodoButton = page.locator('button[data-testid="submit-newTask"]').first();
    this.todoItems = page.locator('[data-testid="todo-item"]');
    this.noTodosMessage = page.locator('[data-testid="no-todos"]').first();
  }

  async open(): Promise<void> {
    await this.goto('/todo');
    await this.page.waitForLoadState('domcontentloaded');
  }

  async addTodo(task: string): Promise<void> {
    await expect(this.addTodoButton).toBeVisible({ timeout: 10000 });
    await this.addTodoButton.click();
    await this.page.waitForURL(/\/todo\/new/, { timeout: 10000 });

    await expect(this.newTodoInput).toBeVisible({ timeout: 10000 });
    await this.newTodoInput.fill(task);
    await expect(this.submitNewTodoButton).toBeVisible({ timeout: 10000 });
    await this.submitNewTodoButton.click();
    await this.page.waitForURL(/\/todo$/i, { timeout: 10000 });
    await expect(this.todoItems.filter({ hasText: task }).first()).toBeVisible({ timeout: 10000 });
  }

  async attemptAddTodo(task: string): Promise<void> {
    await expect(this.addTodoButton).toBeVisible({ timeout: 10000 });
    await this.addTodoButton.click();
    await this.page.waitForURL(/\/todo\/new/, { timeout: 10000 });

    await expect(this.newTodoInput).toBeVisible({ timeout: 10000 });
    await this.newTodoInput.fill(task);
    await expect(this.submitNewTodoButton).toBeVisible({ timeout: 10000 });
    await this.submitNewTodoButton.click();
  }

  async tryDeleteTodo(task: string): Promise<boolean> {
    const item = this.todoItems.filter({ hasText: task }).first();
    const count = await item.count();

    if (count === 0) {
      return false;
    }

    const deleteButton = item.locator('button[data-testid="delete"]');
    await expect(deleteButton).toBeVisible({ timeout: 10000 });
    await deleteButton.click();
    await expect(deleteButton).toBeHidden({ timeout: 5000 }).catch(() => {});
    return true;
  }

  async deleteTodo(task: string): Promise<void> {
    const deleted = await this.tryDeleteTodo(task);
    if (!deleted) {
      throw new Error(`Todo item not found: ${task}`);
    }
    await expect(this.todoItems.filter({ hasText: task }).first()).toHaveCount(0, {
      timeout: 10000
    });
  }

  async assertTodoValidationError(expectedText?: RegExp | string): Promise<void> {
    const errorLocator = expectedText
      ? this.page.getByText(expectedText as any)
      : this.page.getByText(/required|cannot be empty|empty|duplicate|limit|character|invalid/i);

    await expect(errorLocator.first()).toBeVisible({ timeout: 10000 });
  }

  async assertDeleteError(expectedText?: RegExp | string): Promise<void> {
    const errorLocator = expectedText
      ? this.page.getByText(expectedText as any)
      : this.page.getByText(/not found|unable|cannot delete|error|already deleted/i);

    await expect(errorLocator.first()).toBeVisible({ timeout: 10000 });
  }

  async assertTodoExists(task: string): Promise<void> {
    await expect(this.todoItems.filter({ hasText: task }).first()).toBeVisible({ timeout: 10000 });
  }

  async assertTodoNotPresent(task: string): Promise<void> {
    await expect(this.todoItems.filter({ hasText: task })).toHaveCount(0, {
      timeout: 10000
    });
  }

  async assertTodoCompleted(task: string): Promise<void> {
    const item = this.todoItems.filter({ hasText: task }).first();
    await expect(item).toHaveClass(/completed|done|checked/i, { timeout: 10000 });
  }

  async assertEmptyList(): Promise<void> {
    await this.page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await expect(this.todoItems).toHaveCount(0, { timeout: 8_000 });
  }
}
