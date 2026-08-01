// APX20 — La promesse de la fiche produit est tenue : `marque` et `garantie`
// (TEXTE) deviennent saisissables depuis Stock.
//
// Contexte vérifié : la création rapide promet « vous pourrez compléter la
// fiche complète (catégorie, marque, garantie…) plus tard depuis Stock »
// (`components/ProduitQuickCreateModal.jsx`) — or ProduitForm n'exposait NI
// `marque` NI le `garantie` TEXTE (distinct des durées `garantie_mois` /
// `garantie_production_mois`, seules exposées). Ces deux champs alimentent
// pourtant les fiches produits des PDF de devis : on les remplissait par
// l'admin Django ou pas du tout.
//
// Vérifié SUR LA SOURCE (ce lane n'a pas de node_modules ; ce test tourne
// aussi en CI, qui découvre tout `src/**/*.test.mjs` par glob).
//   node --test src/pages/stock/ProduitFormApx20FicheProduit.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const FORM = read('ProduitForm.jsx')
const QUICK = read('../../components/ProduitQuickCreateModal.jsx')
const SERIALIZERS = read(
  '../../../../backend/django_core/apps/stock/serializers.py')

test('la promesse existe toujours dans la création rapide', () => {
  // Si cette phrase disparaît un jour, la tâche perd sa raison d'être — mais
  // les deux champs, eux, restent légitimes.
  assert.match(QUICK, /marque, garantie/)
})

test('`marque` et `garantie` sont dans l\'état initial du formulaire', () => {
  assert.match(FORM, /marque:\s+produit\?\.marque\s+\?\? ''/)
  assert.match(FORM, /garantie:\s+produit\?\.garantie\s+\?\? ''/)
})

test('les deux champs partent dans le payload, vidés → null', () => {
  assert.match(FORM, /marque:\s+fields\.marque\.trim\(\) \|\| null/)
  assert.match(FORM, /garantie:\s+fields\.garantie\.trim\(\) \|\| null/)
})

test('les deux champs sont RENDUS et éditables', () => {
  assert.match(FORM, /id="pf-marque"/)
  assert.match(FORM, /setField\('marque', e\.target\.value\)/)
  assert.match(FORM, /id="pf-gar-txt"/)
  assert.match(FORM, /setField\('garantie', e\.target\.value\)/)
})

test('le texte de garantie reste DISTINCT des durées en mois', () => {
  // Les trois champs coexistent : `garantie` (texte, part sur le devis),
  // `garantie_mois` et `garantie_production_mois` (horloges du parc).
  assert.match(FORM, /id="pf-gar"/)
  assert.match(FORM, /id="pf-garprod"/)
  assert.ok(FORM.indexOf('id="pf-gar-txt"') !== FORM.indexOf('id="pf-gar"'))
})

test('le backend acceptait déjà les deux champs (aucune migration requise)', () => {
  const bloc = SERIALIZERS.slice(SERIALIZERS.indexOf('fields = ['))
  assert.match(bloc, /'marque'/)
  assert.match(bloc, /'garantie'/)
})

test('la saisie reste libre : ni min/step qui snappe, ni rejet (invariant devis)', () => {
  // Les deux champs APX20 sont textuels — ils ne doivent surtout pas hériter
  // d'un `type="number"`, qui ré-introduirait le snapping que le générateur
  // de devis interdit.
  const marque = FORM.slice(FORM.indexOf('id="pf-marque"'))
    .slice(0, 200)
  assert.ok(!/type="number"/.test(marque))
  const garantie = FORM.slice(FORM.indexOf('id="pf-gar-txt"')).slice(0, 200)
  assert.ok(!/type="number"/.test(garantie))
})
