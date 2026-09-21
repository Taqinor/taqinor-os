// WIR255 — Budget vs réalisé (FG149), échéances retenues de garantie/cautions
// et export de la liasse de consolidation : 4 sorties déjà prêtes côté serveur
// (ou côté comptaApi pour les échéances/la liasse) sans le moindre bouton.
// Test SOURCE (comme wir180/wir181/wir254) : vérifie le câblage sans monter
// React ni dépendre d'un mock comptaApi complet.
//   node --test src/features/compta/wir255.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const API_SRC = readFileSync(join(HERE, '../../api/comptaApi.js'), 'utf8')
const BUDGETS_SRC = readFileSync(join(HERE, 'pages/BudgetsPage.jsx'), 'utf8')
const ENGAGEMENTS_SRC = readFileSync(join(HERE, 'pages/EngagementsPage.jsx'), 'utf8')
const CONSOLIDATION_SRC = readFileSync(join(HERE, 'pages/ConsolidationGroupePage.jsx'), 'utf8')

test('comptaApi : budgets.vsRealise appelle vs_realise SOULIGNÉ (jamais vs-realise)', () => {
  assert.match(API_SRC, /vsRealise: \(id, params\) =>/)
  assert.match(API_SRC, /\/compta\/budgets\/\$\{id\}\/vs_realise\//)
  assert.doesNotMatch(API_SRC, /vs-realise/)
})

test('BudgetsPage : la variance Vs réalisé s’affiche et s’exporte en CSV', () => {
  assert.match(BUDGETS_SRC, /comptaApi\.budgets\.vsRealise\(budget\.id\)/)
  assert.match(BUDGETS_SRC, /comptaApi\.budgets\.vsRealise\(budget\.id, \{ export: 'csv' \}\)/)
  assert.match(BUDGETS_SRC, /<VsRealisePanel budget={budget} \/>/)
})

test('EngagementsPage : bloc « Échéances sous N jours » (+CSV) sur les 2 panneaux (RG et cautions)', () => {
  // Les 2 wrappers étaient déjà prêts côté comptaApi (retenuesGarantie/
  // cautionsBancaires.echeances) — ce test vérifie qu'ils sont désormais
  // effectivement APPELÉS depuis l'écran.
  assert.match(ENGAGEMENTS_SRC, /fetchFn={comptaApi\.retenuesGarantie\.echeances}/)
  assert.match(ENGAGEMENTS_SRC, /fetchFn={comptaApi\.cautionsBancaires\.echeances}/)
  // « Silencieux sans rôle » : une erreur laisse le bloc vide, jamais un toast.
  // `\r?\n` (pas `\n` nu) — Git checkout ces .jsx en CRLF sur Windows (voir
  // .gitattributes / autocrlf), un `\n` seul ne matcherait jamais la fin de
  // la fonction sur ce genre de checkout.
  const bloc = ENGAGEMENTS_SRC.match(
    /function EcheancesSousNJoursCard[\s\S]*?\r?\n}\r?\n/)[0]
  assert.match(bloc, /\.catch\(\(\) => setData\(null\)\)/)
  assert.match(bloc, /if \(!loading && !data\) return null/)
  assert.doesNotMatch(bloc.replace(/\/\/.*$/gm, ''), /toast\.error/)
})

test('ConsolidationGroupePage : « Exporter la liasse (XLSX) » par cycle', () => {
  assert.match(CONSOLIDATION_SRC, /id: 'export-liasse'/)
  assert.match(CONSOLIDATION_SRC, /label: 'Exporter la liasse \(XLSX\)'/)
  assert.match(CONSOLIDATION_SRC, /comptaApi\.cyclesConsolidation\.exportLiasse\(cycle\.id\)/)
})
