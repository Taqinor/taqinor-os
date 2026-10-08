// AGNR8 — `etatVersEcritures` normalise les nombres d'en-tête avant l'envoi :
// aucune saisie numérique n'atteint plus un 400 « plus de 2 chiffres » ou
// « nombre valide requis » de `DevisWriteSerializer`
// (`remise_globale` / `taux_tva` / `prix_cible_kwc` : DecimalField à 2
// décimales).
import test from 'node:test'
import assert from 'node:assert/strict'

import { etatVersEcritures, normaliserNombreEntete } from './etatDevis.js'

const etat = (extra) => ({ mode: 'residentiel', lignes: [], ...extra })

test('AGNR8 — 12,345 % / TVA vide / 1234,567 ⇒ en-tête accepté par le serveur', () => {
  const { entete, normalisations } = etatVersEcritures(etat({
    discountPct: '12.345', tauxTva: '', prixCible: '1234.567',
  }))
  assert.equal(entete.remise_globale, '12.35')
  assert.equal('taux_tva' in entete, false, 'TVA vide ⇒ clé omise')
  assert.equal(entete.prix_cible_kwc, '1234.57')
  assert.deepEqual(normalisations, [
    { champ: 'remise_globale', tape: '12.345', envoye: '12.35' },
    { champ: 'prix_cible_kwc', tape: '1234.567', envoye: '1234.57' },
  ])
})

test('AGNR8 — chaque nombre envoyé a au plus 2 décimales', () => {
  const { entete } = etatVersEcritures(etat({ discountPct: '7,125', tauxTva: '19.995', prixCible: '' }))
  for (const cle of ['remise_globale', 'taux_tva']) {
    assert.match(entete[cle], /^-?\d+\.\d{2}$/, cle)
  }
  assert.equal(entete.remise_globale, '7.13')
  assert.equal(entete.taux_tva, '20.00')
  assert.equal(entete.prix_cible_kwc, null)
})

test('AGNR8 — une valeur déjà propre ne produit aucune normalisation', () => {
  const { entete, normalisations } = etatVersEcritures(etat({
    discountPct: '5.00', tauxTva: '20', prixCible: '1500',
  }))
  assert.equal(entete.remise_globale, '5.00')
  assert.equal(entete.taux_tva, '20.00')
  assert.equal(entete.prix_cible_kwc, '1500.00')
  assert.deepEqual(normalisations, [])
})

test('AGNR8 — arrondi au demi supérieur calculé sur le texte (pas d’erreur binaire)', () => {
  assert.equal(normaliserNombreEntete('1.005').envoye, '1.01')
  assert.equal(normaliserNombreEntete('12.344').envoye, '12.34')
  assert.equal(normaliserNombreEntete('0.5').envoye, '0.50')
  assert.equal(normaliserNombreEntete(' 3 ').envoye, '3.00')
})

test('AGNR8 — une saisie illisible n’est jamais envoyée, elle est signalée', () => {
  const { entete, normalisations } = etatVersEcritures(etat({ discountPct: 'abc', tauxTva: '20' }))
  assert.equal(entete.remise_globale, '0')
  assert.deepEqual(normalisations, [{ champ: 'remise_globale', tape: 'abc', envoye: '0' }])
})
