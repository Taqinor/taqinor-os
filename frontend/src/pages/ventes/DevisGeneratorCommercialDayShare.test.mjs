// CIQ126 (remplace QJR575) — un devis commercial rouvert dans l'Édition
// complète puis enregistré SANS retouche renvoie EXACTEMENT ses entrées : plus
// aucune part diurne de catégorie, plus aucune clé de
// l'étude locale (taux_autoconso, payback, part_diurne_pct). La sentinelle
// « Non précisée » se persiste `null` et n'est jamais envoyée au moteur.
// Exécuté : la projection partagée + l'aller-retour du module pur etatDevis.
// Run : node --test src/pages/ventes/DevisGeneratorCommercialDayShare.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { projeterEtudeMarche } from '../../features/ventes/quote/etudeMarcheBloc.js'
import { devisVersEtat, etatVersEcritures } from '../../features/ventes/quote/etatDevis.js'
import { entreesCiV2, profilCiVide, poserProfilCi } from '../../features/ventes/quote/profilCi.js'

const profil = poserProfilCi(poserProfilCi(profilCiVide(), 'saisieConso', 'annuel'), 'kwhAnnuel', '96000')

test('sans catégorie : aucune part diurne ni dérivée locale, catégorie persistée null', () => {
  const bloc = projeterEtudeMarche('commercial', {
    choix: {}, entrees: {}, categorie: null,
    ciEntrees: entreesCiV2(profil, { mode: 'commercial', categorie: null }),
  })
  for (const k of ['taux_autoconso', 'taux_couverture', 'payback', 'part_diurne_pct']) {
    assert.equal(k in bloc, false, k)
  }
  assert.equal(bloc.categorie_commerciale, null)
  assert.equal(bloc.rythme.categorie_commerciale, null)
  assert.equal(bloc.consommation.kwh_annuel, 96000)
})

test('rouvrir sans categorie_commerciale puis enregistrer : étude identique', () => {
  const ecr1 = etatVersEcritures({
    mode: 'commercial', lignes: [], tauxTva: '20.00', discountPct: '0', echeancier: null,
    categorieCommerciale: null, commercialAnswers: {}, profilCi: profil,
  }, { entrees: {} })
  const devis = {
    id: 7, mode_installation: 'commercial', taux_tva: '20.00', remise_globale: '0',
    lignes: [], etude_params: ecr1.etude,
  }
  const ecr2 = etatVersEcritures(devisVersEtat(devis), { entrees: {} })
  assert.deepEqual(ecr2.etude, ecr1.etude)
})
