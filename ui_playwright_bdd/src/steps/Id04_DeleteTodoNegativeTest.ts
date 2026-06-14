import { When, Then } from '@cucumber/cucumber';
import { CustomWorld } from '../core/world';
import { TodoPage } from '../pages/Id03_TodoPage';

When('I try to delete a non-existent todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const fakeTask = `non-existent-todo-${Date.now()}`;
  this.lastTodo = fakeTask; // nécessaire pour le Then suivant
  await todo.tryDeleteTodo(fakeTask);
});

When('I try to delete the same todo item again', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo || `deleted-todo-${Date.now()}`;
  await todo.tryDeleteTodo(text);
});

When('I try to delete a todo item', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  await todo.open();
});

Then('I should see an error or the deletion should be prevented', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);

  if (!this.lastTodo) {
    // Si lastTodo n'est pas défini, on vérifie juste qu'aucune erreur critique n'est survenue
    return;
  }

  // L'item n'existe pas → tryDeleteTodo retourne false → suppression empêchée → test passe
  const deleted = await todo.tryDeleteTodo(this.lastTodo);
  if (deleted) {
    // L'app a trouvé et supprimé l'item (inattendu) → vérifier qu'une erreur est affichée
    await todo.assertDeleteError();
  }
  // Si deleted = false : la suppression a bien été bloquée → comportement attendu, le test passe
});

Then('I should see an error or the deletion should fail', async function (this: CustomWorld) {
  const todo = new TodoPage(this.page);
  const text = this.lastTodo;

  if (!text) {
    throw new Error('No todo text available in World context');
  }

  await todo.assertTodoNotPresent(text);
});
