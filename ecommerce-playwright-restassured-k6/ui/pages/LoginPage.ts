import { Page } from 'playwright';
import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  private readonly selectors = {
    loginEmail:        'input[data-qa="login-email"]',
    loginPassword:     'input[data-qa="login-password"]',
    loginButton:       'button[data-qa="login-button"]',
    signupName:        'input[data-qa="signup-name"]',
    signupEmail:       'input[data-qa="signup-email"]',
    signupButton:      'button[data-qa="signup-button"]',
    loginError:        'p:has-text("Your email or password is incorrect")',
    signupError:       'p:has-text("Email Address already exist")',
    loggedUsername:    'a:has-text("Logged in as")',
  };

  async goto(): Promise<void> {
    await this.navigate('/login');
  }

  async login(email: string, password: string): Promise<void> {
    await this.page.fill(this.selectors.loginEmail, email);
    await this.page.fill(this.selectors.loginPassword, password);
    await this.page.click(this.selectors.loginButton);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async signup(name: string, email: string): Promise<void> {
    await this.page.fill(this.selectors.signupName, name);
    await this.page.fill(this.selectors.signupEmail, email);
    await this.page.click(this.selectors.signupButton);
    await this.page.waitForLoadState('domcontentloaded');
  }

  async isLoginErrorVisible(): Promise<boolean> {
    return this.page.locator(this.selectors.loginError).isVisible();
  }

  async isSignupErrorVisible(): Promise<boolean> {
    return this.page.locator(this.selectors.signupError).isVisible();
  }

  async isLoggedIn(): Promise<boolean> {
    return this.page.locator(this.selectors.loggedUsername).isVisible();
  }
}
