// CJ2b — fonctions pures de etudeHorairePreview.js (construction du corps de
// requête + aides d'affichage honnêtes). Run : node --test
// src/features/ventes/etudeHorairePreview.test.mjs
// Importe le module PUR (aucun import react/axios) : la chaîne du hook lit
// `import.meta.env` au chargement et ne s'importe pas hors de Vite.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  verdictBatteriePourTaille,
} from './etudeHorairePreviewPur.js'

test('construireCorpsPreview : null hors résidentiel, même avec facture', () => {
  assert.equal(construireCorpsPreview({
    modeInstallation: 'industriel', fHiver: '1200',
  }), null)
})

test('construireCorpsPreview : null sans rien pour ancrer un calcul (ni facture, ni devis)', () => {
  assert.equal(construireCorpsPreview({
    modeInstallation: 'residentiel', editId: null, fHiver: '', kwp: 6,
  }), null)
  assert.equal(construireCorpsPreview({
    modeInstallation: 'residentiel', editId: '', fHiver: '0',
  }), null)
})

test('construireCorpsPreview : une facture hiver suffit à ancrer, dimensionner toujours demandé', () => {
  const corps = construireCorpsPreview({
    modeInstallation: 'residentiel', fHiver: '1200', kwp: 6,
  })
  assert.equal(corps.facture_hiver, 1200)
  assert.equal(corps.dimensionner, true)
  assert.equal(corps.kwc, 6)
  assert.equal('devis' in corps, false)
})

test('construireCorpsPreview : un devis existant (édition) suffit aussi, sans aucune facture tapée', () => {
  const corps = construireCorpsPreview({
    modeInstallation: 'residentiel', editId: 42,
  })
  assert.equal(corps.devis, 42)
  assert.equal('facture_hiver' in corps, false)
})

test('construireCorpsPreview : facture été distincte transmise seulement si réellement différente', () => {
  const avecEte = construireCorpsPreview({
    modeInstallation: 'residentiel', fHiver: '1200', fEte: '1600', eteDifferente: true,
  })
  assert.equal(avecEte.facture_ete, 1600)
  assert.equal(avecEte.ete_differente, true)

  const sansEte = construireCorpsPreview({
    modeInstallation: 'residentiel', fHiver: '1200', fEte: '', eteDifferente: false,
  })
  assert.equal('facture_ete' in sansEte, false)
  assert.equal('ete_differente' in sansEte, false)
})

test('construireCorpsPreview : batterie/ville/raccordement omis quand absents, jamais une valeur fabriquée', () => {
  const corps = construireCorpsPreview({ modeInstallation: 'residentiel', fHiver: '1200' })
  assert.equal('batterie_kwh' in corps, false)
  assert.equal('ville' in corps, false)
  assert.equal('raccordement' in corps, false)
  assert.equal('occupation' in corps, false)
  assert.equal('equipements' in corps, false)

  const complet = construireCorpsPreview({
    modeInstallation: 'residentiel', fHiver: '1200', ville: 'Casablanca',
    raccordement: 'monophase', batterieKwh: 10, occupation: 'presence_jour',
    equipements: { clim: true },
  })
  assert.equal(complet.ville, 'Casablanca')
  assert.equal(complet.raccordement, 'monophase')
  assert.equal(complet.batterie_kwh, 10)
  assert.equal(complet.occupation, 'presence_jour')
  assert.deepEqual(complet.equipements, { clim: true })
})

test('etiquetteSource : facture_hiver est une ESTIMATION (une facture répétée sur 12 mois)', () => {
  const { estimation, libelle } = etiquetteSource('facture_hiver')
  assert.equal(estimation, true)
  assert.match(libelle, /[Ee]stimation/)
})

test('etiquetteSource : facture_hiver_ete est aussi une estimation (deux factures répétées)', () => {
  assert.equal(etiquetteSource('facture_hiver_ete').estimation, true)
})

test('etiquetteSource : factures_mensuelles_reelles n\'est PAS une estimation (vraie variation réelle)', () => {
  const { estimation, libelle } = etiquetteSource('factures_mensuelles_reelles')
  assert.equal(estimation, false)
  assert.doesNotMatch(libelle, /[Ee]stimation/)
})

test('etiquetteSource : kwh_mensuels_saisis n\'est pas une estimation', () => {
  assert.equal(etiquetteSource('kwh_mensuels_saisis').estimation, false)
})

test('etiquetteSource : source inconnue/absente ne casse jamais, libellé de repli FR', () => {
  assert.equal(typeof etiquetteSource('absente').libelle, 'string')
  assert.equal(typeof etiquetteSource(undefined).libelle, 'string')
})

