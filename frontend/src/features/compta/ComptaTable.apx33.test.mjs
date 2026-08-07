// APX33 — plus une table nue en compta : les 6 (dont la 6ᵉ oubliée).
// Six `<table>` étaient encore écrites à la main dans `features/compta/pages/`,
// exactement là où le comptable a le plus besoin de trier et d'exporter.
// Elles passent toutes par `ComptaTable`, qui enveloppe le primitif PARTAGÉ
// `pages/reporting/Table` (15 consommateurs réels) en lui ajoutant le tri au
// clic et l'export CSV.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { toCsv, sortRows } from './comptaTableData.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PAGES = path.join(__dirname, 'pages')
const page = (f) => readFileSync(path.join(PAGES, f), 'utf8')

test('zéro table écrite à la main dans features/compta/pages/', () => {
  const offenders = []
  for (const f of readdirSync(PAGES)) {
    if (!f.endsWith('.jsx') || f.includes('.test.')) continue
    const src = page(f)
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    if (/<table\b/.test(code)) offenders.push(f)
  }
  assert.deepEqual(offenders, [], `table nue restante : ${offenders.join(', ')}`)
})

test('les SEPT tables sont migrées (6 APX33 + le plan fiscal PACT163)', () => {
  const attendu = {
    'TresoreriePage.jsx': 3, // Position, Prévisionnel, Journal de caisse
    'EngagementsPage.jsx': 1, // Provisions FNP/FAE
    // PACT163 (XACC16) a ajouté le PLAN FISCAL dérogatoire à côté du plan
    // comptable : deux tableaux distincts, deux bases légales distinctes.
    'ImmobilisationsPage.jsx': 2, // Plan d'amortissement + plan fiscal
    'RapprochementsPage.jsx': 1, // Suggestions d'appariement (dialogue)
  }
  let total = 0
  for (const [f, n] of Object.entries(attendu)) {
    const src = page(f)
    assert.match(src, /import ComptaTable from '\.\.\/ComptaTable'/, `${f} : import`)
    const count = (src.match(/<ComptaTable\r?\n/g) || []).length
    assert.equal(count, n, `${f} : ${count} table(s) migrée(s) au lieu de ${n}`)
    total += count
  }
  // 6 tables APX33 d'origine + le plan fiscal ajouté par PACT163.
  assert.equal(total, 7)
})

test('ComptaTable s’appuie sur le primitif partagé, sans le réécrire', () => {
  const src = readFileSync(path.join(__dirname, 'ComptaTable.jsx'), 'utf8')
  assert.match(src, /import \{ Table as SharedTable \} from '\.\.\/\.\.\/pages\/reporting\/Table'/)
  assert.match(src, /<SharedTable/)
  // Aucune balise `<table>` réécrite ici.
  assert.doesNotMatch(src.replace(/\/\*[\s\S]*?\*\//g, ''), /<table\b/)
})

test('les montants sont à droite et en typographie de données', () => {
  // Chaque colonne d'argent déclare `align: 'right'` + `numeric` (qui pose la
  // classe `.num`, la data typography VX5).
  for (const f of ['TresoreriePage.jsx', 'EngagementsPage.jsx', 'ImmobilisationsPage.jsx']) {
    assert.match(page(f), /align: 'right', numeric: true/, f)
  }
  const src = readFileSync(path.join(__dirname, 'ComptaTable.jsx'), 'utf8')
  assert.match(src, /cellClassName: c\.numeric \? 'num' : c\.cellClassName/)
})

test('l’export CSV est construit dans le navigateur (aucun endpoint nouveau)', () => {
  const src = readFileSync(path.join(__dirname, 'ComptaTable.jsx'), 'utf8')
  assert.doesNotMatch(src, /comptaApi|axios|fetch\(/)
  const csv = toCsv(
    [{ key: 'libelle', label: 'Compte' }, { key: 'solde', label: 'Solde' }],
    [{ libelle: 'Banque "A"', solde: 1200 }, { libelle: 'Caisse', solde: 0 }],
  )
  const lignes = csv.split('\r\n')
  assert.equal(lignes[0], '﻿"Compte";"Solde"')
  // Les guillemets d'une valeur sont bien échappés (doublés).
  assert.equal(lignes[1], '"Banque ""A""";"1200"')
  assert.equal(lignes[2], '"Caisse";"0"')
})

test('le tri utilise sortValue quand la colonne en fournit une', () => {
  const columns = [
    { key: 'solde', label: 'Solde', sortValue: (r) => Number(r.solde) || 0 },
    { key: 'libelle', label: 'Compte' },
  ]
  const rows = [
    { libelle: 'Caisse', solde: '900' },
    { libelle: 'Banque', solde: '1200' },
    { libelle: 'Épargne', solde: null },
  ]
  // Numérique via sortValue : « 900 » AVANT « 1200 » (un tri TEXTE ferait
  // l'inverse) ; la colonne normalise l'absence de solde à 0.
  const parSolde = sortRows(columns, rows, { key: 'solde', dir: 'asc' })
  assert.deepEqual(parSolde.map((r) => r.libelle), ['Épargne', 'Caisse', 'Banque'])
  // Alphabétique FR sur une colonne sans sortValue (É trié comme E).
  const parNom = sortRows(columns, rows, { key: 'libelle', dir: 'asc' })
  assert.deepEqual(parNom.map((r) => r.libelle), ['Banque', 'Caisse', 'Épargne'])
  // Sans clé de tri, l'ordre serveur est préservé À L'IDENTIQUE.
  assert.equal(sortRows(columns, rows, { key: null }), rows)
})
