// VNT44 (Groupe VNT, D-VNT-3) — helpers PURS de l'écran « vente » : les gestes
// ne se déduisent que de `vente.peut` (dit par le serveur), la tête d'une
// chaîne de versions se lit sur `vente.tete_id` puis `superseded_by`, et les
// erreurs serveur (champ, liste d'objets, code) deviennent des erreurs NOMMÉES
// sous le champ + un bandeau « Corrigez : … » (règle « erreurs → le champ
// fautif »). Exemples lus dans le CONTRAT committé, jamais écrits à la main.
import test from 'node:test'
import assert from 'node:assert/strict'
import { exempleContrat, documentContrat } from '../../../test/fixtures/contractSamples.js'
import { peutFacturerAcompte, teteDeVersion } from './venteEtat.js'
import { aplatirErreurs, erreursParChamp, bandeau } from './erreursVente.js'

const etat = (variante) => exempleContrat('ventes', 'vente_etat', variante)

test('peutFacturerAcompte : lu sur vente.peut, jamais un repli', () => {
  assert.equal(peutFacturerAcompte(etat('exemple')), true)
  assert.equal(peutFacturerAcompte(etat('exemple_acompte_brouillon')), false)
  assert.equal(peutFacturerAcompte(etat('exemple_version_remplacee')), false)
  assert.equal(peutFacturerAcompte(etat('exemple_revision_en_cours')), false)
  // absent / ancien serveur : faux, JAMAIS le repli « libre »
  assert.equal(peutFacturerAcompte({}), false)
  assert.equal(peutFacturerAcompte({ vente: {} }), false)
  assert.equal(peutFacturerAcompte(null), false)
  assert.equal(peutFacturerAcompte({ vente: { peut: { facturer_acompte: 'libre' } } }), false)
})

test("teteDeVersion : vente.tete_id d'abord, sinon superseded_by", () => {
  const v1 = { id: 501, superseded_by: 502 }
  const v2 = { id: 502, superseded_by: null }
  assert.equal(teteDeVersion([v1, v2], 501), 502)
  assert.equal(teteDeVersion([v1, v2], 502), 502)
  // le serveur a parlé : tete_id l'emporte
  const avecVente = { id: 501, superseded_by: 502, vente: { tete_id: 600 } }
  assert.equal(teteDeVersion([avecVente, v2], 501), 600)
  // chaîne de 3 et cycle défensif
  const a = { id: 1, superseded_by: 2 }
  const b = { id: 2, superseded_by: 3 }
  const c = { id: 3, superseded_by: null }
  assert.equal(teteDeVersion([a, b, c], 1), 3)
  assert.equal(teteDeVersion([{ id: 1, superseded_by: 2 }, { id: 2, superseded_by: 1 }], 1), null)
  assert.equal(teteDeVersion([a], 99), null)
  assert.equal(teteDeVersion(undefined, 1), null)
})

test("aplatirErreurs : champ plat, liste d'objets", () => {
  const liste = aplatirErreurs({
    montant_ttc: ['Montant invalide.'],
    pourcentage: 'Pourcentage trop grand.',
    paiements: [{ date_paiement: ['Date requise.'] }, {}, { montant: ['Montant requis.'], reference: ['Trop long.'] }],
  })
  assert.deepEqual(liste.map((e) => e.cle), [
    'montant_ttc', 'pourcentage', 'paiements.0.date_paiement',
    'paiements.2.montant', 'paiements.2.reference',
  ])
  assert.equal(liste[0].libelle, 'Montant')
  assert.equal(liste[2].libelle, 'Paiement 1 — date')
  assert.equal(liste[3].libelle, 'Paiement 3 — montant')
  assert.equal(liste[2].message, 'Date requise.')
  const parChamp = erreursParChamp(liste)
  assert.equal(parChamp['paiements.0.date_paiement'], 'Date requise.')
  assert.equal(parChamp.montant_ttc, 'Montant invalide.')
})

test('aplatirErreurs : codes de devis_facturer.json (detail seul => erreur générale portant son code)', () => {
  const doc = documentContrat('ventes', 'devis_facturer')
  const d400 = doc.erreurs_400.montant_depasse_reste
  const liste = aplatirErreurs(d400)
  assert.equal(liste.length, 1)
  assert.equal(liste[0].cle, 'submit')
  assert.equal(liste[0].code, 'montant_depasse_reste')
  assert.equal(liste[0].message, d400.detail)
  const d409 = doc.erreurs_409.version_remplacee
  const l409 = aplatirErreurs(d409)
  assert.equal(l409[0].code, 'version_remplacee')
  assert.deepEqual(l409[0].successeur, d409.successeur)
  const brouillons = doc.erreurs_409.brouillons_a_remplacer
  assert.deepEqual(aplatirErreurs(brouillons)[0].brouillons, brouillons.brouillons)
  // rien d'exploitable : repli explicite, jamais silencieux
  assert.equal(aplatirErreurs(null)[0].message, 'Une erreur est survenue.')
  assert.equal(aplatirErreurs('boom')[0].message, 'boom')
})

test('bandeau : « Corrigez : … » nomme les champs, sinon le message général', () => {
  const liste = aplatirErreurs({
    montant_ttc: ['x'], paiements: [{ date_paiement: ['y'] }],
  })
  assert.equal(bandeau(liste), 'Corrigez : Montant, Paiement 1 — date')
  const doc = documentContrat('ventes', 'devis_facturer')
  assert.equal(
    bandeau(aplatirErreurs(doc.erreurs_403.credit_hold)),
    doc.erreurs_403.credit_hold.detail,
  )
  assert.equal(bandeau([]), '')
})
