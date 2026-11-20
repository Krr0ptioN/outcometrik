import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: {
    jsx: 'automatic',
  },
  resolve: {
    alias: {
      '@outcometrik/api': fileURLToPath(
        new URL('../../api/src/index.ts', import.meta.url),
      ),
      '@outcometrik/ui': fileURLToPath(
        new URL('../../core/src/index.ts', import.meta.url),
      ),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
    reporters: process.env.CI ? ['default', 'junit'] : ['default'],
    outputFile: process.env.CI ? { junit: 'reports/junit.xml' } : undefined,
  },
});
