// AGNR51 / AGNR60 — acompte personnalisé absorbé par la dernière tranche ; aller-retour sans perte.
// Exécuté en CI : node --test src/features/ventes/echeancierEdition.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  echeancierAvecAcompte, erreurEcheancier, echeancierVersSaisie, saisieVersEcheancier,
} from './echeancierEdition.js'

const INDUSTRIEL = [
  { type: 'commande', libelle: 'Commande', unite: 'pct', pct_or_montant: 30, jalon: 'commande' },
  { type: 'materiel', libelle: 'Livraison', unite: 'pct', pct_or_montant: 40, jalon: 'livraison_materiel' },
  { type: 'materiel', libelle: 'Mise en service', unite: 'pct', pct_or_montant: 20, jalon: 'mise_en_service' },
  { type: 'solde', libelle: 'Réception', unite: 'pct', pct_or_montant: 10, jalon: 'reception_definitive' },
]

test('acompte_personnalise_quatre_jalons', () => {
  const r = echeancierAvecAcompte(INDUSTRIEL, '6000', 17000, 'industriel', null)
  assert.deepEqual(r.map(t => [t.unite, t.pct_or_montant]),[
    ['montant', 6000], ['pct', 40], ['pct', 20], ['montant', 800],
  ])
})

test('acompte trop grand : aucune tranche inventée, l\'erreur est nommée', () => {
  const r = echeancierAvecAcompte(INDUSTRIEL, '8500', 17000, 'industriel', null)
  assert.equal(r[3].unite, 'pct'); assert.equal(r[3].pct_or_montant, 10)
  assert.match(erreurEcheancier(echeancierVersSaisie(r), 17000), /Total des tranches/)
})

test('TTC inconnu : aucune conversion inventée', () => {
  const r = echeancierAvecAcompte(INDUSTRIEL, '6000', 0, 'industriel', null)
  assert.equal(r[3].unite, 'pct'); assert.equal(r[3].pct_or_montant, 10)
})

test('3 tranches : le matériel absorbe toujours l\'écart', () => {
  const trois = [
    { type: 'commande', libelle: 'Acompte', unite: 'pct', pct_or_montant: 20 },
    { type: 'materiel', libelle: 'Matériel', unite: 'pct', pct_or_montant: 70 },
    { type: 'solde', libelle: 'Solde', unite: 'pct', pct_or_montant: 10 },
  ]
  const r = echeancierAvecAcompte(trois, '20000', 100000, 'residentiel', null)
  assert.deepEqual(r.map(t => [t.unite, t.pct_or_montant]),[['montant', 20000], ['pct', 70], ['pct', 10]])
})
