// Régression « aperçu devis cassé » (panneau lead).
// Exécutés en CI : node --test src/features/ventes/previewPdf.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  proposalParams, pdfBlob, PDF_MIME,
  previewView, classifyFetchError, PREVIEW_VIEW,
} from './previewPdf.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const PANEL = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'LeadDevisPanel.jsx'), 'utf8')
const PDFCANVAS = readFileSync(join(HERE, 'PdfCanvas.jsx'), 'utf8')

test('proposalParams : Premium = full, étude respectée', () => {
  assert.deepEqual(proposalParams('full', false), {
    pdf_mode: 'full', include_etude: 0,
  })
  assert.deepEqual(proposalParams('full', true), {
    pdf_mode: 'full', include_etude: 1,
  })
})

test('proposalParams : 1 page = onepage, et n’envoie JAMAIS l’étude', () => {
  assert.deepEqual(proposalParams('onepage', false), {
    pdf_mode: 'onepage', include_etude: 0,
  })
  // include_etude n’a pas de sens en 1 page : forcé à 0 même si coché.
  assert.deepEqual(proposalParams('onepage', true), {
    pdf_mode: 'onepage', include_etude: 0,
  })
})

test('proposalParams : tout mode inconnu retombe sur Premium (full)', () => {
  assert.equal(proposalParams(undefined, false).pdf_mode, 'full')
  assert.equal(proposalParams('', true).pdf_mode, 'full')
})

test('pdfBlob : emballe les octets en Blob application/pdf affichable', async () => {
  // Octets façon réponse axios responseType:'blob' (en-tête %PDF d’un vrai PDF).
  const bytes = new TextEncoder().encode('%PDF-1.7\n…octets…')
  const blob = pdfBlob(bytes)
  assert.equal(blob.type, PDF_MIME, 'le type DOIT être application/pdf')
  assert.equal(blob.size, bytes.byteLength)
  // Le contenu transite intact -> l’iframe affiche le PDF, pas une icône cassée.
  const head = new Uint8Array(await blob.arrayBuffer()).subarray(0, 5)
  assert.deepEqual([...head], [...new TextEncoder().encode('%PDF-')])
})

// ── Repli gracieux quand l'aperçu inline ne se rend pas ──────────────────────

test('previewView : aperçu bloqué (bloqueur/timeout) -> REPLI, pas le PDF brut', () => {
  // Le fetch a réussi (hasUrl) mais l'iframe ne s'est pas rendue (bloquée).
  // On NE doit PAS rester sur le cadre PDF/bloqué : on bascule sur le repli.
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: true, hasUrl: true }),
    PREVIEW_VIEW.FALLBACK,
  )
})

test('previewView : échec réseau du fetch -> REPLI (téléchargeable)', () => {
  // Pas d'URL (le fetch a échoué côté réseau) mais blocked=true -> repli.
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: true, hasUrl: false }),
    PREVIEW_VIEW.FALLBACK,
  )
})

test('previewView : rendu normal -> PDF ; chargement -> LOADING', () => {
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: false, hasUrl: true }),
    PREVIEW_VIEW.PDF,
  )
  assert.equal(
    previewView({ loading: true, serverError: false, blocked: false, hasUrl: false }),
    PREVIEW_VIEW.LOADING,
  )
})

test('previewView : vrai échec serveur prime et reste un message d’ERREUR distinct', () => {
  // Un 4xx/5xx réel (PDF impossible à générer) ne doit PAS devenir le repli
  // "bloqueur" : il garde son message clair, même si blocked était vrai.
  assert.equal(
    previewView({ loading: false, serverError: true, blocked: true, hasUrl: false }),
    PREVIEW_VIEW.ERROR,
  )
})

test('classifyFetchError : réponse HTTP 4xx/5xx = serveur ; sinon réseau', () => {
  assert.equal(classifyFetchError({ response: { status: 500 } }), 'server')
  assert.equal(classifyFetchError({ response: { status: 404 } }), 'server')
  // Timeout / connexion coupée : pas de réponse -> réseau (repli gracieux).
  assert.equal(classifyFetchError({ code: 'ECONNABORTED' }), 'network')
  assert.equal(classifyFetchError({ request: {} }), 'network')
  assert.equal(classifyFetchError(undefined), 'network')
})

// ── L'aperçu rend via PDF.js (canvas), JAMAIS un embed blocable ──────────────

test('le panneau ne contient AUCUN embed PDF blocable (iframe/embed/object)', () => {
  // Un <iframe>/<embed>/<object> pointant le PDF se fait bloquer par un
  // bloqueur de pub / la politique PDF de Chrome. Le rendu doit passer par
  // PDF.js (canvas), inblocable.
  assert.ok(!/<iframe[\s/>]/.test(PANEL), 'aucune <iframe> dans le panneau')
  assert.ok(!/<embed[\s/>]/.test(PANEL), 'aucun <embed> dans le panneau')
  assert.ok(!/<object[\s/>]/.test(PANEL), 'aucun <object> dans le panneau')
})

test('le panneau rend l’aperçu via PDF.js (PdfCanvas)', () => {
  assert.match(PANEL, /PdfCanvas/, 'le panneau monte le composant PdfCanvas')
  assert.match(PANEL, /blob=\{previewBlob\}/, 'il passe les octets (blob) à PDF.js')
})

test('PdfCanvas dessine les octets via pdf.js sur des canvas (worker local)', () => {
  assert.match(PDFCANVAS, /from 'pdfjs-dist'/)
  assert.match(PDFCANVAS, /getDocument/, 'charge le PDF depuis les octets')
  assert.match(PDFCANVAS, /createElement\(['"]canvas['"]\)/, 'dessine sur canvas')
  assert.match(PDFCANVAS, /\.render\(/, 'rend chaque page')
  // Worker servi depuis NOTRE origine (Vite ?worker), pas un CDN blocable.
  assert.match(PDFCANVAS, /pdf\.worker\.min\.mjs\?worker/)
  assert.match(PDFCANVAS, /workerPort/)
})

test('échec du fetch des octets -> repli FR avec bouton « Télécharger »', () => {
  // 1) le réseau qui échoue mène bien au repli (logique pure)
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: true, hasUrl: false }),
    PREVIEW_VIEW.FALLBACK,
  )
  // 2) le bloc repli du panneau offre le téléchargement qui marche
  assert.match(PANEL, /PREVIEW_VIEW\.FALLBACK/)
  assert.match(PANEL, /Télécharger le PDF/)
  assert.match(PANEL, /onClick=\{handleDownload\}/)
})
