// PVORD (fondateur 19/08/2026) — ordre des lignes de devis.
// `createAutoQuote` (autoQuote.js) créait ses lignes via
// `Promise.all(rows.map(r => dispatch(addLigneDevis({...}))))` — des POSTs
// CONCURRENTS sans `ordre` explicite. `LigneDevis.ordre` défaut 0 pour
// TOUTES les lignes ⇒ le tri serveur (`Meta.ordering = ['ordre', 'id']`)
// retombait sur `id` = ordre d'ARRIVÉE réseau (une course), jamais l'ordre
// canonique du simulateur produit par `autoFillLines`/`autoFillPompage`.
//
// Correctif : chaque ligne porte désormais `ordre: idx`, l'index dans le
// tableau `rows` FILTRÉ (composition order), calculé de façon synchrone
// avant tout dispatch — déterministe malgré la concurrence des requêtes.
//
// autoQuote.js ne peut pas être importé tel quel par `node --test` (import
// relatif vers ./store/ventesSlice, dépendance à un `dispatch` Redux réel —
// voir autoQuote.paliers.test.mjs) : ce test lit donc le SOURCE, même
// patron que LeadDevisPanel.wiring.test.mjs.
//
// Run : node --test src/features/ventes/autoQuote.ordre.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')

// Ne garde que le CODE : un commentaire peut légitimement mentionner
// l'ancien patron sans que ce soit une régression.
const CODE = SRC
  .split('\n')
  .filter((ligne) => !ligne.trim().startsWith('//'))
  .join('\n')

test('createAutoQuote : le mapping de création de lignes reçoit idx (r, idx)', () => {
  assert.match(CODE, /\.map\(\(r,\s*idx\)\s*=>\s*dispatch\(addLigneDevis\(/)
})

test('createAutoQuote : le payload addLigneDevis porte "ordre: idx"', () => {
  assert.match(CODE, /ordre:\s*idx,?/)
})

test('createAutoQuote : ordre est DANS le même objet addLigneDevis que produit/quantite (même bloc de lignes)', () => {
  const m = CODE.match(/dispatch\(addLigneDevis\(\{[\s\S]*?\}\)\)\.unwrap\(\)\)\)/)
  assert.ok(m, 'bloc addLigneDevis introuvable')
  const bloc = m[0]
  assert.match(bloc, /produit:\s*parseInt\(r\.produit\)/)
  assert.match(bloc, /quantite:\s*String\(r\.quantite\)/)
  assert.match(bloc, /ordre:\s*idx/)
})

test('createAutoQuote : la concurrence Promise.all est conservée (pas de sérialisation régressive)', () => {
  assert.match(CODE, /await Promise\.all\(rows/)
})
