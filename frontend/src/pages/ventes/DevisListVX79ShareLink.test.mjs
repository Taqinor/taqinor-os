// VX79 — Lien interne partageable pour les devis : bouton « Copier le lien »
// pointé vers l'URL INTERNE de l'ERP (/ventes/devis?devis=<pk>), distinct du
// lien PUBLIC de proposition (règle #4, intouché) ; un ?devis=<pk> introuvable
// affiche un EmptyState inline, jamais une page blanche.
// Vérifié contre la SOURCE (pas de node_modules dans ce worktree — même
// convention que DevisListDeepLinks.test.mjs).
//   node --test src/pages/ventes/DevisListVX79ShareLink.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('VX79 : un handler copie le lien INTERNE /ventes/devis?devis=<pk>', () => {
  assert.match(SRC, /const copierLienInterne = async \(d\) =>/)
  assert.match(SRC, /\/ventes\/devis\?devis=\$\{d\.id\}/)
  assert.match(SRC, /navigator\.clipboard\?\.writeText/)
})

test('VX79 : le lien interne est DISTINCT du lien public de proposition (règle #4)', () => {
  // handleCopierLienProposition (public, tokenisé) reste présent et intouché.
  assert.match(SRC, /const handleCopierLienProposition = async \(d\) =>/)
  // Le nouveau handler ne réutilise pas le token public : il pointe vers l'ERP.
  const start = SRC.indexOf('const copierLienInterne')
  // Corps du handler seulement (jusqu'à sa toast de succès) : ne doit pas
  // toucher au token/chemin public.
  const block = SRC.slice(start, SRC.indexOf('copié.', start))
  assert.doesNotMatch(block, /proposition\/|share_link|shareLinkDevis/)
})

test('VX79 : une action de ligne déclenche copierLienInterne', () => {
  // VX20 a replié « Lien interne » dans le menu « ⋯ » (DropdownMenuItem
  // `onSelect`) au lieu d'un bouton direct `onClick` — le handler est le même.
  assert.match(SRC, /onSelect=\{\(\) => copierLienInterne\(d\)\}/)
  // Le handler transite par le sac de contexte de la ligne (rowCtx + destructure).
  const occurrences = (SRC.match(/copierLienInterne/g) || []).length
  assert.ok(occurrences >= 4, `attendu >=4 occurrences, trouvé ${occurrences}`)
})

test('VX79 : ?devis=<pk> introuvable → EmptyState inline (pas de page blanche)', () => {
  assert.match(SRC, /const highlightMissing = !!highlightId && !loading/)
  assert.match(SRC, /!devis\.some\(d => d\.id === highlightId\)/)
  const block = SRC.slice(
    SRC.indexOf('{highlightMissing && ('),
    SRC.indexOf('{highlightMissing && (') + 400)
  assert.match(block, /<EmptyState/)
  assert.match(block, /Devis introuvable/)
})
