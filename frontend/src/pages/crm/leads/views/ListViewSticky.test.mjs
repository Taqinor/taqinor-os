// LB18 — scrolleur unique (.lv-wrap) + thead sticky + colonne nom sticky +
// colgroup à largeurs fixes (blueprint D4 : refit en place, `.lv-wrap` reste
// le SEUL ancêtre overflow — un ancêtre overflow-x séparé casserait le
// sticky vertical du thead, D1). Contrat conservé : `tr.lv-row`,
// `.lv-lead-name`, `.ie-cell`, `select.ie-input` (inchangés, non retouchés
// par cette tâche). Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/views/ListViewSticky.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '..', '..', '..', '..', 'index.css'), 'utf8')

test('LB18 : LIST_COLUMNS déclare un modèle de colonnes (id/header/width), 13 colonnes', () => {
  const start = SRC.indexOf('const LIST_COLUMNS = [')
  assert.ok(start > 0)
  const block = SRC.slice(start, SRC.indexOf(']', start) + 1)
  const ids = [...block.matchAll(/id: '([a-z_]+)'/g)].map((m) => m[1])
  assert.deepEqual(ids, [
    'lead', 'stage', 'score', 'telephone', 'ville', 'facture', 'canal',
    'owner', 'priorite', 'relance', 'next_activity', 'tags', 'actions',
  ])
  // Colonnes cœur jamais masquables (Lead/Stade/Relance/Actions) — le reste
  // reprend l'ensemble qui portait `.m-hide` (repli responsive existant).
  assert.match(block, /id: 'lead', header: 'Lead', width: \d+, hideable: false/)
  assert.match(block, /id: 'stage', header: 'Stade', width: \d+, hideable: false/)
  assert.match(block, /id: 'relance', header: 'Relance', width: \d+, hideable: false/)
  assert.match(block, /id: 'actions', header: 'Actions', width: \d+, hideable: false/)
})

test('LB18/LB19 : <colgroup> précède le <thead>, une <col> par colonne VISIBLE (+ case à cocher)', () => {
  const tableStart = SRC.indexOf('<table className="data-table lv-table calm-list">')
  assert.ok(tableStart > 0)
  const theadStart = SRC.indexOf('<thead', tableStart)
  const colgroupStart = SRC.indexOf('<colgroup>', tableStart)
  assert.ok(colgroupStart > tableStart && colgroupStart < theadStart, 'colgroup doit précéder thead')
  const block = SRC.slice(colgroupStart, theadStart)
  assert.match(block, /onToggleSelect && <col/)
  // LB19 — filtré par colonne cachée (le nombre de <col> doit toujours
  // correspondre au nombre de <td>/<th> réellement rendus).
  assert.match(block, /visibleColumns\.map\(\(c\) => <col key=\{c\.id\} style=\{\{ width: c\.width \}\} \/>\)/)
})

test('LB18 : la colonne Lead (th ET td) porte .lv-sticky-name — contrat tr.lv-row/.lv-lead-name intact', () => {
  assert.match(SRC, /<SortableTh col="lead" label="Lead" sort=\{sort\} onSort=\{onSort\} className="lv-sticky-name" \/>/)
  const start = SRC.indexOf('<td data-label="Lead"')
  assert.ok(start > 0)
  assert.match(SRC.slice(start, start + 60), /className="lv-sticky-name"/)
  // Contrat e2e inchangé (leads.spec E3/E7, datatable-breakpoint.spec).
  assert.match(SRC, /className=\{`lv-row/)
  assert.match(SRC, /<span className="lv-lead-name">/)
})

test('LB18 : listener de scroll PASSIF sur .lv-wrap (jamais un re-rendu React pour l\'ombre de bord)', () => {
  assert.match(SRC, /const wrapRef = useRef\(null\)/)
  assert.match(SRC, /el\.addEventListener\('scroll', onScroll, \{ passive: true \}\)/)
  assert.match(SRC, /el\.classList\.toggle\('lv-scrolled-x', el\.scrollLeft > 0\)/)
  assert.match(SRC, /<div className="lv-wrap" ref=\{wrapRef\}>/)
})

test('LB18 : index.css pose table-layout:fixed sur .lv-table + l\'ombre .lv-scrolled-x .lv-sticky-name', () => {
  assert.match(CSS, /\.lv-table \{\s*table-layout: fixed;\s*\}/)
  assert.match(CSS, /\.lv-wrap\.lv-scrolled-x \.lv-sticky-name \{\s*box-shadow: /)
})
