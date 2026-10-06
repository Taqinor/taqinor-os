// CIQ125 — le profil déclaré C&I : état d'écran ⇄ corps ⇄ entrées v2.
// Exécuté en CI : node --test src/features/ventes/quote/profilCi.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil, entreesCiV2,
  profilDepuisEtude, CLES_ENTREES_CI_V2, profilCiAncre,
} from './profilCi.js'
import { devisVersEtat, etatVersEcritures } from './etatDevis.js'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('ventes', 'etude_ci_preview')
const KWH = CONTRAT.corps.consommation.kwh_mensuels

const profilSaisi = () => {
  let p = profilCiVide()
  KWH.forEach((v, i) => { p = poserProfilCi(p, `kwhMensuels.${i}`, String(v)) })
  for (const i of [0, 1, 2, 3, 4]) p = poserProfilCi(p, `joursOuverts.${i}`, true)
  p = poserProfilCi(p, 'plages.ouvre.debut', '8')
  p = poserProfilCi(p, 'plages.ouvre.fin', '18,5')
  p = poserProfilCi(p, 'fermetures', [{ du: '2026-08-01', au: '2026-08-15', motif: 'congés' }])
  p = poserProfilCi(p, 'talonKw', '8')
  p = poserProfilCi(p, 'typePose', 'toit_plat_leste')
  p = poserProfilCi(p, 'surfaceUtile', '650')
  p = poserProfilCi(p, 'couverture', 'beton')
  p = poserProfilCi(p, 'tension', 'mt')
  p = poserProfilCi(p, 'phases', 'tri')
  p = poserProfilCi(p, 'puissanceSouscrite', '72.125')
  p = poserProfilCi(p, 'revente', true)
  return p
}

test('12 kWh saisis ⇒ le corps porte consommation.kwh_mensuels tels quels', () => {
  const corps = corpsCiDepuisProfil(profilSaisi(), { mode: 'industriel' })
  assert.deepEqual(corps.consommation.kwh_mensuels, KWH)
  assert.equal(corps.mode, 'industriel')
  // la forme est celle du contrat : mêmes clés de tête que l'échantillon
  assert.deepEqual(Object.keys(corps).sort(), Object.keys(CONTRAT.corps).sort())
  assert.deepEqual(corps.rythme.jours_ouverts, [true, true, true, true, true, false, false])
  assert.deepEqual(corps.rythme.plages, { ouvre: [[8, 18.5]] })
  assert.equal(corps.puissance_souscrite_kva, 72.125)
  assert.equal(corps.contraintes.revente_choisie, true)
})

test('aucun jour coché d’office, aucun défaut : profil vide ⇒ aucun appel', () => {
  assert.equal(corpsCiDepuisProfil(profilCiVide(), { mode: 'commercial' }), null)
  assert.equal(profilCiAncre(profilCiVide()), false)
  // avec un lead, le serveur résout ce qui manque : le corps part
  const avecLead = corpsCiDepuisProfil(profilCiVide(), { mode: 'commercial', lead: 12 })
  assert.equal(avecLead.lead, 12)
  assert.equal(avecLead.rythme.jours_ouverts, null)
  assert.equal(avecLead.consommation.kwh_mensuels, null)
})

test('la revente n’existe qu’en MT : repasser en BT la retire', () => {
  const p = poserProfilCi(profilSaisi(), 'tension', 'bt')
  assert.equal(p.revente, false)
  assert.equal(corpsCiDepuisProfil(p, { mode: 'commercial' }).contraintes.revente_choisie, false)
})

test('une taille explicite seule ancre le calcul', () => {
  const p = poserProfilCi(profilCiVide(), 'tailleExplicite', '55')
  assert.equal(profilCiAncre(p), true)
  assert.equal(corpsCiDepuisProfil(p, { mode: 'industriel' }).taille_explicite_kwc, 55)
})

test('entrées v2 : seules les clés `ecran` du contrat, jamais une dérivée', () => {
  const contrat = CONTRAT.cles_etude_params_ci_v2.entrees.map((e) => e.cle)
  assert.deepEqual([...CLES_ENTREES_CI_V2].sort(), [...contrat].sort())
  const e = entreesCiV2(profilSaisi(), { mode: 'commercial' })
  assert.deepEqual(Object.keys(e).sort(), [...contrat].sort())
  for (const derivee of ['etude_ci', 'production_figee', 'taux_autoconso', 'payback']) {
    assert.equal(derivee in e, false)
  }
})

test('enregistrer → rouvrir → enregistrer sans toucher = objet serveur identique', () => {
  for (const mode of ['industriel', 'commercial']) {
    const etat1 = {
      mode, lignes: [], tauxTva: '20.00', discountPct: '0', echeancier: null,
      profilCi: profilSaisi(), ctxCi: { mode, ville: 'Marrakech' },
    }
    const ecr1 = etatVersEcritures(etat1, { etude: null, entrees: {} })
    const devis = {
      id: 5, mode_installation: mode, taux_tva: '20.00', remise_globale: '0',
      lignes: [], etude_params: ecr1.etude,
    }
    const etat2 = devisVersEtat(devis)
    const ecr2 = etatVersEcritures(etat2, { etude: null, entrees: {} })
    for (const cle of CLES_ENTREES_CI_V2) {
      assert.deepEqual(ecr2.etude[cle], ecr1.etude[cle], `${mode} : ${cle}`)
    }
    assert.deepEqual(profilDepuisEtude(ecr2.etude), profilDepuisEtude(ecr1.etude))
  }
})

test('factures MAD et total annuel : aller-retour exact', () => {
  let p = poserProfilCi(profilCiVide(), 'saisieConso', 'factures')
  p = poserProfilCi(p, 'factures', [{ mois: '2026-01', montant_ttc: '4200,5', kwh: '' }])
  const e = entreesCiV2(p, { mode: 'commercial' })
  assert.deepEqual(e.consommation.factures_mad, [{ mois: '2026-01', montant_ttc: 4200.5, kwh: null }])
  assert.deepEqual(entreesCiV2(profilDepuisEtude(e), { mode: 'commercial' }), e)

  let a = poserProfilCi(profilCiVide(), 'saisieConso', 'annuel')
  a = poserProfilCi(a, 'kwhAnnuel', '150000.75')
  const ea = entreesCiV2(a, { mode: 'industriel' })
  assert.equal(ea.consommation.kwh_annuel, 150000.75)
  assert.deepEqual(entreesCiV2(profilDepuisEtude(ea), { mode: 'industriel' }), ea)
})
