# QA Analysis for ui_playwright_bdd

## Application URL
- `https://qacart-todo.herokuapp.com`

## Current framework summary
- Framework: Playwright + Cucumber BDD in `ui_playwright_bdd`
- Test engine: `ts-node/register` via `cucumber-js`
- Current feature coverage:
  - `src/features/Id01_SignupTest.feature` → Signup successful flow
  - `src/features/Id02_LoginTest.feature` → Login successful flow
- Existing page objects:
  - `src/pages/SignupPage.ts`
  - `src/pages/LoginPage.ts`
- Missing page object:
  - `src/pages/TodoPage.ts` (Todo CRUD operations)
- Execution & reporting:
  - Allure report generation in `allure-report`
  - Trend and KPI scripts under `scripts`
- Configured base URL and environment:
  - `BASE_URL=https://qacart-todo.herokuapp.com`
  - `HEADLESS=false`
  - `BROWSER=chromium`

## What is covered today
- New user signup success
- Returning user login success

## Gaps and missing coverage

### Implemented negative test coverage
- Negative login: `src/features/Id05_LoginNegativeTest.feature` - invalid email/password scenarios
- Todo CRUD operations: All main flows implemented (add, delete)

### Missing negative test coverage (TODO)
- Signup validation: missing fields, mismatched passwords, invalid email format, weak password
- Todo validation: empty submission, whitespace-only, length limits, duplicate detection
- Todo lifecycle: completion state, persistence after refresh, concurrent operations
- Security: password rules enforcement, session expiration, brute force protection, XSS prevention
- Edge cases: network failures, timeouts, concurrent requests, data persistence

## Proposed user stories

### User story 1: Signup
- As a new visitor,
- I want to create an account,
- So that I can manage my todo list.

#### Acceptance criteria (passing)
- The signup page is accessible.
- The user can fill first name, last name, email, password and confirm password.
- The application accepts valid credentials.
- After signup, the user is redirected to the todo or dashboard page.
- The created user can be reused for login tests.

#### Failing test cases (negative acceptance criteria)
- Signup with invalid email format should display validation error.
- Signup with mismatched passwords should display password mismatch error.
- Signup with missing required fields should display field validation errors.
- Signup with weak password should display password strength error.
- Signup with existing email should display email already registered error.
- Signup with only whitespace in first/last name should be rejected.
- Signup should enforce minimum password length requirements.

### User story 2: Login
- As a returning user,
- I want to login with my email and password,
- So that I can access my todo list.

#### Acceptance criteria (passing)
- The login page is accessible.
- The user can enter valid email and password.
- The user is redirected to the todo dashboard after login.
- Invalid credentials show an error message.

#### Failing test cases (negative acceptance criteria)
- Login with invalid email format should display validation error.
- Login with wrong password should display authentication error.
- Login with non-existent email should display user not found error.
- Login with empty email field should display required field error.
- Login with empty password field should display required field error.
- Login with both fields empty should display required field errors.
- Login with case-sensitive email mismatch should fail.
- Multiple failed login attempts should trigger rate limiting or lock account.

### User story 3: Todo creation
- As a logged-in user,
- I want to add a new todo item,
- So that I can track tasks I need to complete.

#### Acceptance criteria (passing)
- The todo input is visible after login.
- The user can type a todo description and add it.
- The new todo appears in the list.
- An empty todo cannot be added.

#### Failing test cases (negative acceptance criteria)
- Adding empty todo should display validation error or be prevented.
- Adding todo with only whitespace should display validation error.
- Adding todo exceeding maximum character limit should display length error.
- Adding duplicate todo text should either allow or display duplicate warning.
- Adding todo after logout should redirect to login page.
- Adding todo with special characters should be validated.
- Adding todo without completing previous unfinished input should show error.

### User story 4: Todo deletion
- As a logged-in user,
- I want to remove a todo item,
- So that I can keep my list clean.

#### Acceptance criteria (passing)
- The user can delete a specific todo item.
- The deleted item disappears from the list.

#### Failing test cases (negative acceptance criteria)
- Deleting non-existent todo should display error or be prevented.
- Deleting already deleted todo should fail with not found error.
- Attempting to delete without proper authorization should fail.
- Deleting todo and refreshing page should confirm deletion persisted.
- Deleting after logout should redirect to login page.
- Bulk delete without confirmation should display confirmation dialog.

## Documented test cases

### Passing scenarios (implemented)
- Sign up with valid credentials
- Login with valid credentials
- Add a todo item
- Delete a todo item

### Failing/Negative scenarios (documented but not yet implemented)
#### Signup validation
- Sign up with missing first name
- Sign up with missing last name
- Sign up with missing email
- Sign up with missing password
- Sign up with invalid email format
- Sign up with mismatched confirm password
- Sign up with weak password
- Sign up with existing email (duplicate)

#### Login validation
- Login with wrong email
- Login with wrong password
- Login with non-existent email
- Login with empty credentials
- Login with case-sensitive email mismatch
- Multiple failed login attempts

#### Todo operations
- Add a blank todo item
- Add todo with only whitespace
- Add todo exceeding character limit
- Delete non-existent todo item
- Delete already deleted todo item
- Verify todo persistence after reload

## Current automation updates
- Added fixture recovery logic for stale saved users.
- Added a negative login validation scenario for invalid credentials.
- Added a dedicated RAG QA analysis file in `RAG/QA_ANALYSIS.md`.

## Recommended next steps
1. Add `src/pages/TodoPage.ts` with common todo actions.
2. Add BDD scenarios for todo creation and deletion.
3. Add agent scaffolding scripts in `scripts/agents/`.
4. Add a RAG document store under `RAG/`.
5. Run the new BDD scenarios and publish the Allure report.
