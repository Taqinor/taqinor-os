// Garde de non-régression — CI run 32200473257 (PR #538, devis.spec.js E4).
// `LeadDevisPanel.jsx` (et `DevisGenerator.jsx`, même bug) appelaient
// `stockApi.getProduits()` SANS paramètre pour charger le catalogue avant un
// devis automatique — page 1 SEULE (`StandardPagination.page_size = 50`,
// `ProduitViewSet.ordering = ['nom']`). La trace réseau du run rouge le
// prouve : `{"count":101,"next":".../produits/?page=2", ...}`, les DEUX
// « Panneau … » tombant en page 2 — invisibles à `autoFillLines`, d'où
// « Devis auto impossible : aucun panneau du stock ne correspond ». Le
// correctif utilise `fetchAllPages` (VX54, déjà le chemin de
// `stockSlice.js`). Ce test lit le SOURCE (JSX non exécutable ici sans
// node_modules) pour verrouiller que le fil ne régresse pas vers l'appel nu.
//
// Run : node --test src/pages/crm/leads/LeadDevisPanel.wiring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

// Ne garde que le CODE : une ligne de commentaire (// …) peut légitimement
// NOMMER l'ancien appel nu pour mémoire (voir les deux fichiers) sans que ce
// soit une régression — seul le code réel doit être absent.
const codeSansCommentaires = (src) => src
  .split('\n')
  .filter((ligne) => !ligne.trim().startsWith('//'))
  .join('\n')

const LDP = read('LeadDevisPanel.jsx')
const DG = read('../../ventes/DevisGenerator.jsx')
const LDP_CODE = codeSansCommentaires(LDP)
const DG_CODE = codeSansCommentaires(DG)

test('LeadDevisPanel importe fetchAllPages (VX54)', () => {
  assert.match(LDP, /import\s*\{\s*fetchAllPages\s*\}\s*from\s*'\.\.\/\.\.\/\.\.\/utils\/fetchAllPages'/)
})

test('LeadDevisPanel ne rappelle plus stockApi.getProduits() SANS paramètre (code réel, hors commentaires)', () => {
  // On tolère `stockApi.getProduits({ page })` (celui que fetchAllPages
  // construit) — seul l'appel NU (sans argument) est banni.
  assert.doesNotMatch(LDP_CODE, /stockApi\.getProduits\(\)/)
  assert.match(LDP_CODE, /fetchAllPages\(\s*\n?\s*\(page\)\s*=>\s*stockApi\.getProduits\(\{\s*page\s*\}\)/)
})

test('DevisGenerator importe fetchAllPages (VX54) — même bug, même correctif', () => {
  assert.match(DG, /import\s*\{\s*fetchAllPages\s*\}\s*from\s*'\.\.\/\.\.\/utils\/fetchAllPages'/)
})

test('DevisGenerator ne rappelle plus stockApi.getProduits() SANS paramètre (code réel, hors commentaires)', () => {
  assert.doesNotMatch(DG_CODE, /stockApi\.getProduits\(\)/)
  assert.match(DG_CODE, /fetchAllPages\(\(page\)\s*=>\s*stockApi\.getProduits\(\{\s*page\s*\}\)/)
})

// QJR652 — le téléchargement passe par le helper partagé (chemin iOS / PWA) :
// la fenêtre est ouverte dans le geste, AVANT le premier await.
test('QJR652 — handleDownload ouvre downloadBlobInGesture avant getProposalPdf', () => {
  const i = LDP_CODE.indexOf('downloadBlobInGesture()')
  const j = LDP_CODE.indexOf('ventesApi.getProposalPdf', LDP_CODE.indexOf('const handleDownload'))
  assert.ok(i > 0, 'downloadBlobInGesture() appelé')
  assert.ok(j > i, 'ouvert avant getProposalPdf')
  assert.doesNotMatch(LDP_CODE, /function downloadBlob\(/)
})

test('QJR653 — l\'aperçu passe par usePdfPreview + PdfPreviewBody, plus d\'état local', () => {
  assert.match(LDP_CODE, /import \{ usePdfPreview \} from '\.\.\/\.\.\/\.\.\/features\/ventes\/usePdfPreview'/)
  assert.match(LDP_CODE, /import PdfPreviewBody from '\.\.\/\.\.\/\.\.\/features\/ventes\/PdfPreviewBody'/)
  assert.match(LDP_CODE, /<PdfPreviewBody\b/)
  assert.doesNotMatch(LDP_CODE, /previewReloadKey/)
  assert.doesNotMatch(LDP_CODE, /new AbortController/)
})

test('QJR589 — LeadDevisPanel monte BandeauDeriveLead sur le détail déjà lu (code réel)', () => {
  assert.match(LDP_CODE, /import BandeauDeriveLead from '\.\.\/\.\.\/\.\.\/features\/ventes\/quote\/BandeauDeriveLead'/)
  assert.match(LDP_CODE, /<BandeauDeriveLead[\s\S]{0,200}champs=\{devisRecord\.lead_valeurs_modifiees\}/)
})

// EDC10 — Groupe EDC (09/10/2026) : le contrat entre le panneau et le
// générateur embarqué est CÂBLÉ dans le JSX réel (jamais seulement décrit) —
// `onDirtyChange` (sorties protégées, EDC6), `onEnregistre` (rester dans
// l'éditeur après l'enregistrement, EDC7/EDC11), `onVoirPdf` (barre en tête,
// EDC4). Et la règle CSS EDC2 neutralise le plafond LDPQ1 SANS l'éditer
// (surface append-only : la règle d'origine doit rester à l'octet).
const CSS = read('../../../index.css')

test('EDC10 — LeadDevisPanel passe onDirtyChange / onEnregistre / onVoirPdf à <DevisGenerator>', () => {
  const bloc = LDP_CODE.slice(LDP_CODE.indexOf('<DevisGenerator'))
  const jsx = bloc.slice(0, bloc.indexOf('/>') + 2)
  assert.match(jsx, /\bembedded\b/)
  assert.match(jsx, /onDirtyChange=\{/)
  assert.match(jsx, /onEnregistre=\{/)
  assert.match(jsx, /onVoirPdf=\{/)
})

test('EDC10 — index.css : le plafond 980 px (LDPQ1) est intact et neutralisé par la règle EDC2 ajoutée en fin', () => {
  assert.match(CSS, /\.ldp-edit \.gen-embedded \{ max-width: 980px; margin: 0 auto; \}/)
  const origine = CSS.indexOf('.ldp-edit .gen-embedded { max-width: 980px')
  const edc2 = CSS.search(/\.ldp-body \.ldp-edit \.gen-embedded\s*\{[^}]*max-width:\s*none/)
  assert.ok(edc2 > origine, 'la règle EDC2 vient APRÈS la règle d\'origine (cascade)')
  assert.match(CSS, /\.gen-root\s*\{[^}]*container-type:\s*inline-size/)
})
