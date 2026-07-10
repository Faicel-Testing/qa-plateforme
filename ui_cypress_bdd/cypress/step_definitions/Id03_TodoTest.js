const { When, Then } = require('@badeball/cypress-cucumber-preprocessor');
const { TodoPage } = require('../support/pages/TodoPage');

When('I add a new todo item', function () {
  const ctx = this;
  const text = `Todo ${Date.now()}`;
  ctx.lastTodo = text;
  new TodoPage().addTodo(text);
});

Then('I should see the new todo item in the list', function () {
  const text = this.lastTodo;
  if (!text) {
    throw new Error('No todo text available in scenario context');
  }
  new TodoPage().assertTodoExists(text);
});
