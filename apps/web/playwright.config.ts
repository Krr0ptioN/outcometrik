import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000' },
  webServer: {
    command: 'pnpm exec next start',
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
});
