// VX92 — « Enregistrer et créer un autre » + mort du window.alert du paiement.
// Aucun « save & new » n'existait dans le repo : 10 leads après un salon, 5
// paiements après un relevé, 20 produits à seeder = un cycle fermer/rouvrir
// par enregistrement (~10-30 s chacun). Verified against SOURCE (no
// node_modules in this worktree/lane — these pages import react-redux/ui,
// unrunnable standalone).
//   node --test src/pages/ventes/FactureListVX92.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
// VX230 — la modale de paiement a été extraite de FactureList vers le composant
// partagé PaiementDialog.jsx (montée aussi depuis RelancesPage). Les assertions
// « paiement » de VX92 suivent le code : elles ciblent désormais PaiementDialog.
const PAIEMENT_DIALOG_SRC = readFileSync(join(HERE, 'PaiementDialog.jsx'), 'utf8')
const PRODUIT_FORM_SRC = readFileSync(join(HERE, '../stock/ProduitForm.jsx'), 'utf8')
const CLIENT_FORM_SRC = readFileSync(join(HERE, '../crm/ClientForm.jsx'), 'utf8')

test('VX92 : le window.alert("Paiement enregistré.") est mort — remplacé par toast.success', () => {
  assert.doesNotMatch(PAIEMENT_DIALOG_SRC, /alert\('Paiement enregistré\.'\)/)
  assert.match(PAIEMENT_DIALOG_SRC, /toast\.success\('Paiement enregistré\.'\)/)
})

test('VX92 : pay-montant porte autoFocus (le dialog paiement peut se rouvrir sans clic)', () => {
  const start = PAIEMENT_DIALOG_SRC.indexOf('id="pay-montant"')
  const block = PAIEMENT_DIALOG_SRC.slice(start, start + 200)
  assert.match(block, /autoFocus/)
})

test('VX92 : le dialog paiement persiste le toggle "Créer un autre" en localStorage, défaut OFF', () => {
  assert.match(PAIEMENT_DIALOG_SRC, /PAY_CREER_UN_AUTRE_KEY = 'taqinor\.factureList\.paiement\.creerUnAutre'/)
  assert.match(PAIEMENT_DIALOG_SRC, /function lireCreerUnAutrePaiement\(\)/)
  assert.match(PAIEMENT_DIALOG_SRC, /window\.localStorage\.getItem\(PAY_CREER_UN_AUTRE_KEY\) === '1'/)
})

test('VX92 : paiement — ON garde le dialog ouvert (reset + refocus), OFF ferme (identique)', () => {
  const start = PAIEMENT_DIALOG_SRC.indexOf('const handleEnregistrerPaiement')
  const block = PAIEMENT_DIALOG_SRC.slice(start, start + 1200)
  assert.match(block, /if \(payCreerUnAutre\) \{/)
  assert.match(block, /payMontantRef\.current\?\.focus\(\)/)
  // VX230 — la fermeture passe désormais par onOpenChange(false) (le parent
  // possède la facture ciblée), plus par setPayTarget(null) local.
  assert.match(block, /\} else \{\s*onOpenChange\?\.\(false\)\s*\}/)
})

test('VX92 : ProduitForm — toggle persisté, OFF par défaut, jamais affiché en édition', () => {
  assert.match(PRODUIT_FORM_SRC, /CREER_UN_AUTRE_KEY = 'taqinor\.produitForm\.creerUnAutre'/)
  assert.match(PRODUIT_FORM_SRC, /useState\(\(\) => !isEdit && lireCreerUnAutre\(\)\)/)
  assert.match(PRODUIT_FORM_SRC, /\{!isEdit && \(/)
})

test('VX92 : ProduitForm — succès + toggle ON = reset formulaire + refocus nom (pas onClose)', () => {
  const start = PRODUIT_FORM_SRC.indexOf('onSaved?.()')
  // Fenêtre élargie (VX93 a inséré un commentaire + la ligne TVA « dernière
  // saisie » ; VX249(b) a ensuite inséré setTvaTouched(false) dans le même
  // bloc « créer un autre »).
  const block = PRODUIT_FORM_SRC.slice(start, start + 800)
  assert.match(block, /if \(!isEdit && creerUnAutre\) \{/)
  // VX93 — le reset ré-applique la dernière TVA saisie (spread de initialFields).
  assert.match(block, /setFields\(\{ \.\.\.initialFields/)
  assert.match(block, /nomRef\.current\?\.focus\(\)/)
  assert.match(block, /\} else \{\s*onClose\(\)\s*\}/)
})

test('VX92 : ClientForm — toggle persisté, OFF par défaut, jamais affiché en édition', () => {
  assert.match(CLIENT_FORM_SRC, /CREER_UN_AUTRE_KEY = 'taqinor\.clientForm\.creerUnAutre'/)
  assert.match(CLIENT_FORM_SRC, /useState\(\(\) => !isEdit && lireCreerUnAutre\(\)\)/)
})

test('VX92 : ClientForm — succès création + toggle ON = reset + refocus nom (pas onClose)', () => {
  const start = CLIENT_FORM_SRC.indexOf('await dispatch(createClient(payload))')
  const block = CLIENT_FORM_SRC.slice(start, start + 500)
  assert.match(block, /if \(creerUnAutre\) \{/)
  assert.match(block, /setFields\(initial\)/)
  assert.match(block, /nomRef\.current\?\.focus\(\)/)
  assert.match(block, /\} else \{\s*onClose\(\)\s*\}/)
})

test('VX92 : ClientForm — édition (isEdit) ferme toujours immédiatement (comportement OFF identique)', () => {
  const start = CLIENT_FORM_SRC.indexOf('if (isEdit) {')
  const block = CLIENT_FORM_SRC.slice(start, start + 200)
  assert.match(block, /toast\.success\('Client mis à jour\.'\)/)
  assert.match(block, /onClose\(\)/)
})
