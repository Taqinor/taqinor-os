// APAR64 — garde de classe : `no-alert` est une ERREUR dans les dossiers
// Paramètres / Approbations (dialogues natifs interdits, critère C13).
// Utilise la configuration ESLint RÉELLE du dépôt (aucune règle recopiée).
import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const DOSSIERS = [
  'src/pages/parametres/__apar64_probe.jsx',
  'src/features/parametres/__apar64_probe.jsx',
  'src/pages/approbations/__apar64_probe.jsx',
]
const HORS_PERIMETRE = 'src/pages/crm/__apar64_probe.jsx'

async function noAlertErrors(relPath, code) {
  const eslint = new ESLint({ cwd: FRONTEND })
  const [res] = await eslint.lintText(code, { filePath: path.join(FRONTEND, relPath) })
  return res.messages.filter((m) => m.ruleId === 'no-alert' && m.severity === 2)
}

for (const dossier of DOSSIERS) {
  for (const call of ['window.confirm', 'window.alert', 'window.prompt', 'confirm', 'alert']) {
    test(`no-alert est une erreur : ${call}(…) dans ${dossier}`, async () => {
      const errs = await noAlertErrors(dossier, `export function f() { ${call}('x') }\n`)
      assert.equal(errs.length, 1)
    })
  }
}

test('le code sans dialogue natif ne lève aucune erreur no-alert', async () => {
  const errs = await noAlertErrors(DOSSIERS[0], 'export function f() { return 1 }\n')
  assert.equal(errs.length, 0)
})

test('la règle reste limitée au périmètre (pas d’extension à tout src)', async () => {
  const errs = await noAlertErrors(HORS_PERIMETRE, "export function f() { window.confirm('x') }\n")
  assert.equal(errs.length, 0)
})
