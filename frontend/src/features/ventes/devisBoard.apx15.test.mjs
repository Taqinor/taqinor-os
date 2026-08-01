// APX15 — Un VRAI board Ventes, et la fin du fichier qui ment.
//   (a) `VentesKanban.jsx` exportait `BonCommandeList()` : le nom du fichier
//       mentait. Renommé — l'URL `/ventes/bons-commande` est inchangée.
//   (b) le board des devis existe enfin, par statut DOCUMENT (règle #4),
//       sans AUCUNE action d'état par glisser-déposer.
//   (c) `FactureKanbanBoard` parle le même langage `kb-*`.
//   (d) plus une seule fuite de JSON brut dans pages/ventes/.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { devisBoardColumns, effectiveStatut, DEVIS_BOARD_COLUMNS } from './devisBoard.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PAGES = path.join(__dirname, '..', '..', 'pages', 'ventes')
const page = (f) => readFileSync(path.join(PAGES, f), 'utf8')

test('(a) le fichier ne ment plus, et l’URL du BC n’a pas bougé', () => {
  assert.ok(existsSync(path.join(PAGES, 'BonCommandeList.jsx')))
  assert.ok(!existsSync(path.join(PAGES, 'VentesKanban.jsx')))
  const cfg = readFileSync(path.join(__dirname, 'module.config.jsx'), 'utf8')
  assert.match(cfg, /\{ path: '\/ventes\/bons-commande', component: BonCommandeList \}/)
  assert.match(cfg, /import\('\.\.\/\.\.\/pages\/ventes\/BonCommandeList'\)/)
})

test('(b) les colonnes sont les statuts DOCUMENT, jamais le funnel STAGES.py', () => {
  assert.deepEqual(
    DEVIS_BOARD_COLUMNS.map(c => c.key),
    ['brouillon', 'envoye', 'accepte', 'refuse', 'expire'],
  )
  const src = readFileSync(path.join(__dirname, 'devisBoard.js'), 'utf8')
  for (const stage of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD']) {
    assert.doesNotMatch(src, new RegExp(`['"\`]${stage}['"\`]`), `clé de funnel ${stage} interdite`)
  }
})

test('(b) le regroupement compte et totalise par colonne', () => {
  const cols = devisBoardColumns([
    { id: 1, statut: 'brouillon', total_ttc: 1000 },
    { id: 2, statut: 'brouillon', total_ttc: 500 },
    { id: 3, statut: 'accepte', total_ttc: 9000 },
    { id: 4, statut: 'inconnu', total_ttc: 42 },
  ])
  const by = Object.fromEntries(cols.map(c => [c.key, c]))
  assert.equal(by.brouillon.count, 2)
  assert.equal(by.brouillon.total, 1500)
  assert.equal(by.accepte.count, 1)
  // Un statut inconnu n'invente aucune colonne et n'est compté nulle part.
  assert.equal(cols.reduce((s, c) => s + c.count, 0), 3)
})

test('(b) une validité dépassée tombe dans « Expiré » sans changer le statut stocké', () => {
  assert.equal(effectiveStatut({ statut: 'envoye', is_expired: true }), 'expire')
  assert.equal(effectiveStatut({ statut: 'envoye' }), 'envoye')
})

test('(b) AUCUNE action d’état par glisser-déposer sur les boards d’argent', () => {
  for (const f of ['DevisKanbanBoard.jsx', 'FactureKanbanBoard.jsx']) {
    const src = page(f)
    assert.doesNotMatch(src, /dnd-kit|useDraggable|useDroppable|onDragEnd|draggable=/, f)
    assert.match(src, /kb-board-static/, f)
  }
  const css = readFileSync(path.join(__dirname, '..', '..', 'index.css'), 'utf8')
  assert.match(css, /\.kb-board-static \.kb-card \{[\s\S]{0,120}?cursor: pointer;/)
})

test('(c) les deux boards parlent le langage kb-*', () => {
  for (const f of ['DevisKanbanBoard.jsx', 'FactureKanbanBoard.jsx']) {
    const src = page(f)
    for (const cls of ['kb-board', 'kb-col', 'kb-col-header', 'kb-col-title', 'kb-col-count', 'kb-card']) {
      assert.match(src, new RegExp(cls), `${f} : ${cls} attendu`)
    }
  }
  // Le contrat de test historique de la vue factures est conservé.
  const fkb = page('FactureKanbanBoard.jsx')
  for (const id of ['facture-kanban-board', 'fkb-column-', 'fkb-count-', 'fkb-total-']) {
    assert.ok(fkb.includes(id), `testid ${id} perdu`)
  }
})

test('(b) la liste des devis monte réellement le board', () => {
  const src = page('DevisList.jsx')
  assert.match(src, /import DevisKanbanBoard from '\.\/DevisKanbanBoard'/)
  assert.match(src, /<DevisKanbanBoard\s+devis=\{filteredDevis\}/)
})

test('(d) plus une seule fuite de JSON brut dans pages/ventes/', () => {
  const offenders = []
  for (const f of readdirSync(PAGES)) {
    if (!f.endsWith('.jsx') || f.includes('.test.')) continue
    if (/JSON\.stringify\(\s*err/.test(page(f))) offenders.push(f)
  }
  assert.deepEqual(offenders, [], `JSON brut affiché : ${offenders.join(', ')}`)
})
