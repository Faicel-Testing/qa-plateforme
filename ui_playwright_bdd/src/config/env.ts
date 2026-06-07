import 'dotenv/config';

export const env = {
  baseUrl: process.env.BASE_URL ?? 'https://qacart-todo.herokuapp.com',
  headless: (process.env.HEADLESS ?? 'true') === 'true',
  browser: process.env.BROWSER ?? 'chromium',
};