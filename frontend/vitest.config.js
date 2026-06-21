import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/* Couche « tests de composants / UX » (RTL + axe), distincte des tests de logique
   pure exécutés par `node --test` (fichiers *.test.mjs). On limite donc Vitest aux
   fichiers *.test.jsx pour éviter tout double-passage avec node:test. */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.test.jsx'],
    setupFiles: ['./src/test/setup.js'],
    css: false,
    coverage: {
      // `npm run test:coverage` → un % visible des composants/UX couverts.
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/**/*.test.{js,jsx}', 'src/test/**', 'src/**/*.test.mjs'],
    },
  },
})
