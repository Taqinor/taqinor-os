// ADEV70 — les listes consommées par les écrans facture/avoirs/paiements lisent TOUTES
// les pages (forme DRF `core/pagination.py`), jamais `r.data.results ?? r.data` (50 max).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { fetchAllPages } from '../../../utils/fetchAllPages.js'

const ICI = dirname(fileURLToPath(import.meta.url))
const lire = (f) => readFileSync(join(ICI, '..', f), 'utf8')

const drf = (total, taille) => (page) => {
  const debut = (page - 1) * taille
  const results = Array.from({ length: Math.max(0, Math.min(taille, total - debut)) }, (_, i) => ({ id: debut + i + 1 }))
  return Promise.resolve({ count: total, next: debut + taille < total ? 'x' : null, results })
}

test('57 éléments en deux pages de 50 : fetchAllPages les rend tous', async () => {
  const tout = await fetchAllPages(drf(57, 50))
  assert.equal(tout.length, 57)
})

const CAS = [
  ['FactureList.jsx', /fetchAllPages\([^\n]*getDevis\(\{ statut: 'accepte'/],
  ['FactureForm.jsx', /fetchAllPages\([^\n]*getBonsCommande\(/],
  ['AvoirsPage.jsx', /fetchAllPages\([^\n]*getAvoirs\(/],
  ['PaiementsPage.jsx', /fetchAllPages\([^\n]*getPaiements\(/],
]
for (const [fichier, motif] of CAS) {
  test(`${fichier} lit toutes les pages`, () => {
    const src = lire(fichier)
    assert.match(src, /import fetchAllPages from '..\/..\/utils\/fetchAllPages'/)
    assert.match(src, motif)
    assert.doesNotMatch(src, /r\.data\.results \?\? r\.data/)
    assert.doesNotMatch(src, /setConsoliderDevis\(res\.data\.results/)
  })
}
