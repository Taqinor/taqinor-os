// QJR658 — l'aller-retour Édition complète EXÉCUTÉ : pour un devis par marché,
// `etatVersEcritures(devisVersEtat(devis))` reproduit exactement les lignes
// stockées, chaque clé d'ENTRÉE d'`etude_params`, le prix cible et
// l'échéancier. Remplace `DevisGeneratorRoundTripEtude.test.mjs` (regex sur la
// source), qui avait laissé passer recommended_choice / recommended_option.
// Exécuté en CI : node --test src/features/ventes/quote/etatDevis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { devisVersEtat, etatVersEcritures } from './etatDevis.js'
import { consoAnnuelleDepuisFactures } from '../solar.js'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const ICI = dirname(fileURLToPath(import.meta.url))
// Les clés DÉCLARÉES au schéma serveur (`domain/etude_schema.py`) : toute clé
// que l'écran écrit doit y figurer, sinon la fusion la refuse en 400.
const SCHEMA_PY = readFileSync(join(ICI, '..', '..', '..', '..', '..',
  'backend', 'django_core', 'apps', 'ventes', 'domain', 'etude_schema.py'), 'utf8')
const CLES_SCHEMA = new Set(
  [...SCHEMA_PY.matchAll(/^ {4}'([a-z0-9_]+)': _cle\(/gm)].map(m => m[1]))

const ligne = (id, produit, designation, quantite, pu, taux, extra = {}) => ({
  id, produit, designation, quantite, prix_unitaire: pu, taux_tva: taux,
  remise: '0.00', ordre: id, type_ligne: 'produit', optionnelle: false,
  variante: '', prix_manuel: false, quantite_manuelle: false,
  groupe_index: null, groupe_label: '', role_devis: '', ...extra,
})

const FACTURES = [900, 850, 800, 700, 650, 900, 1200, 1300, 1000, 750, 700, 850]
const ECHEANCIER = [
  { libelle: 'Acompte', type: 'acompte', unite: 'montant', pct_or_montant: 20000 },
  { libelle: 'Livraison du matériel', type: 'materiel', unite: 'pct', pct_or_montant: 60 },
  { libelle: 'Solde', type: 'solde', unite: 'pct', pct_or_montant: 10 },
]

const base = (id, mode, etude, lignes, extra = {}) => ({
  id, reference: `DEV-202609-0${id}`, statut: 'envoye', lead: 77, client: 9,
  mode_installation: mode, taux_tva: '20.00', remise_globale: '5.00',
  date_validite: '2026-10-30', note: 'Pose sous quinze jours.',
  prix_cible_kwc: null, echeancier: [], etude_params: etude, lignes, ...extra,
})

const FIXTURES = {
  'résidentiel « Les deux », reco « Sans batterie »': base(1, 'residentiel', {
    scenario: 'Les deux (Sans + Avec)',
    recommended_option: 'Sans batterie',
    factures_mensuelles_reelles: FACTURES,
    conso_annuelle: consoAnnuelleDepuisFactures(FACTURES, 'onee'),
    distributeur: 'onee',
  }, [
    ligne(1, 12, 'Panneau Canadien Solar 550W', '10.00', '1090.91', '10.00'),
    ligne(2, 13, 'Onduleur réseau Huawei 5kW', '1.00', '12500.00', '20.00', { variante: 'sans' }),
    ligne(3, 14, 'Onduleur hybride Deye 5kW', '1.00', '14166.67', '20.00', { variante: 'avec' }),
    ligne(4, 15, 'Batterie Dyness 5 kWh', '1.00', '15000.00', '20.00', { variante: 'avec', prix_manuel: true }),
    { id: 5, ordre: 5, type_ligne: 'note', designation: 'Accès toiture par l’échelle', produit: null },
  ], { prix_cible_kwc: '6500.00', echeancier: ECHEANCIER }),

  'industriel MT': base(2, 'industriel', {
    scenario: 'Sans batterie',
    recommended_option: 'Sans batterie',
    conso_annuelle: 120000,
    distributeur: 'srm_casablanca',
    part_diurne_pct: 65,
    tension_raccordement: 'mt',
    repartition_mt: { pointe: 20, pleines: 50, creuses: 30 },
  }, [
    ligne(1, 21, 'Panneau Jinko 580W', '60.00', '1000.00', '10.00'),
    ligne(2, 22, 'Onduleur réseau Huawei 30kW Triphasé', '1.00', '45000.00', '20.00', { quantite_manuelle: true }),
  ]),

  'commercial hôtel': base(3, 'commercial', {
    scenario: 'Sans batterie',
    conso_annuelle: 90000,
    distributeur: 'onee',
    categorie_commerciale: 'hotel',
    chambres: 40,
    occupation_pct: 70,
    piscine: true,
  }, [
    ligne(1, 31, 'Panneau Jinko 580W', '40.00', '1000.00', '10.00', { remise: '5.00' }),
    ligne(2, 32, 'Onduleur réseau Huawei 20kW Triphasé', '1.00', '30000.00', '20.00'),
  ]),

  'agricole, pompe à courbe': base(4, 'agricole', {
    scenario: 'Sans batterie',
    // AGR130 — ENTRÉES v2 seules (forme du corps de l'aperçu, contrat
    // `etude_pompage_preview.json`) : jamais une dérivée (pompe_cv, m3_jour…).
    mode_pompe: 'neuve',
    plaque: null,
    besoin: {
      mode: 'volume_declare', volume_m3_jour: 135, debit_souhaite_m3h: 12,
      mois_pointe: 7, debit_actuel_m3h: null, heures_actuelles_jour: null,
      cultures: [{ crop: 'agrumes', surface_ha: 3, irrigation: 'goutte' }],
      region: 'souss-massa',
    },
    source: {
      debit_exploitation_m3h: 36, debit_exploitation_origine: 'foreur',
      debit_exploitation_date: '2026-09-15', debit_autorise_m3h: null,
      volume_annuel_autorise_m3: null, compteur: true, niveau_dynamique_m: null,
      diametre_tubage_mm: 150, profondeur_calage_m: 60, volume_reservoir_m3: null,
      niveau_statique_m: 40, rabattement_m: 8, profondeur_forage_m: 45,
    },
    hmt_entrees: {
      saisie_m: null, denivele_m: 4,
      conduite: { c_hazen_williams: null, materiau: 'pehd', diametre_interieur_mm: 100, longueur_m: 350 },
      pertes_singulieres_m: 0.8, pression_service_bar: 1,
    },
    type_pompe: 'immergee',
    alim: 'tri',
    localisation: { ville: 'Taroudant', lat: 30.47, lon: -8.88 },
    distance_champ_m: 30,
    options_cochees: ['afficheur_variateur', 'protection_dc'],
    taille: 'superieure',
    // AGR212 — l'énergie DÉCLARÉE vit dans saisies_economie_pompage.
    saisies_economie_pompage: {
      energie_actuelle: { valeur: 'diesel', provenance: { origine: 'saisie', detail: null, date: '2026-09-12' } },
      consommation: { quantite: 30, unite: 'litre', periode: 'semaine', jours_irrigation_par_semaine: null, saisi_le: '2026-09-12' },
      depense_unitaire_payee: { valeur: 11.5, saisi_le: '2026-09-12' },
      facture_reseau: null,
      mois_irrigation: { mois: [5, 6, 7], provenance: { origine: 'calculee', detail: 'calendrier_culture', date: '2026-09-12' } },
      entretien_paye_mad_an: null,
      coherence_confirmee: false,
      taux_actualisation: null,
      pret: null,
    },
  }, [
    ligne(1, 41, 'Pompe OSP 30-8 5.5kW', '1.00', '18000.00', '20.00'),
    ligne(2, 42, 'Panneau Jinko 580W', '14.00', '1000.00', '10.00'),
    ligne(3, 43, 'Variateur VEICHI SI23 7.5kW', '1.00', '9000.00', '20.00'),
  ]),

  'villas (groupes) + ×N': base(5, 'residentiel', {
    scenario: 'Sans batterie',
    recommended_option: 'Sans batterie',
    nombre_proprietes: 3,
  }, [
    ligne(1, 51, 'Panneau Canadien Solar 550W', '8.00', '1090.91', '10.00', { groupe_index: 1, groupe_label: 'Villa A' }),
    ligne(2, 52, 'Onduleur réseau Huawei 5kW', '1.00', '12500.00', '20.00', { groupe_index: 2, groupe_label: 'Villa B' }),
    ligne(3, 53, 'Coffret AC', '1.00', '900.00', '20.00', { groupe_index: 0 }),
  ]),
}

// Normalisation de forme (pas de valeur) : '8.00' et '8' disent la même chose.
const num = (v) => (v === null || v === undefined || v === '' ? null : Number(v))
const projeterLigne = (l) => (l.type_ligne && l.type_ligne !== 'produit'
  ? { type_ligne: l.type_ligne, designation: l.designation }
  : {
      produit: num(l.produit), designation: l.designation, quantite: num(l.quantite),
      prix_unitaire: num(l.prix_unitaire), remise: num(l.remise), taux_tva: num(l.taux_tva),
      optionnelle: !!l.optionnelle, variante: l.variante || '',
      prix_manuel: !!l.prix_manuel, quantite_manuelle: !!l.quantite_manuelle,
      role_devis: l.role_devis || '',
    })

for (const [nom, devis] of Object.entries(FIXTURES)) {
  test(`aller-retour exact — ${nom}`, () => {
    const etat = devisVersEtat(devis)
    const { lignes, entete, etude } = etatVersEcritures(etat)

    // Les lignes stockées, dans leur ordre.
    assert.deepEqual(lignes.map(projeterLigne), devis.lignes.map(projeterLigne))
    // Les groupes villa reviennent quand le devis en porte.
    if (devis.lignes.some(l => l.groupe_index != null)) {
      assert.equal(etat.multiMode, 'villas')
      assert.deepEqual(lignes.map(l => l.groupe_index ?? null),
        devis.lignes.map(l => l.groupe_index ?? null))
    }

    // Chaque clé d'ENTRÉE d'etude_params.
    for (const [cle, valeur] of Object.entries(devis.etude_params)) {
      if (cle === 'nombre_proprietes' && etat.multiMode === 'villas') continue
      assert.deepEqual(etude?.[cle], valeur, `etude_params.${cle}`)
    }

    // En-tête : prix cible, échéancier, remise, note, date.
    assert.equal(num(entete.prix_cible_kwc), num(devis.prix_cible_kwc))
    assert.equal(num(entete.remise_globale), num(devis.remise_globale))
    assert.equal(entete.note, devis.note)
    assert.equal(entete.date_validite, devis.date_validite)
    assert.equal(entete.mode_installation, devis.mode_installation)
    assert.equal('statut' in entete, false, 'jamais de statut dans l’en-tête')
    if (devis.echeancier.length) assert.deepEqual(entete.echeancier, devis.echeancier)
    else assert.equal('echeancier' in entete, false)
  })
}

test('l’option recommandée stockée revient telle quelle (jamais « Auto »)', () => {
  const etat = devisVersEtat(FIXTURES['résidentiel « Les deux », reco « Sans batterie »'])
  assert.equal(etat.recommendedChoice, 'Sans batterie')
  assert.equal(etat.scenario, 'Les deux (Sans + Avec)')
  assert.equal(etat.reouverture.panelW, '550')
})

test('la clé legacy recommended_choice est relue en repli', () => {
  const devis = base(9, 'residentiel', { recommended_choice: 'Avec batterie' }, [])
  assert.equal(devisVersEtat(devis).recommendedChoice, 'Avec batterie')
})

test('devisVersEtat marque `compose` les lignes produit relues sans verrou ni option', () => {
  const devis = base(10, 'residentiel', {}, [
    ligne(1, 5, 'Panneau', '10', '1000', '20'),
    ligne(2, 6, 'Onduleur', '1', '7500', '20', { prix_manuel: true }),
    ligne(3, 7, 'Borne', '1', '5000', '20', { optionnelle: true }),
  ])
  const { lignes } = devisVersEtat(devis)
  assert.deepEqual(lignes.map(l => l.compose), [true, false, false])
})

test('toute clé écrite par l’écran est DÉCLARÉE au schéma serveur', () => {
  assert.ok(CLES_SCHEMA.size >= 50, `schéma trop petit : ${CLES_SCHEMA.size}`)
  for (const devis of Object.values(FIXTURES)) {
    const { etude } = etatVersEcritures(devisVersEtat(devis), {
      etude: { conso_annuelle: 1, taux_autoconso: 1, taux_couverture: 1,
        payback: 1, injection_kwh_an: 1, injection_dh_an: 1, kwc: 1 },
    })
    for (const cle of Object.keys(etude || {})) {
      assert.ok(CLES_SCHEMA.has(cle), `clé « ${cle} » écrite mais absente du schéma`)
    }
  }
})

// ── AGR218 — enregistrer → rouvrir → enregistrer sans toucher : identique ──
test('AGR218 — ligne à 0 % + base légale + attestation : aller-retour exact et stable', () => {
  const corps = documentContrat('ventes', 'devis_replace_lines_entete').corps_agricole
  const devis = base(6, 'agricole', { ...corps.etude_params },
    corps.lignes.map((l, i) => ({ id: i + 1, ...l })))
  const premier = etatVersEcritures(devisVersEtat(devis))
  assert.deepEqual(premier.lignes.map(l => l.tva_base_legale),
    corps.lignes.map(l => l.tva_base_legale))
  assert.deepEqual(premier.etude.attestation_usage_agricole,
    corps.etude_params.attestation_usage_agricole)
  // Rouvrir ce qui vient d'être enregistré, ré-enregistrer sans toucher.
  const relu = {
    ...devis, etude_params: premier.etude,
    lignes: premier.lignes.map((l, i) => ({ id: i + 1, ...l })),
  }
  const second = etatVersEcritures(devisVersEtat(relu))
  assert.deepEqual(second.lignes, premier.lignes)
  assert.deepEqual(second.etude, premier.etude)
})

// ── AGR130 — rien de dérivé ne part du navigateur ; mode « existante » ────
const DERIVEES = ['pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h', 'm3_jour',
  'champ_kwc', 'heures_pompage', 'production', 'kit', 'conception', 'champ',
  'besoin_mensuel', 'alertes_pompage', 'provenance_pompage', 'pvgis_fige']

test('AGR130 — un devis agricole relu avec des dérivées serveur : aucune ne repart', () => {
  const devis = { ...FIXTURES['agricole, pompe à courbe'] }
  devis.etude_params = {
    ...devis.etude_params,
    pompe_cv: 10, pompe_kw: 7.5, hmt_m: 61.2, debit_hmt_m3h: 14, m3_jour: 98,
    champ_kwc: 9.94, heures_pompage: 7, production: { m3_jour_mois: [1] },
    kit: { inclus: [], options: [] }, conception: {}, champ: {},
    besoin_mensuel: [], alertes_pompage: [], provenance_pompage: {}, pvgis_fige: {},
  }
  const { etude } = etatVersEcritures(devisVersEtat(devis))
  for (const cle of DERIVEES) assert.equal(cle in etude, false, cle)
  assert.deepEqual(etude.besoin, FIXTURES['agricole, pompe à courbe'].etude_params.besoin)
})

test('AGR130 — pompe existante : plaque, HMT saisie, taille ; enregistrer → rouvrir → enregistrer', () => {
  const devis = base(7, 'agricole', {
    mode_pompe: 'existante',
    plaque: { kw: 5.5, tension_v: 380, phases: 'tri', cv: 7.5, courant_a: null },
    besoin: {
      mode: 'pompe_actuelle', volume_m3_jour: null, debit_souhaite_m3h: null,
      mois_pointe: null, debit_actuel_m3h: 10, heures_actuelles_jour: 6,
      cultures: [], region: null,
    },
    source: {
      debit_exploitation_m3h: null, debit_exploitation_origine: null,
      debit_exploitation_date: null, debit_autorise_m3h: null,
      volume_annuel_autorise_m3: null, compteur: false, niveau_dynamique_m: 50,
      diametre_tubage_mm: null, profondeur_calage_m: null, volume_reservoir_m3: null,
      niveau_statique_m: null, rabattement_m: null, profondeur_forage_m: null,
    },
    hmt_entrees: { saisie_m: 60, denivele_m: null, conduite: null,
      pertes_singulieres_m: null, pression_service_bar: null },
    type_pompe: 'immergee', alim: 'tri',
    localisation: { ville: null, lat: null, lon: null },
    distance_champ_m: null, options_cochees: [], taille: 'recommandee',
  }, [ligne(1, 41, 'Variateur VEICHI SI23 4kW', '1.00', '9000.00', '20.00')])
  const premier = etatVersEcritures(devisVersEtat(devis))
  assert.deepEqual(premier.etude.plaque, devis.etude_params.plaque)
  for (const [cle, valeur] of Object.entries(devis.etude_params)) {
    assert.deepEqual(premier.etude[cle], valeur, cle)
  }
  const relu = { ...devis, etude_params: premier.etude,
    lignes: premier.lignes.map((l, i) => ({ id: i + 1, ...l })) }
  const second = etatVersEcritures(devisVersEtat(relu))
  assert.deepEqual(second.etude, premier.etude)
  assert.deepEqual(second.lignes, premier.lignes)
})
