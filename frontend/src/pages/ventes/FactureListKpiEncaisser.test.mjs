// ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER — l'écran Factures ne se contredit plus :
// « Reste à encaisser » ignore brouillons/annulées/payées, et une facture au
// statut « en_retard » (même sans échéance) tombe dans l'onglet « En retard ».
// Test SOURCE (aucun node_modules requis) :
//   node --test src/pages/ventes/FactureListKpiEncaisser.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { lireSourcesFactureList } from './factureList/lireSources.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
// SPL211 — FactureList.jsx + factureList/*.{js,jsx} (la ligne et ses aides y vivent).
const SRC = lireSourcesFactureList()

test('Reste à encaisser (onglet) exclut brouillon, annulée et payée', () => {
  assert.match(SRC, /const STATUTS_HORS_ENCAISSEMENT = \['brouillon', 'annulee', 'payee'\]/)
  assert.match(SRC, /filtered\.reduce\(\(s, f\) => \(STATUTS_HORS_ENCAISSEMENT\.includes\(f\.statut\)/)
})

test('isOverdue couvre le statut « en_retard » (onglet En retard = lignes En retard)', () => {
  const m = SRC.match(/const isOverdue = \(f, aujourdhui\) =>([\s\S]*?)\r?\n\}\r?\n/)
  assert.ok(m, 'isOverdue introuvable')
  assert.match(m[1], /f\?\.statut === 'en_retard'/)
})
