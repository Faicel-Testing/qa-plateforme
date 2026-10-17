import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

async function assertDeletionRejected(world: CustomWorld): Promise<void> {
  if (!world.lastTodo || world.deleteAttemptFoundItem === undefined) {
    throw new Error('No todo deletion attempt recorded in World context');
  }

  const todo = new TodoPage(world.page);
  // Contrôler la tentative du When ; ne pas déclencher une seconde suppression ici.
  if (world.deleteAttemptFoundItem) {
    await todo.assertDeleteError();
    return;
  }
  await todo.assertTodoNotPresent(world.lastTodo);
}

When('I try to delete a non-existent todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const fakeTask = `non-existent-todo-${Date.now()}`;
  this.lastTodo = fakeTask; // nécessaire pour le Then suivant
  this.deleteAttemptFoundItem = await todo.tryDeleteTodo(fakeTask);
});

When('I try to delete the same todo item again', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo;
  if (!text) {
    throw new Error('No previously deleted todo available in World context');
  }
  this.deleteAttemptFoundItem = await todo.tryDeleteTodo(text);
});

When('I try to delete a todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.open();
});

Then('I should see an error or the deletion should be prevented', async function (this: CustomWorld) {
  await assertDeletionRejected(this);
});

Then('I should see an error or the deletion should fail', async function (this: CustomWorld) {
  await assertDeletionRejected(this);
});
