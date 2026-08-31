// QJR218 — L'écran renvoie `quantite_manuelle`, donc un verrou de quantité
// survit à l'enregistrement.
//
// `DevisGenerator.jsx` envoyait `prix_manuel` à l'enregistrement mais JAMAIS
// `quantite_manuelle`, et `replace-lignes` défaute le marqueur absent à
// `False` — une ligne verrouillée en quantité (posée côté serveur, ex. une
// resynchronisation) perdait son verrou au prochain enregistrement du
// vendeur, et `?edit=` ne le restaurait jamais (le backend, lui, round-trip
// déjà les deux marqueurs, `domain/lignes`).
//
// Répro du Done= : ligne `quantite_manuelle=True` -> enregistrement -> une
// relecture ultérieure la trouve `False` (AVANT le correctif).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE (même patron que les autres
// tests DevisGenerator* de ce dossier).
//
// Run : node --test src/pages/ventes/DevisGeneratorQuantiteManuelle.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR218 — round-trip ENREGISTREMENT : quantite_manuelle part avec la ligne, comme prix_manuel', () => {
  const idx = DG.indexOf('prix_manuel: !!l.prixManuel,')
  assert.ok(idx > -1, 'le champ prix_manuel du payload de sauvegarde est introuvable')
  const bloc = DG.slice(idx, idx + 600)
  assert.match(bloc, /quantite_manuelle: !!l\.quantiteManuelle,/,
    'AVANT QJR218 : quantite_manuelle n’était jamais envoyé au serveur — ' +
    'replace-lignes le défaute alors à False, le verrou de quantité posé ' +
    'côté serveur ne survit pas à l’enregistrement suivant du vendeur',
  )
})

test('QJR218 — round-trip ?edit= : quantite_manuelle est RELU depuis la colonne persistée, comme prix_manuel', () => {
  const idx = DG.indexOf('prixManuel: !!l.prix_manuel,')
  assert.ok(idx > -1, 'le mappeur de réouverture ?edit= (prixManuel) est introuvable')
  const bloc = DG.slice(idx, idx + 400)
  assert.match(bloc, /quantiteManuelle: !!l\.quantite_manuelle,/,
    'AVANT QJR218 : ?edit= ne relisait jamais quantite_manuelle — le verrou ' +
    'de quantité restait invisible à la réouverture, même si le serveur ' +
    'le portait toujours',
  )
})

test('QJR218 — withKeys() porte quantiteManuelle par défaut (même patron que prixManuel)', () => {
  const idx = DG.indexOf('const withKeys = (rows) => rows.map(r => ({')
  assert.ok(idx > -1)
  const fin = DG.indexOf('}))', idx)
  const bloc = DG.slice(idx, fin)
  assert.match(bloc, /prixManuel: !!r\.prixManuel,/)
  assert.match(bloc, /quantiteManuelle: !!r\.quantiteManuelle,/)
})

test('QJR218 — une ligne neuve (emptyLine) n’a AUCUN verrou de quantité par défaut', () => {
  const idx = DG.indexOf('const emptyLine = () => ({')
  assert.ok(idx > -1)
  const fin = DG.indexOf('})', idx)
  const bloc = DG.slice(idx, fin)
  assert.match(bloc, /prixManuel: false,/)
  assert.match(bloc, /quantiteManuelle: false,/)
})

test('QJR218 — le marqueur suit la MÊME convention de nommage que prixManuel (camelCase écran / snake_case API)', () => {
  // Écran : quantiteManuelle (camelCase, comme prixManuel). API : quantite_manuelle
  // (snake_case, comme prix_manuel) — jamais un troisième nom inventé.
  assert.doesNotMatch(DG, /quantiteManuel\b/, 'pas de troncature du nom du drapeau')
  assert.match(DG, /quantiteManuelle/)
  assert.match(DG, /quantite_manuelle/)
})
