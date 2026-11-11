import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000' },
  webServer: [
    {
      command: 'uv run --project ../api python ../../tools/auth-e2e-server.py',
      url: 'http://127.0.0.1:8000/api/health/status',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: '../../node_modules/.bin/next start',
      port: 3000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
