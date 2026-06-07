import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

When('I delete the todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo;

  if (!text) {
    throw new Error('No todo text available in World context');
  }

  await todo.deleteTodo(text);
});

Then('I should not see the deleted todo item in the list', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo;

  if (!text) {
    throw new Error('No todo text available in World context');
  }

  await todo.assertTodoNotPresent(text);
});