const LIGNE_BATTERIE_INDISPONIBLE = {
  panneaux: 8, kwc: 5.68, batterie_disponible: false,
  economie_sans_mad: 8471.2, economie_avec_mad: null,
  cout_avec_ttc: null, payback_avec_annees: null,
  couverture_avec: null, taux_autoconso_avec: null,
  // Fixture SYNTHÉTIQUE — les chiffres n'ont plus (depuis le 24/08/2026) de
  // pendant réel au catalogue (le couple panneau 710 Wc / hybride 5 kW mono
  // qui inspirait ces valeurs a été rendu compatible, cf. CJ2b-historique
  // dans etudeHorairePreviewPur.js) ; seul le motif "Isc ... A > ... A"
  // exercé par le test ci-dessous compte ici, pas un fait catalogue.
  verdicts_bloquants_avec: ['Isc 30,0 A > 25,0 A — panneau fixture incompatible avec cet onduleur hybride.'],
}

const LIGNE_BATTERIE_DISPONIBLE = {
  panneaux: 10, kwc: 7.1, batterie_disponible: true,
  economie_sans_mad: 9000, economie_avec_mad: 13000,
  cout_avec_ttc: 90000, payback_avec_annees: 6.9,
  couverture_avec: 0.8, taux_autoconso_avec: 0.65,
  verdicts_bloquants_avec: [],
}

test('lignesAffichables : batterie_disponible=false -> batterieVendable=false, raison FR, aucun chiffre _avec', () => {
  const [ligne] = lignesAffichables({ tableau: [LIGNE_BATTERIE_INDISPONIBLE] })
  assert.equal(ligne.batterieVendable, false)
  assert.match(ligne.raisonBatterie, /Isc/)
  assert.equal(ligne.economie_avec_mad, null)
  assert.equal(ligne.cout_avec_ttc, null)
  assert.equal(ligne.payback_avec_annees, null)
  assert.equal(ligne.couverture_avec, null)
  assert.equal(ligne.taux_autoconso_avec, null)
  // Le sans-batterie, lui, reste un vrai chiffre — jamais effacé par erreur.
  assert.equal(ligne.economie_sans_mad, 8471.2)
})

test('lignesAffichables : défense en profondeur — un chiffre _avec renvoyé malgré batterie_disponible=false est quand même effacé', () => {
  const pollué = { ...LIGNE_BATTERIE_INDISPONIBLE, economie_avec_mad: 999999 }
  const [ligne] = lignesAffichables({ tableau: [pollué] })
  assert.equal(ligne.economie_avec_mad, null)
})

test('lignesAffichables : batterie_disponible=true -> batterieVendable=true, raison vide, chiffres _avec préservés', () => {
  const [ligne] = lignesAffichables({ tableau: [LIGNE_BATTERIE_DISPONIBLE] })
  assert.equal(ligne.batterieVendable, true)
  assert.equal(ligne.raisonBatterie, '')
  assert.equal(ligne.economie_avec_mad, 13000)
  assert.equal(ligne.payback_avec_annees, 6.9)
})

test('lignesAffichables : dimensionnement absent/nul -> tableau vide, jamais une exception', () => {
  assert.deepEqual(lignesAffichables(null), [])
  assert.deepEqual(lignesAffichables(undefined), [])
  assert.deepEqual(lignesAffichables({}), [])
})

// ── CJ2b — le verdict batterie DE LA TAILLE CHIFFRÉE ────────────────────────
// Les cartes de comparaison en haut de l'écran chiffrent UNE taille : c'est le
// verdict de CETTE taille qu'elles doivent appliquer, pas celui du tableau en
// général. Sans cela, l'écran promet l'économie d'une installation que le
// catalogue ne peut pas livrer (trou réel exhumé par CJ2a).

const LIGNES_VERDICT = lignesAffichables({
  tableau: [
    { ...LIGNE_BATTERIE_DISPONIBLE, kwc: 4.26, panneaux: 6 },
    { ...LIGNE_BATTERIE_INDISPONIBLE, kwc: 5.68, panneaux: 8 },
  ],
})

test('verdictBatteriePourTaille : rend le verdict de la taille la plus proche', () => {
  const v = verdictBatteriePourTaille(LIGNES_VERDICT, 5.68)
  assert.equal(v.vendable, false)
  assert.equal(v.kwc, 5.68)
  assert.ok(v.raison.length > 0, 'la raison FR doit être portée')
})

test('verdictBatteriePourTaille : une autre taille peut être vendable', () => {
  assert.equal(verdictBatteriePourTaille(LIGNES_VERDICT, 4.26).vendable, true)
})

test('verdictBatteriePourTaille : tolérance — une puissance tapée proche retrouve son palier', () => {
  assert.equal(verdictBatteriePourTaille(LIGNES_VERDICT, 5.5).vendable, false)
})

test('verdictBatteriePourTaille : null quand le moteur ne dit rien sur cette taille', () => {
  // Trop loin de tout palier : on n'invente aucun verdict, ni dans un sens ni
  // dans l'autre — l'écran garde alors son comportement d'avant.
  assert.equal(verdictBatteriePourTaille(LIGNES_VERDICT, 30), null)
  assert.equal(verdictBatteriePourTaille([], 5.68), null)
  assert.equal(verdictBatteriePourTaille(null, 5.68), null)
  assert.equal(verdictBatteriePourTaille(LIGNES_VERDICT, 0), null)
})
