import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

When('I add a new todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = `Todo ${Date.now()}`;
  this.lastTodo = text;
  await todo.addTodo(text);
});

Then('I should see the new todo item in the list', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo;

  if (!text) {
    throw new Error('No todo text available in World context');
  }

  await todo.assertTodoExists(text);
});
