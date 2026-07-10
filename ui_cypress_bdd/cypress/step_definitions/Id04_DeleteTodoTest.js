const { When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { TodoPage } = require('../support/pages/TodoPage');

When('I delete the todo item', function () {
  const text = this.lastTodo;
  if (!text) {
    throw new Error('No todo text available in scenario context');
  }
  new TodoPage().deleteTodo(text);
});

Then('I should not see the deleted todo item in the list', function () {
  const text = this.lastTodo;
  if (!text) {
    throw new Error('No todo text available in scenario context');
  }
  new TodoPage().assertTodoNotPresent(text);
});
