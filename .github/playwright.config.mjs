import { fileURLToPath } from 'node:url';
import base from '../frontend/playwright.config.js';

export default {
  ...base,
  testDir: fileURLToPath(new URL('../frontend/tests', import.meta.url)),
  outputDir: fileURLToPath(new URL('../frontend/test-results', import.meta.url)),
  use: { ...base.use, channel: 'chromium' },
  webServer: { ...base.webServer, cwd: fileURLToPath(new URL('../frontend', import.meta.url)) },
};
