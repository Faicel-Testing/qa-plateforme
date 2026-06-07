import path from 'path';
import dotenv from 'dotenv';

const envName = process.env.ENV || 'local';
const envFile = path.resolve(process.cwd(), `.env.${envName}`);

dotenv.config({ path: envFile });

export const envConfig = {
  env: process.env.ENV || 'local',
  baseUrl: process.env.BASE_URL || 'http://localhost:3000',
  apiUrl: process.env.API_URL || '',
  headless: (process.env.TEST_HEADLESS || 'true').toLowerCase() === 'true',
  browser: (process.env.TEST_BROWSER || 'chromium').toLowerCase()
};