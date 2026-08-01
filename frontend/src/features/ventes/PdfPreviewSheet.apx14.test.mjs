// APX14 — L'aperçu PDF ne quitte plus l'écran.
// Vérification STRUCTURELLE : le composant partagé existe, les deux écrans
// (devis + facture) le montent, la RÈGLE #4 est respectée (le panneau ne
// connaît AUCUNE URL de PDF : c'est l'appelant qui fournit les octets — le
// moteur vendorisé `/proposal` pour les devis, le PDF legacy pour les
// factures), et pdfjs reste hors du bundle par un import paresseux.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sheet = readFileSync(path.join(__dirname, 'PdfPreviewSheet.jsx'), 'utf8')
const page = (f) => readFileSync(path.join(__dirname, '..', '..', 'pages', 'ventes', f), 'utf8')
const css = readFileSync(path.join(__dirname, '..', '..', 'index.css'), 'utf8')

test('le panneau rend le PDF INLINE (PdfCanvas), jamais un onglet', () => {
  assert.match(sheet, /const PdfCanvas = lazy\(\(\) => import\('\.\/PdfCanvas'\)\)/)
  assert.match(sheet, /<PdfCanvas\b/)
  // Le rendu passe par ResponsiveDialog : panneau au bureau, tiroir bas en
  // mobile — zéro dépendance nouvelle.
  assert.match(sheet, /import \{ ResponsiveDialog \} from '\.\.\/\.\.\/ui\/ResponsiveDialog'/)
})

test('RÈGLE #4 — le panneau ne connaît AUCUNE URL de PDF', () => {
  // On regarde le CODE, pas la prose : les commentaires ont le droit de citer
  // `/proposal` pour expliquer d'où viennent les octets.
  const code = sheet.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /proposal/i, 'le panneau ne doit citer aucun chemin PDF')
  assert.doesNotMatch(code, /ventesApi|api\.get/, 'le panneau ne doit appeler aucune API de document')
  // Il reçoit les octets de l'appelant.
  assert.match(code, /fetchBlob/)
})

test('les DEUX écrans montent l’aperçu inline', () => {
  for (const f of ['DevisList.jsx', 'FactureList.jsx']) {
    const src = page(f)
    assert.match(src, /import PdfPreviewSheet from '\.\.\/\.\.\/features\/ventes\/PdfPreviewSheet'/, f)
    assert.match(src, /<PdfPreviewSheet\b/, f)
  }
})

test('le devis garde le moteur /proposal, la facture son PDF legacy', () => {
  const devis = page('DevisList.jsx')
  // L'aperçu du devis passe toujours par getProposalPdf (le SEUL chemin).
  assert.match(devis, /fetchDevisPreviewBlob[\s\S]{0,900}?ventesApi\.getProposalPdf/)
  // Et il n'ouvre plus d'onglet dans le handler d'aperçu.
  assert.match(devis, /const handlePreview = \(d\) => \{ setPreviewDevis\(d\) \}/)

  const facture = page('FactureList.jsx')
  assert.match(facture, /fetchFacturePreviewBlob[\s\S]{0,900}?ventesApi\.telechargerPdfFacture/)
  // Le PDF de facture ne passe JAMAIS par le moteur de proposition.
  assert.doesNotMatch(facture, /getProposalPdf/)
})

test('le repli reste offert : télécharger + ouvrir dans un onglet', () => {
  assert.match(sheet, /Télécharger/)
  assert.match(sheet, /Ouvrir dans un onglet/)
  // VX48 — l'ouverture d'onglet se fait sur un blob DÉJÀ en mémoire, donc
  // window.open est synchrone dans le geste (Safari iOS ne le bloque pas).
  assert.match(sheet, /ouvrirPdfBlob\(blob, filename\)/)
})

test('la zone d’aperçu a une hauteur : sans elle le canvas absolu ne se voit pas', () => {
  assert.match(css, /\.apx-pdf-preview \{[\s\S]{0,200}?position: relative;/)
  assert.match(css, /\.apx-pdf-preview \{[\s\S]{0,200}?height:/)
})
