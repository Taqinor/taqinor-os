// QJR214 — Le client d'API expose enfin le registre de surcharges.
// `features/ventes/quote/overrides.js` était un module SANS AUCUN importeur
// et aucune méthode de `ventesApi.js` ne visait
// `/ventes/devis/<id>/overrides/` — l'endpoint GET/PATCH/DELETE
// (`views/devis.py:2582-2634`) n'avait donc littéralement pas de client.
//
// `ventesApi.js` importe `./axios`, qui a des effets de bord réseau/globaux
// au chargement du module : comme `ventesApi.xsal3.test.mjs` et
// `ventesApi.pdfTimeout.test.mjs` déjà au dépôt, ce test relit la SOURCE pour
// verrouiller URL/verbe/forme, et importe RÉELLEMENT `overrides.js` (module
// PUR, sans effet de bord) pour prouver — en EXÉCUTANT le code réel, pas une
// regex — que la validation des chemins est bien celle dérivée du contrat.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { cheminsRefuses } from '../features/ventes/quote/overrides.js'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'ventesApi.js'), 'utf8')
const CONTRAT = JSON.parse(readFileSync(join(
  here, '..', '..', '..', 'backend', 'django_core', 'apps', 'ventes',
  'contract_samples', 'devis_overrides.json'), 'utf8'))

// ── overrides.js est désormais IMPORTÉ par le client (fin du module orphelin) ─

test('overrides.js est IMPORTÉ par ventesApi.js (fin du module sans importeur)', () => {
  assert.match(src, /import \{ cheminsRefuses \} from '\.\.\/features\/ventes\/quote\/overrides'/)
})

// ── lireOverrides : GET ───────────────────────────────────────────────────────

test('lireOverrides -> GET /ventes/devis/<id>/overrides/', () => {
  assert.match(src, /lireOverrides: \(id\) => api\.get\(`\/ventes\/devis\/\$\{id\}\/overrides\/`\)/)
})

// ── poserOverrides : PATCH = FUSION ──────────────────────────────────────────

test('poserOverrides -> PATCH /ventes/devis/<id>/overrides/ avec le patch en corps', () => {
  assert.match(src, /poserOverrides: \(id, patch\) => \{/)
  assert.match(src, /api\.patch\(`\/ventes\/devis\/\$\{id\}\/overrides\/`, patch\)/)
})

test('poserOverrides EXÉCUTE réellement cheminsRefuses (module réel, pas une copie) avant tout PATCH', () => {
  // On exécute le VRAI cheminsRefuses (importé, pas recopié) : un chemin hors
  // liste blanche du contrat doit ressortir refusé.
  assert.deepEqual(cheminsRefuses({ total_ttc: { valeur: 42000 } }), ['total_ttc'])
  assert.deepEqual(cheminsRefuses({ 'taille.nb_panneaux': { valeur: 14 } }), [])
  // Câblage : poserOverrides doit bien appeler cheminsRefuses(patch) avant le réseau.
  assert.match(src, /const refuses = cheminsRefuses\(patch\)/)
  assert.match(src, /if \(refuses\.length\)/)
})

test('EXHAUSTIVITÉ : chaque chemin du contrat (JSON sur disque, jamais recopié) est accepté par poserOverrides', () => {
  // Dérivé du contrat, PAS écrit en dur ici — `profil.equipements.<clef>` est
  // le motif lui-même (jamais un chemin réel), explicitement exclu par
  // `cheminAutorise` (overrides.js) : on l'écarte pour tester les CHEMINS.
  const chemins = CONTRAT.notes.chemins_autorises.filter((c) => c !== 'profil.equipements.<clef>')
  assert.ok(chemins.length > 0, 'le contrat doit lister des chemins')
  for (const chemin of chemins) {
    assert.deepEqual(cheminsRefuses({ [chemin]: { valeur: 'x' } }), [],
      `le chemin du contrat "${chemin}" doit être accepté (jamais refusé client-side)`)
  }
})

// ── regenererOverride : DELETE ?chemin= ──────────────────────────────────────

test('regenererOverride -> DELETE /ventes/devis/<id>/overrides/?chemin=<chemin>', () => {
  assert.match(
    src,
    /regenererOverride: \(id, chemin\) =>\s*\n\s*api\.delete\(`\/ventes\/devis\/\$\{id\}\/overrides\/`, \{ params: \{ chemin \} \}\)/,
  )
})

// ── forme de réponse (overrides/effectif/lignes) : le CONTRAT fait foi ──────

test('la forme de réponse du contrat porte bien overrides/effectif/lignes (les trois clés que l’écran QJR215 consommera)', () => {
  for (const cle of ['overrides', 'effectif', 'lignes']) {
    assert.ok(cle in CONTRAT.exemple, `clé "${cle}" absente de l'exemple du contrat`)
    assert.ok(cle in CONTRAT.exemple_vide, `clé "${cle}" absente de l'exemple_vide du contrat`)
  }
  assert.equal(CONTRAT.endpoint, 'GET /api/django/ventes/devis/<int:pk>/overrides/')
})
