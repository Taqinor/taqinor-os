// APX17 — Hygiène premium Ventes.
//   1. plus UNE SEULE popup du système (window.confirm/alert) dans
//      pages/ventes/ : tout passe par le dialogue maison (VX19/L152) ;
//   2. la cellule Statut de la liste des devis empilait jusqu'à SIX blocs :
//      hauteur de ligne du simple au triple — et comme la liste tourne sur
//      `ui/datatable`, qui ESTIME une hauteur constante au-delà de ~100
//      lignes, la variabilité décalait aussi le scroll. Elle est plafonnée à
//      StatusPill + piste documentaire, le reste dans un Popover « Détails » ;
//   3. la page Relances rendait encore une table écrite à la main : elle passe
//      au tableau PARTAGÉ du reporting, avec tri et export CSV.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const read = (f) => readFileSync(path.join(__dirname, f), 'utf8')

test('plus une seule popup du système dans pages/ventes/', () => {
  const offenders = []
  for (const f of readdirSync(__dirname)) {
    if (!f.endsWith('.jsx') || f.includes('.test.')) continue
    const src = read(f)
    // Le code seul : un commentaire a le droit de raconter l'histoire.
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    if (/window\.(confirm|alert)\s*\(/.test(code)) offenders.push(f)
  }
  assert.deepEqual(offenders, [], `popup système restante : ${offenders.join(', ')}`)
})

test('les 5 écrans qui confirmaient utilisent le dialogue maison', () => {
  for (const f of ['DevisGenerator.jsx', 'DevisList.jsx', 'FactureList.jsx',
    'RelancesPage.jsx', 'BonCommandeList.jsx']) {
    const src = read(f)
    assert.match(src, /useConfirmDialog/, `${f} : dialogue maison absent`)
    assert.match(src, /await confirm(Delete)?\(/, `${f} : confirmation non attendue`)
  }
})

test('la cellule Statut est PLAFONNÉE : pastille + piste, le reste en Popover', () => {
  const src = read('DevisList.jsx')
  const start = src.indexOf('<td data-label="Statut">')
  const end = src.indexOf('</td>', start)
  const cell = src.slice(start, end)
  assert.ok(start > 0 && end > start, 'cellule Statut introuvable')
  // Exactement deux signaux permanents dans la cellule.
  assert.match(cell, /<StatusPill/)
  assert.match(cell, /<DocumentStageTrack/)
  assert.match(cell, /statutDetails\.length > 0/)
  // Les blocs empilés ont bien quitté la cellule.
  for (const gone of ['Proposition signée', 'Devis accepté mais BC annulé', 'BC : ']) {
    assert.ok(!cell.includes(gone), `« ${gone} » empile encore la cellule`)
  }
  // ... et vivent dans la liste de détails, aucun signal perdu.
  assert.match(src, /const statutDetails = \[/)
  for (const kept of ['Proposition signée', 'Devis accepté mais BC annulé',
    'Avis demandé — en attente', 'Option :']) {
    assert.ok(src.includes(kept), `signal « ${kept} » perdu`)
  }
  // L'anomalie reste signalée SUR la ligne, même repliée.
  assert.match(cell, /bon_commande_etat\?\.mismatch/)
})

test('aucun CSS <td> artisanal n’a été ajouté pour plafonner la hauteur', () => {
  const css = readFileSync(path.join(__dirname, '..', '..', 'index.css'), 'utf8')
  assert.doesNotMatch(css, /APX17[\s\S]{0,400}?td\s*\{/)
})

test('la page Relances rejoint le tableau partagé, triable et exportable', () => {
  const src = read('RelancesPage.jsx')
  assert.match(src, /import \{ Table \} from '\.\.\/reporting\/Table'/)
  assert.match(src, /<Table\b/)
  assert.doesNotMatch(src, /<table className="data-table"/)
  // Le tri par montant dû existant est conservé (en-tête cliquable).
  assert.match(src, /onClick=\{\(\) => setSortByDu\(v => !v\)\}/)
  // Export CSV construit dans le navigateur : aucun endpoint nouveau.
  assert.match(src, /const exporterCsv = \(\) => \{/)
  assert.match(src, /Exporter CSV/)
  assert.doesNotMatch(src, /ventesApi\.export/)
})
