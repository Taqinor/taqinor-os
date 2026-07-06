import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// FE1 — verrouille le CONTRAT REST des endpoints round-2 de la paie marocaine
// (XPAI/ZPAI/YHIRE) nouvellement câblés côté frontend (PaieRunWizard,
// PaieParametres, PaieDeclarations, BulletinList). Le module importe
// `./axios` (effet de bord) : on verrouille le contrat textuel plutôt que de
// mocker le graphe ESM — même méthode que CH6/WR10.

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'paieApi.js'), 'utf8')

test('XPAI1 — stc → POST profils/<id>/stc/', () => {
  assert.match(src, /stc: \(id, data\) => api\.post\(`\/paie\/profils\/\$\{id\}\/stc\/`, data\)/)
})

test('XPAI1 — stcPdf → GET profils/<id>/stc-pdf/ en blob', () => {
  assert.match(src, /stcPdf:[\s\S]*?api\.get\(`\/paie\/profils\/\$\{id\}\/stc-pdf\/`, \{ responseType: 'blob' \}\)/)
})

test('YHIRE3/XPAI15/ZPAI2 — avertissements/controle-completude/controle-ecarts sur périodes', () => {
  assert.match(src, /avertissements: \(id\) => api\.get\(`\/paie\/periodes\/\$\{id\}\/avertissements\/`\)/)
  assert.match(src, /controleCompletude:[\s\S]*?api\.get\(`\/paie\/periodes\/\$\{id\}\/controle-completude\/`\)/)
  assert.match(src, /controleEcarts: \(id, params\) =>[\s\S]*?api\.get\(`\/paie\/periodes\/\$\{id\}\/controle-ecarts\/`, \{ params \}\)/)
})

test('XPAI3 — régimes/adhésions mutuelle', () => {
  assert.match(src, /getRegimesMutuelle:[\s\S]*?api\.get\('\/paie\/regimes-mutuelle\/', \{ params \}\)/)
  assert.match(src, /getAdhesionsMutuelle:[\s\S]*?api\.get\('\/paie\/adhesions-mutuelle\/', \{ params \}\)/)
})

test('XPAI4 — runGratification → POST periodes/<id>/run-gratification/', () => {
  assert.match(src, /runGratification: \(id, data\) =>\s*api\.post\(`\/paie\/periodes\/\$\{id\}\/run-gratification\/`, data\)/)
})

test('XPAI8 — fichierVirement supporte ?format_banque=simt', () => {
  assert.match(src, /fichierVirement: \(id, formatBanque\) =>[\s\S]*?format_banque: formatBanque/)
})

test('XPAI9 — rejeterLigneVirement / reemettreLigneVirement', () => {
  assert.match(src, /rejeterLigneVirement:[\s\S]*?api\.post\(`\/paie\/lignes-virement\/\$\{id\}\/rejeter\/`/)
  assert.match(src, /reemettreLigneVirement:[\s\S]*?api\.post\(`\/paie\/lignes-virement\/\$\{id\}\/reemettre\/`/)
})

test('XPAI12/XPAI13 — dépôt BDS complémentaire + XML SIMPL-IR', () => {
  assert.match(src, /deposerBdsComplementaire:[\s\S]*?api\.post\(`\/paie\/periodes\/\$\{id\}\/deposer-bds-complementaire\/`, data\)/)
  assert.match(src, /etatIrAnnuelXml:[\s\S]*?api\.get\('\/paie\/periodes\/etat-ir-annuel-xml\/', \{ params: \{ annee \} \}\)/)
})

test('XPAI16 — brutPourNet (simulateur net/brut)', () => {
  assert.match(src, /brutPourNet: \(id, params\) =>\s*api\.get\(`\/paie\/periodes\/\$\{id\}\/brut-pour-net\/`, \{ params \}\)/)
})

test('XPAI18 — expirerRegimesExoneration', () => {
  assert.match(src, /expirerRegimesExoneration:[\s\S]*?api\.post\('\/paie\/profils\/expirer-regimes\/'\)/)
})

test('XPAI22 — reprise des cumuls dry-run + commit (multipart)', () => {
  assert.match(src, /repriseDryRun:[\s\S]*?\/paie\/cumuls-annuels\/reprise-dry-run\//)
  assert.match(src, /repriseCommit:[\s\S]*?\/paie\/cumuls-annuels\/reprise-commit\//)
})

test('ZPAI1 — analysePaie / analysePaieCsv sur bulletins/analyse/', () => {
  assert.match(src, /analysePaie: \(params\) => api\.get\('\/paie\/bulletins\/analyse\/', \{ params \}\)/)
  assert.match(src, /analysePaieCsv:[\s\S]*?export: 'csv' \}, responseType: 'blob' \}\)/)
})

test('ZPAI3 — coutEmployeur / coutGlobal sur périodes', () => {
  assert.match(src, /coutGlobal: \(id\) => api\.get\(`\/paie\/periodes\/\$\{id\}\/cout-global\/`\)/)
  assert.match(src, /coutEmployeur: \(id\) => api\.get\(`\/paie\/periodes\/\$\{id\}\/cout-employeur\/`\)/)
})

test('ZPAI4 — annulerBulletin → POST bulletins/<id>/annuler/', () => {
  assert.match(src, /annulerBulletin: \(id, data\) =>\s*api\.post\(`\/paie\/bulletins\/\$\{id\}\/annuler\/`, data\)/)
})

test('ZPAI5 — bulletinsPdf (impression en lot) → GET periodes/<id>/bulletins-pdf/ en blob', () => {
  assert.match(src, /bulletinsPdf: \(id\) =>\s*api\.get\(`\/paie\/periodes\/\$\{id\}\/bulletins-pdf\/`, \{ responseType: 'blob' \}\)/)
})

test('ZPAI6/ZPAI7 — annulerSaisie / creerLotSaisies', () => {
  assert.match(src, /annulerSaisie:[\s\S]*?api\.post\(`\/paie\/saisies\/\$\{id\}\/annuler\/`/)
  assert.match(src, /creerLotSaisies: \(data\) => api\.post\('\/paie\/saisies\/creer-lot\/', data\)/)
})
