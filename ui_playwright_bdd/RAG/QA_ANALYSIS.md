# QA Analysis and RAG Knowledge Base for ui_playwright_bdd

## Application under test
- `https://qacart-todo.herokuapp.com`

## Framework summary
- Playwright + Cucumber BDD in `ui_playwright_bdd`
- TypeScript test steps via `ts-node/register`
- Allure reporting configured via npm scripts
- Shared test user persisted in `src/fixtures/user.json`

## Goal for this RAG integration
- Capture QA analysis, user stories, acceptance criteria, and missing coverage in a central RAG-friendly document
- Link the knowledge directly to implemented feature files and page object patterns
- Make the framework self-healing by generating stable fixture users when stale

## Current implemented coverage
- Signup success flow: `src/features/Id01_SignupTest.feature`
- Login success flow: `src/features/Id02_LoginTest.feature`
- Todo creation flow: `src/features/Id03_TodoTest.feature`
- Todo deletion flow: `src/features/Id04_DeleteTodoTest.feature`

## Known stability improvement
- Fixture users may become stale if the application database resets.
- The login fixture step now attempts to reuse the saved user and will create a fresh signup fixture when the saved user is invalid.

## User stories

### User story 1: Signup
- As a new visitor
- I want to create an account
- So that I can manage my todo list

#### Acceptance criteria (passing)
- Signup page is accessible.
- User can fill first name, last name, email, password and confirm password.
- Valid credentials are accepted.
- User is redirected to the todo/dashboard page after signup.
- Created user is saved for later login and todo scenarios.

#### Failing test cases (negative acceptance criteria)
- Signup with invalid email format should display validation error.
- Signup with mismatched passwords should display password mismatch error.
- Signup with missing required fields should display field validation errors.
- Signup with weak password should display password strength error.
- Signup with existing email should display email already registered error.
- Signup with only whitespace in first/last name should be rejected.
- Signup should enforce minimum password length requirements.

### User story 2: Login
- As a returning user
- I want to login with my email and password
- So that I can access my todo list

#### Acceptance criteria (passing)
- Login page is accessible.
- User can enter valid email and password.
- User is redirected to the todo/dashboard page after login.
- Invalid credentials produce a visible error.
- Login reuses the stored fixture user if valid.

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
- As a logged-in user
- I want to add a new todo item
- So that I can track tasks I need to complete

#### Acceptance criteria (passing)
- Todo input is visible after login.
- User can type a todo description and add it.
- The new todo appears in the list.
- Empty todos are not accepted.

#### Failing test cases (negative acceptance criteria)
- Adding empty todo should display validation error or be prevented.
- Adding todo with only whitespace should display validation error.
- Adding todo exceeding maximum character limit should display length error.
- Adding duplicate todo text should either allow or display duplicate warning.
- Adding todo after logo (passing)
- User can delete a specific todo item.
- The deleted item disappears from the list.

#### Failing test cases (negative acceptance criteria)
- Deleting non-existent todo should display error or be prevented.
- Deleting already deleted todo should fail with not found error.
- Attempting to delete without proper authorization should fail.
- Deleting todo and refreshing page should confirm deletion persisted.
- Deleting after logout should redirect to login page.
- Bulk delete without confirmation should display confirmation dialognfinished input should show error.

### User story 4: Todo deletion
- As a logged-in user
- I want to remove a todo item
- So that I can keep my list clean

#### Acceptance criteria
- User can delete a specific todo item.
- The deleted item disappears from the list.

## Implemented negative test coverage
- Negative login: `src/features/Id05_LoginNegativeTest.feature` - invalid email/password scenarios

## Missing negative test coverage (TODO)
- Signup validation: missing fields, mismatched passwords, invalid email format, weak password
- Todo validation: empty submission, whitespace-only, length limits, duplicate detection
- Todo lifecycle: completion state, persistence after refresh, concurrent operations
- Security: password rules enforcement, session expiration, brute force protection, XSS prevention
- Edge cases: network failures, timeouts, concurrent requests, data persistence

## Automation plan
- Keep the RAG document updated alongside feature files.
- Add new BDD scenarios for negative login and todo validation.
- Keep page object selectors aligned with actual app HTML.
- Use fixture user recovery logic to reduce test flakiness.

## Quick reference
- Fixture storage: `src/fixtures/user.json`
- Login step definition: `src/steps/Id02_LoginTest.ts`
- Signup step definition: `src/steps/Id01_SignupTest.ts`
- Todo page object: `src/pages/TodoPage.ts`
- Allure report: `allure-report`
