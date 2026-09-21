// XSTK5 — Tests purs (node, sans DOM) de la logique des 3 flux scan-first.
// Exécuté en CI : node --test src/features/magasin/scan/scanFlows.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  SCAN_MODES,
  matchLigneByProduitId,
  matchPickListLine,
  matchComptageLine,
  matchBcfLigne,
  nextReceptionQuantite,
  nextPickingState,
  nextComptageQuantite,
  rejectedScan,
  acceptedScan,
  scanModeOptions,
} from './scanFlows.js'

test('matchLigneByProduitId retrouve la ligne par id produit (coercition string→number)', () => {
  const lignes = [{ id: 1, produit: 10 }, { id: 2, produit: 20 }]
  assert.equal(matchLigneByProduitId('20', lignes), lignes[1])
  assert.equal(matchLigneByProduitId(10, lignes), lignes[0])
})

test('matchLigneByProduitId renvoie null pour un scan HORS-LISTE (jamais une ligne au hasard)', () => {
  const lignes = [{ id: 1, produit: 10 }]
  assert.equal(matchLigneByProduitId(999, lignes), null)
  assert.equal(matchLigneByProduitId(undefined, lignes), null)
  assert.equal(matchLigneByProduitId('abc', lignes), null)
})

test('les 3 alias métier délèguent au même matcher (picking/comptage/réception)', () => {
  const lignes = [{ id: 1, produit: 5 }]
  assert.equal(matchPickListLine(5, lignes), lignes[0])
  assert.equal(matchComptageLine(5, lignes), lignes[0])
  assert.equal(matchBcfLigne(5, lignes), lignes[0])
  assert.equal(matchPickListLine(7, lignes), null)
})

test('rejectedScan/acceptedScan forment un résultat stable (pas d\'exception)', () => {
  const rej = rejectedScan('CODE123')
  assert.equal(rej.ok, false)
  assert.equal(rej.code, 'CODE123')
  assert.equal(rej.reason, 'hors-liste')

  const acc = acceptedScan({ id: 1 })
  assert.equal(acc.ok, true)
  assert.deepEqual(acc.ligne, { id: 1 })
})

test('scanModeOptions expose les 2 valeurs stables pour le Segmented', () => {
  const opts = scanModeOptions()
  assert.deepEqual(opts.map((o) => o.value), [SCAN_MODES.PAR_UNITE, SCAN_MODES.SAISIE_QUANTITE])
})

// ── RÉCEPTION ────────────────────────────────────────────────────────────

test('réception scan-par-unité : +1 par scan, plafonné au reste dû', () => {
  const ligne = { quantite: 10, quantite_recue: 9 }
  assert.equal(nextReceptionQuantite(ligne, { mode: SCAN_MODES.PAR_UNITE }), 1)
  const complete = { quantite: 10, quantite_recue: 10 }
  assert.equal(nextReceptionQuantite(complete, { mode: SCAN_MODES.PAR_UNITE }), 0)
})

test('réception saisie-quantité : utilise la valeur tapée, plafonnée au reste dû', () => {
  const ligne = { quantite: 10, quantite_recue: 3 }
  assert.equal(
    nextReceptionQuantite(ligne, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '4' }), 4)
  // Sur-saisie (12 > reste dû 7) → plafonnée à 7, jamais plus que commandé.
  assert.equal(
    nextReceptionQuantite(ligne, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '12' }), 7)
  // Saisie invalide/vide → 0 (rien à envoyer).
  assert.equal(
    nextReceptionQuantite(ligne, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '' }), 0)
})

// ── PICKING ──────────────────────────────────────────────────────────────

test('picking scan-par-unité incrémente de 1, coche `preleve` à quantité atteinte', () => {
  const ligne = { quantite_demandee: 3, quantite_prelevee: 2 }
  const res = nextPickingState(ligne, { mode: SCAN_MODES.PAR_UNITE })
  assert.equal(res.quantite_prelevee, 3)
  assert.equal(res.preleve, true)
})

test('picking scan-par-unité ne dépasse jamais la quantité demandée', () => {
  const ligne = { quantite_demandee: 2, quantite_prelevee: 2 }
  const res = nextPickingState(ligne, { mode: SCAN_MODES.PAR_UNITE })
  assert.equal(res.quantite_prelevee, 2)
  assert.equal(res.preleve, true)
})

test('picking saisie-quantité utilise la valeur tapée, plafonnée à la demande', () => {
  const ligne = { quantite_demandee: 5, quantite_prelevee: 1 }
  const res = nextPickingState(ligne, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '3' })
  assert.equal(res.quantite_prelevee, 3)
  assert.equal(res.preleve, false)
  const over = nextPickingState(ligne, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '99' })
  assert.equal(over.quantite_prelevee, 5)
  assert.equal(over.preleve, true)
})

// ── COMPTAGE ─────────────────────────────────────────────────────────────

test('comptage scan-par-unité incrémente depuis la valeur déjà comptée (0 si jamais comptée)', () => {
  assert.equal(
    nextComptageQuantite({ quantite_comptee: null }, { mode: SCAN_MODES.PAR_UNITE }), 1)
  assert.equal(
    nextComptageQuantite({ quantite_comptee: 4 }, { mode: SCAN_MODES.PAR_UNITE }), 5)
})

test('comptage saisie-quantité remplace le compte par la valeur tapée', () => {
  assert.equal(
    nextComptageQuantite(
      { quantite_comptee: 4 }, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: '7' }), 7)
  // Saisie invalide → conserve le compte actuel (ne casse jamais la valeur).
  assert.equal(
    nextComptageQuantite(
      { quantite_comptee: 4 }, { mode: SCAN_MODES.SAISIE_QUANTITE, saisie: 'x' }), 4)
})
