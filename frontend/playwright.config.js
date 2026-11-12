import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4186',
    channel: 'chrome',
    launchOptions: { args: ['--no-proxy-server'] },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run preview -- --port 4186 --strictPort',
    url: 'http://127.0.0.1:4186',
    reuseExistingServer: false,
  },
});
