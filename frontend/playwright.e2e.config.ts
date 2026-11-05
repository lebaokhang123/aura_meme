import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: ['**/auth-real.spec.ts', '**/blog-real.spec.ts'],
  fullyParallel: false,
  workers: 1,
  webServer: {
    command: 'npm run dev -- --mode e2e --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
  },
});
