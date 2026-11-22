import base from '../playwright.config.js'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const here = path.dirname(fileURLToPath(import.meta.url))
export default { ...base, testDir: here, outputDir: path.join(here, '..', 'test-results'),
  use: { ...base.use, navigationTimeout: 180_000, actionTimeout: 90_000 },
  expect: { timeout: 90_000 }, timeout: 600_000, reporter: [['list']] }
