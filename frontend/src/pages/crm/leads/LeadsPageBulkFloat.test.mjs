// LB25 — Barre bulk FLOTTANTE (blueprint D5) : l'ancienne barre inline
// poussait le layout à chaque sélection (le board sautait de hauteur) ;
// MÊME composant BulkActionBar dans un nouveau wrapper `.lp-bulk-float`,
// Échap/« Effacer » la ferment tous les deux. Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageBulkFloat.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const CSS_SRC = readFileSync(join(HERE, '..', '..', '..', 'index.css'), 'utf8')

test('LB25 : BulkActionBar reste le MÊME composant, enveloppé dans .lp-bulk-float', () => {
  const idx = PAGE_SRC.indexOf('<div className="lp-bulk-float">')
  assert.ok(idx > 0, 'wrapper .lp-bulk-float introuvable')
  const block = PAGE_SRC.slice(idx, idx + 400)
  assert.match(block, /<BulkActionBar/)
  assert.match(block, /count=\{visibleSelected\.size\}/)
  assert.match(block, /onAction=\{runBulk\}/)
  assert.match(block, /onExport=\{exportSelection\}/)
  assert.match(block, /onClear=\{clearSelection\}/)
})

test('LB25 : clearSelection est stabilisée (useCallback) — référence stable pour Échap', () => {
  assert.match(PAGE_SRC, /const clearSelection = useCallback\(\(\) => setSelected\(new Set\(\)\), \[\]\)/)
})

test('LB25 : Échap ferme la barre bulk flottante (même geste que « Effacer »)', () => {
  const idx = PAGE_SRC.indexOf("if (visibleSelected.size === 0) return undefined")
  assert.ok(idx > 0)
  // Fenêtre élargie : la garde de la critique Fable #6 (commentaire + 2
  // early-returns) vit entre le test de touche et clearSelection().
  const block = PAGE_SRC.slice(idx, idx + 1000)
  assert.match(block, /e\.key !== 'Escape'\) return/)
  assert.match(block, /clearSelection\(\)/)
  assert.match(block, /window\.addEventListener\('keydown', onKeyDown\)/)
  assert.match(block, /window\.removeEventListener\('keydown', onKeyDown\)/)
})

test('LB25 (critique Fable #6) : Échap n\'efface JAMAIS la sélection à travers un overlay ouvert', () => {
  const idx = PAGE_SRC.indexOf("if (visibleSelected.size === 0) return undefined")
  const block = PAGE_SRC.slice(idx, idx + 1000)
  assert.match(block, /if \(e\.defaultPrevented\) return/)
  assert.match(block, /\[role="dialog"\]\[data-state="open"\]/)
  assert.match(block, /data-radix-popper-content-wrapper/)
})

test('LB25 : .lp-bulk-float est fixed, palier --z-sticky, safe-area, au-dessus de la tabbar mobile', () => {
  const idx = CSS_SRC.indexOf('.lp-bulk-float {')
  assert.ok(idx > 0)
  const block = CSS_SRC.slice(idx, idx + 400)
  assert.match(block, /position:\s*fixed/)
  assert.match(block, /z-index:\s*var\(--z-sticky/)
  assert.match(block, /env\(safe-area-inset-bottom\)/)
  // Ombre --shadow-lg posée sur .bulk-bar lui-même (pas de doublon de style).
  assert.match(CSS_SRC, /\.lp-bulk-float \.bulk-bar \{[\s\S]{0,80}box-shadow:\s*var\(--shadow-lg\)/)
})
