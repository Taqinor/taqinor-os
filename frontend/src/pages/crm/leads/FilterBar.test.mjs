// LB23 — recherche débouncée (blueprint D5/I7) : l'input de recherche garde
// un état local et pousse `setFilters` seulement après 250ms de pause,
// annulé au démontage/à la frappe suivante ; se resynchronise IMMÉDIATEMENT
// quand `filters.q` change depuis l'extérieur (Effacer les filtres, vue
// enregistrée, URL collée). Verified against SOURCE (no node_modules in
// this worktree/lane).
//   node --test src/pages/crm/leads/FilterBar.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FilterBar.jsx'), 'utf8')

test('LB23 : état local searchLocal initialisé depuis filters.q', () => {
  assert.match(SRC, /const \[searchLocal, setSearchLocal\] = useState\(filters\.q\)/)
})

test('LB23 : resynchronisation immédiate quand filters.q change depuis l’extérieur', () => {
  // Motif « adjust state during render » (lint v7 interdit le setState
  // synchrone en effet) : resync pendant le rendu, gardée par prevQ.
  const idx = SRC.indexOf('setSearchLocal(filters.q)')
  assert.ok(idx > 0, 'resynchronisation introuvable')
  const block = SRC.slice(Math.max(0, idx - 160), idx + 80)
  assert.match(block, /if \(prevQ !== filters\.q\) \{/)
  assert.match(block, /setPrevQ\(filters\.q\)/)
})

test('LB23 : le push vers setFilters est débouncé 250ms et annulé au démontage/frappe suivante', () => {
  const start = SRC.indexOf('if (searchLocal === filters.q) return undefined')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 350)
  assert.match(block, /setTimeout\(\(\) => setFilters\(\(f\) => \(\{ \.\.\.f, q: searchLocal \}\)\), 250\)/)
  assert.match(block, /return \(\) => clearTimeout\(t\)/)
  assert.match(block, /\}, \[searchLocal\]\)/)
})

test('LB23 : le champ de recherche est contrôlé par searchLocal (jamais filters.q directement)', () => {
  const start = SRC.indexOf('placeholder="Rechercher nom, téléphone, email…"')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 200)
  assert.match(block, /value=\{searchLocal\}/)
  assert.match(block, /onChange=\{\(e\) => setSearchLocal\(e\.target\.value\)\}/)
  assert.doesNotMatch(block, /value=\{filters\.q\}/)
})

// ── LB36 — « Effacer les filtres » pendant le débounce ne ressuscite plus la
// recherche tapée. Le scénario du bug : un AUTRE filtre est posé, on tape
// « xyz », on efface sous 250 ms — `filters.q` n'a JAMAIS changé (il était
// déjà vide), donc le resync gardé par `prevQ` ne se déclenche pas et le
// timer en vol ré-applique « xyz » APRÈS l'effacement.
//
// Le contrat est verrouillé sur la SOURCE (le suite frontend de la CI est
// `node --test "src/**/*.test.mjs"` — aucun rendu React/RTL disponible ici,
// même convention que tout ce fichier depuis LB23). Ce qui est vérifié : la
// détection de réinitialisation existe, elle ramène `searchLocal` (ce qui,
// `searchLocal` étant l'unique dépendance de l'effet, déclenche son
// `clearTimeout` et annule le timer), elle est faite PENDANT LE RENDU, et
// elle est assez étroite pour ne pas effacer une frappe en cours.

test('LB36 : une réinitialisation complète des filtres ramène le texte local (donc annule le timer en vol)', () => {
  const idx = SRC.indexOf('const [prevFilters, setPrevFilters] = useState(filters)')
  assert.ok(idx > 0, 'détection de réinitialisation introuvable')
  const end = SRC.indexOf('useEffect(', idx)
  assert.ok(end > idx, 'effet de débounce introuvable après la détection')
  const block = SRC.slice(idx, end)
  // Motif « adjust state during render » (jamais un setState-in-effect) : la
  // détection vit ENTIÈREMENT avant le premier useEffect du composant.
  assert.match(block, /if \(prevFilters !== filters\) \{/)
  assert.match(block, /setPrevFilters\(filters\)/)
  assert.match(block, /if \(isAllCleared\(filters\) && searchLocal !== filters\.q\) setSearchLocal\(filters\.q\)/)
  assert.doesNotMatch(block, /useEffect/)
})

test('LB36 : l’annulation passe par le cleanup de l’effet existant — `searchLocal` reste son unique dépendance', () => {
  const start = SRC.indexOf('if (searchLocal === filters.q) return undefined')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 350)
  // Le resync pose searchLocal === filters.q → l'effet re-tourne, son cleanup
  // clearTimeout le timer en vol, et il ressort AVANT d'en reprogrammer un.
  assert.match(block, /return \(\) => clearTimeout\(t\)/)
  assert.match(block, /\}, \[searchLocal\]\)/)
})

test('LB36 : la détection est étroite — « tout est vide » a UNE seule définition, partagée avec isDirty', () => {
  assert.match(
    SRC,
    /const isAllCleared = \(f\) => Object\.keys\(EMPTY_FILTERS\)\.every\(\(k\) => f\[k\] === EMPTY_FILTERS\[k\]\)/,
  )
  // isDirty est désormais la NÉGATION du même prédicat (jamais deux règles).
  assert.match(SRC, /const isDirty = !isAllCleared\(filters\)/)
  // Le resync n'est PAS déclenché par un changement quelconque de `filters`
  // (sinon changer une étape pendant la frappe effacerait le texte tapé).
  assert.doesNotMatch(SRC, /if \(prevFilters !== filters\) \{\s*\n\s*setPrevFilters\(filters\)\s*\n\s*setSearchLocal\(filters\.q\)/)
})

test('LB36 : « Effacer les filtres » de la barre vide aussi le texte local (cas où React court-circuite setFilters)', () => {
  assert.match(SRC, /const clearAll = \(\) => \{\s*\n\s*setSearchLocal\(EMPTY_FILTERS\.q\)\s*\n\s*setFilters\(EMPTY_FILTERS\)\s*\n\s*\}/)
  assert.match(SRC, /onClick=\{clearAll\}/)
  // Plus aucun effacement qui oublierait le texte local dans cette barre.
  assert.doesNotMatch(SRC, /onClick=\{\(\) => setFilters\(EMPTY_FILTERS\)\}/)
})
