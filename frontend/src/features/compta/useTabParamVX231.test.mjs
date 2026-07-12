// VX231 — La navigation finance atterrit sur la CIBLE : ?facture=, lien client,
// onglet persistant, TVA↔Grand-livre. Test SOURCE (aucun node_modules ici) :
// on prouve le CÂBLAGE (hook + adoptions + deep-links) au niveau du code.
//   node --test src/features/compta/useTabParamVX231.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const HOOK = read('components/useTabParam.js')
const FACTURE_LIST = read('../../pages/ventes/FactureList.jsx')
const PAIEMENTS = read('../../pages/ventes/PaiementsPage.jsx')
const FISCALITE = read('pages/FiscalitePage.jsx')
const ETATS = read('pages/EtatsPage.jsx')

test('VX231(c) : useTabParam synchronise l\'onglet avec ?onglet (clé configurable), en replace', () => {
  assert.match(HOOK, /export function useTabParam\(defaultTab, param = 'onglet'\)/)
  assert.match(HOOK, /searchParams\.get\(param\)/)
  assert.match(HOOK, /\{ replace: true \}/)
  // Onglet par défaut → URL propre (param retiré).
  assert.match(HOOK, /if \(!next \|\| next === defaultTab\) p\.delete\(param\)/)
})

test('VX231(c) : les 7 pages compta à onglets adoptent useTabParam (une ligne)', () => {
  const pages = {
    EffetsPage: "useTabParam('effets')",
    EngagementsPage: "useTabParam('retenuesGarantie')",
    FiscalitePage: "useTabParam('declarationsTva')",
    NotesDeFraisPage: "useTabParam('notesFrais')",
    RapprochementsPage: "useTabParam('bancaires')",
    TresoreriePage: "useTabParam('tresorerie')",
  }
  for (const [page, call] of Object.entries(pages)) {
    const src = read(`pages/${page}.jsx`)
    assert.ok(src.includes(call), `${page} doit adopter ${call}`)
    assert.match(src, /import.*useTabParam.*from '\.\.\/components\/useTabParam'/)
  }
  // EtatsPage utilise la clé « etat » (aussi cible du deep-link GL).
  assert.match(ETATS, /useTabParam\('balance', 'etat'\)/)
})

test('VX231(a) : FactureList lit ?facture=, surligne + scrolle la ligne cible', () => {
  assert.match(FACTURE_LIST, /useSearchParams/)
  assert.match(FACTURE_LIST, /searchParams\.get\('facture'\)/)
  assert.match(FACTURE_LIST, /id=\{`facture-row-\$\{f\.id\}`\}/)
  assert.match(FACTURE_LIST, /getElementById\(`facture-row-\$\{highlightFactureId\}`\)/)
  assert.match(FACTURE_LIST, /scrollIntoView/)
  assert.match(FACTURE_LIST, /isHighlighted \? 'ring-2/)
})

test('VX231(b) : PaiementsPage rend le client cliquable → filtre local ?client=<id>', () => {
  assert.match(PAIEMENTS, /useSearchParams/)
  assert.match(PAIEMENTS, /searchParams\.get\('client'\)/)
  assert.match(PAIEMENTS, /onClick=\{\(\) => setClientFilter\(p\.client\)\}/)
  // filtrage local par id (déjà chargé, zéro appel réseau)
  assert.match(PAIEMENTS, /clientFilter && String\(p\.client\) !== clientFilter/)
})

test('VX231(d) : FiscalitePage propose « Comparer au Grand-livre » → EtatsPage pré-filtré', () => {
  assert.match(FISCALITE, /Comparer au Grand-livre/)
  assert.match(FISCALITE, /\/comptabilite\/etats\?etat=grand-livre/)
  assert.match(FISCALITE, /date_debut=\$\{row\.date_debut\}&date_fin=\$\{row\.date_fin\}/)
  // EtatsPage pré-remplit sa plage depuis l'URL (deep-link).
  assert.match(ETATS, /useState\(\(\) => searchParams\.get\('date_debut'\) \|\| ''\)/)
  assert.match(ETATS, /useState\(\(\) => searchParams\.get\('date_fin'\) \|\| ''\)/)
})
