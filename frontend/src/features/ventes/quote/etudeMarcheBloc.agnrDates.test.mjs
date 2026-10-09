// AGNR38 — chaque montant agricole déclaré est daté par SA saisie : corriger
// le prix le 08/10 date le prix du 08/10 et garde la date du 01/09 sur la
// quantité ; sans déclaration, aucune date n'est présentée comme saisie.
//
// Run : node --test src/features/ventes/quote/etudeMarcheBloc.agnrDates.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  saisiesEconomiePompage, ecoDepuisSaisies, aujourdhuiCasablanca, ECO_POMPAGE_VIDE,
} from './etudeMarcheBloc.js'

const DECLARE_01_09 = {
  ...ECO_POMPAGE_VIDE, energie: 'butane', quantite: '2', unite: 'bouteille', periode: 'mois',
  prix: '45', entretien: '1200',
}

test('AGNR38 — aller-retour : seule la donnée corrigée prend la date du jour', () => {
  // Déclaré et enregistré le 01/09.
  const stocke = saisiesEconomiePompage(DECLARE_01_09, { aujourdhui: '2026-09-01' })
  assert.equal(stocke.consommation.saisi_le, '2026-09-01')
  assert.equal(stocke.depense_unitaire_payee.saisi_le, '2026-09-01')
  // Rouvert le 08/10 : le prix passe à 52, rien d'autre ne bouge.
  const relu = ecoDepuisSaisies(stocke)
  const corrige = saisiesEconomiePompage({ ...relu, prix: '52' }, { aujourdhui: '2026-10-08' })
  assert.deepEqual(corrige.depense_unitaire_payee, { valeur: 52, saisi_le: '2026-10-08' })
  assert.equal(corrige.consommation.saisi_le, '2026-09-01')
  assert.equal(corrige.entretien_paye_mad_an.saisi_le, '2026-09-01')
  assert.equal(corrige.energie_actuelle.provenance.date, '2026-09-01')
})

test('AGNR38 — ré-enregistrer sans toucher garde toutes les dates', () => {
  const stocke = saisiesEconomiePompage(DECLARE_01_09, { aujourdhui: '2026-09-01' })
  const relu = ecoDepuisSaisies(stocke)
  assert.deepEqual(saisiesEconomiePompage(relu, { aujourdhui: '2026-10-08' }), stocke)
})

test('AGNR38 — le champ date ne présente jamais « aujourd’hui » comme une saisie', () => {
  const stocke = saisiesEconomiePompage(DECLARE_01_09, { aujourdhui: '2026-09-01' })
  assert.equal(ecoDepuisSaisies(stocke).dateDeclaration, '')
  assert.equal(ecoDepuisSaisies(null).dateDeclaration, '')
  // Rien de déclaré ⇒ aucune saisie (donc aucune date).
  assert.equal(saisiesEconomiePompage({ ...ECO_POMPAGE_VIDE }, { aujourdhui: '2026-10-08' }), null)
})

test('AGNR38 — la date du jour est celle de Casablanca', () => {
  // 23 h 30 UTC le 07/10 = 00 h 30 le 08/10 à Casablanca (UTC+1). Comme
  // lib/dateLocale.test.mjs (ADEV73) : le décalage suit la base tz du runtime
  // (celle du runner CI donne GMT+00:00 pour cette date), jamais une constante.
  const t = new Date('2026-10-07T23:30:00Z')
  const off = new Intl.DateTimeFormat('en', { timeZone: 'Africa/Casablanca', timeZoneName: 'longOffset' })
    .formatToParts(t).find((p) => p.type === 'timeZoneName').value
  assert.equal(aujourdhuiCasablanca(t), off === 'GMT+01:00' ? '2026-10-08' : '2026-10-07')
  // Midi UTC : même date partout, quelle que soit la base tz.
  assert.equal(aujourdhuiCasablanca(new Date('2026-10-08T12:00:00Z')), '2026-10-08')
})
