// QJR640 — ventesApi ne garde aucune méthode sans appelant (grep mot entier sur
// frontend/src et frontend/e2e : 0 référence, aucun accès dynamique).
// Run : node --test src/api/ventesApiNoDeadMethods.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ventesApi.js'), 'utf8')

const MORTES = [
  'updateListePrix', 'getLignesDevis', 'getBonCommande', 'getPaiementsFacture',
  'getEmailsFacture', 'getClientReleve', 'getLignesFacture',
]

for (const nom of MORTES) {
  test(`ventesApi ne définit plus ${nom}`, () => {
    assert.doesNotMatch(SRC, new RegExp(`^\\s*${nom}\\s*:`, 'm'))
  })
}

test('les voisins vivants restent définis', () => {
  for (const nom of ['patchListePrix', 'getBonsCommande', 'getBonCommandePdf',
    'getClientRelevePdf', 'createLigneDevis', 'createLigneFacture', 'getEmailConfig']) {
    assert.match(SRC, new RegExp(`^\\s*${nom}\\s*:`, 'm'), nom)
  }
})
