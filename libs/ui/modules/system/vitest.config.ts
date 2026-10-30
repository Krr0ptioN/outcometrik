import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@outcometrik/api': fileURLToPath(
        new URL('../../api/src/index.ts', import.meta.url),
      ),
    },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
