const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { Writable } = require('node:stream');
const { test } = require('node:test');
const ts = require('typescript');

const root = path.resolve(__dirname, '../..');

// Execute the real step callbacks with controlled UI outcomes, without a browser.
function loadSource(relativePath, dependencies) {
  const filename = path.join(root, relativePath);
  const { outputText } = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    fileName: filename,
  });
  const module = { exports: {} };
  vm.runInNewContext(outputText, {
    module,
    exports: module.exports,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected dependency: ${name}`);
      return dependencies[name];
    },
  }, { filename });
  return module.exports;
}

function matches(text, expected) {
  return typeof expected === 'string' ? text.includes(expected) : expected.test(text);
}

function locator(read) {
  return {
    first: () => locator(() => read().slice(0, 1)),
    or: other => locator(() => [...read(), ...other.read()]),
    filter: ({ hasText }) => locator(() => read().filter(text => matches(text, hasText))),
    count: async () => read().length,
    waitFor: async () => assert.ok(read().length > 0, 'Expected a visible element'),
    read,
  };
}

const expect = actual => ({
  toBeVisible: async () => assert.ok(await actual.count() > 0, 'Expected a visible element'),
  toHaveCount: async expected => assert.equal(await actual.count(), expected, 'Unexpected todo count'),
});

function createScenario(relativePath, options = {}) {
  const state = { items: [], errors: [], muiErrors: [], acceptAdd: false, opens: 0, deletes: 0, ...options };
  const page = {
    getByText: expected => locator(() => state.errors.filter(text => matches(text, expected))),
    locator: () => locator(() => state.muiErrors),
  };
  const todo = {
    todoItems: locator(() => state.items),
    noTodosMessage: locator(() => state.items.length ? [] : ['No todos']),
    open: async () => { state.opens += 1; },
    attemptAddTodo: async text => { if (state.acceptAdd) state.items.push(text); },
    tryDeleteTodo: async text => {
      state.deletes += 1;
      const index = state.items.indexOf(text);
      if (index < 0) return false;
      state.items.splice(index, 1);
      return true;
    },
    assertTodoValidationError: async expected => expect(page.getByText(expected)).toBeVisible(),
    assertDeleteError: async () => expect(page.getByText(/not found|unable|cannot delete|error|already deleted/i)).toBeVisible(),
    assertTodoNotPresent: async text => expect(locator(() => state.items.filter(item => item === text))).toHaveCount(0),
  };
  const steps = new Map();
  const register = (name, callback) => {
    assert.ok(!steps.has(name), `Duplicate step: ${name}`);
    steps.set(name, callback);
  };
  const exported = loadSource(relativePath, {
    '@cucumber/cucumber': { When: register, Then: register },
    '@playwright/test': { expect },
    '../pages/Id03_TodoPage': { TodoPage: class { constructor() { return todo; } } },
  });
  const world = { page };
  return { state, world, exported, run: name => {
    assert.ok(steps.has(name), `Missing step: ${name}`);
    return steps.get(name).call(world);
  } };
}

const addSteps = 'src/steps/Id03_TodoNegativeTest.ts';
const deleteSteps = 'src/steps/Id04_DeleteTodoNegativeTest.ts';
const addVerdict = 'I should see a validation error or the todo should not be added';
const deleteVerdict = 'I should see an error or the deletion should be prevented';

for (const action of ['I try to add an empty todo item', 'I try to add a todo with only whitespace']) {
  test(`${action}: accepting invalid input must fail the scenario`, async () => {
    const scenario = createScenario(addSteps, { acceptAdd: true });
    await scenario.run(action);
    await assert.rejects(scenario.run(addVerdict), /Unexpected todo count/);
    assert.equal(scenario.state.opens, 1);
  });

  test(`${action}: silent rejection preserves existing todos`, async () => {
    const scenario = createScenario(addSteps, { items: ['Existing task'] });
    await scenario.run(action);
    await scenario.run(addVerdict);
    assert.deepEqual(scenario.state.items, ['Existing task']);
    assert.equal(scenario.state.opens, 1);
  });
}

test('visible validation errors satisfy the error-or-no-add scenario', async () => {
  const scenario = createScenario(addSteps);
  await scenario.run('I try to add an empty todo item');
  scenario.state.errors.push('Todo is required');
  await scenario.run(addVerdict);
  assert.equal(scenario.state.opens, 0);
});

test('missing creation context cannot produce a passing verdict', async () => {
  await assert.rejects(createScenario(addSteps).run(addVerdict), /No todo creation attempt/);
});

test('a long todo accepted without a length error must fail the scenario', async () => {
  const scenario = createScenario(addSteps, { acceptAdd: true });
  await scenario.run('I try to add a todo exceeding the character limit');
  assert.equal(scenario.state.items[0].length, 201); // Documented boundary: maximum 200 + 1.
  await assert.rejects(scenario.run('I should see a length validation error'), /Expected a visible element/);
});

test('a visible length error satisfies the length scenario', async () => {
  const scenario = createScenario(addSteps, { errors: ['Maximum length exceeded'] });
  await scenario.run('I should see a length validation error');
});

test('an absent todo is checked without repeating the deletion action', async () => {
  const scenario = createScenario(deleteSteps);
  await scenario.run('I try to delete a non-existent todo item');
  await scenario.run(deleteVerdict);
  assert.equal(scenario.state.deletes, 1);
});

for (const verdict of [deleteVerdict, 'I should see an error or the deletion should fail']) {
  test(`${verdict}: an unexpected successful deletion must fail`, async () => {
    const scenario = createScenario(deleteSteps, { items: ['Previously deleted task'] });
    scenario.world.lastTodo = 'Previously deleted task';
    await scenario.run('I try to delete the same todo item again');
    await assert.rejects(scenario.run(verdict), /Expected a visible element/);
    assert.equal(scenario.state.deletes, 1);
  });
}

test('a repeated deletion of an absent task passes', async () => {
  const scenario = createScenario(deleteSteps);
  scenario.world.lastTodo = 'Previously deleted task';
  await scenario.run('I try to delete the same todo item again');
  await scenario.run('I should see an error or the deletion should fail');
  assert.equal(scenario.state.deletes, 1);
});

test('missing deletion context cannot produce a passing verdict or a fabricated task', async () => {
  const scenario = createScenario(deleteSteps);
  await assert.rejects(scenario.run(deleteVerdict), /No todo deletion attempt/);
  await assert.rejects(scenario.run('I try to delete the same todo item again'), /No previously deleted todo/);
  assert.equal(scenario.state.deletes, 0);
});

test('an unrelated MUI error cannot satisfy a specific expected error', async () => {
  const { exported, world } = createScenario('src/pages/BasePage.ts', { muiErrors: ['Invalid email'] });
  const page = new exported.BasePage(world.page);
  await assert.rejects(page.assertErrorMessage(/password/i), /Expected a visible element/);
});

test('the expected MUI error is found even among multiple errors', async () => {
  const { exported, world } = createScenario('src/pages/BasePage.ts', {
    muiErrors: ['Invalid email', 'Password is required'],
  });
  const page = new exported.BasePage(world.page);
  await page.assertErrorMessage(/password/i);
  await page.assertErrorMessage('Password is required');
  await page.assertErrorMessage();
});

test('non-MUI error messages remain supported', async () => {
  const { exported, world } = createScenario('src/pages/BasePage.ts', { errors: ['Invalid password'] });
  await new exported.BasePage(world.page).assertErrorMessage(/password/i);
});

test('all Gherkin scenarios resolve without undefined or ambiguous steps', async t => {
  const { loadConfiguration, runCucumber } = require('@cucumber/cucumber/api');
  let output = '';
  const stdout = new Writable({ write(chunk, encoding, done) { output += chunk.toString(); done(); } });
  const environment = { cwd: root, stdout };
  const { runConfiguration } = await loadConfiguration({}, environment);
  runConfiguration.runtime.dryRun = true;
  // Do not overwrite real Allure results with a dry run.
  runConfiguration.formats = { stdout: 'summary', files: {}, publish: false, options: {} };
  let scenarios = 0;
  const result = await runCucumber(runConfiguration, environment, message => {
    if (message.pickle) scenarios += 1;
  });
  assert.ok(scenarios > 0, 'No Gherkin scenarios were loaded');
  assert.equal(result.success, true, output);
  t.diagnostic(output.trim());
});
