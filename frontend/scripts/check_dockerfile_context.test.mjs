// ERR-QJR5-DOCKERFILE-CONTEXTE-GARDE — prouve que la garde est ROUGE sans la
// ligne `COPY apps/web/worker` et VERTE avec (lancé par la CI : frontend-static).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { findUncovered } from './check_dockerfile_context.mjs'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const dockerfile = readFileSync(join(repoRoot, 'frontend', 'Dockerfile.prod'), 'utf8')

test('Dockerfile.prod actuel : tout import hors frontend/ est couvert', () => {
  assert.deepEqual(findUncovered({ repoRoot, dockerfileText: dockerfile }), [])
})

test('sans la ligne COPY apps/web/worker : la garde échoue sur worker/deadLetter.mjs', () => {
  const sans = dockerfile
    .split(/\r?\n/)
    .filter((l) => !/^\s*COPY\s+apps\/web\/worker\b/.test(l))
    .join('\n')
  assert.notEqual(sans, dockerfile, 'la ligne COPY apps/web/worker doit exister dans le Dockerfile')
  const missing = findUncovered({ repoRoot, dockerfileText: sans })
  assert.ok(missing.includes('apps/web/worker/deadLetter.mjs'), `obtenu : ${missing.join(', ')}`)
})

test('sans le COPY apps/web/src : la garde échoue aussi', () => {
  const sans = dockerfile
    .split(/\r?\n/)
    .filter((l) => !/^\s*COPY\s+apps\/web\/src\b/.test(l))
    .join('\n')
  assert.ok(findUncovered({ repoRoot, dockerfileText: sans }).length > 0)
})
