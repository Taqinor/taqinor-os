// QJR542 — la projection « étude du marché → clés etude_params légales »
// vit dans UNE fonction pure partagée (générateur + devis automatique).
// Run : node --test src/features/ventes/quote/etudeMarcheBloc.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  projeterEtudeMarche, saisiesEconomiePompage, ecoDepuisSaisies, ECO_POMPAGE_VIDE,
  lignesDepuisKit,
  attestationUsageAgricole, attestationDepuisEtude,
} from './etudeMarcheBloc.js'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

// Liste ECRAN figée depuis apps/ventes/domain/etude_schema.py (SCHEMA, clés de
// propriétaire ECRAN, :94-260). Toute clé hors de cette liste est refusée en
// 400 par la fusion etude-params / la création atomique.
const ECRAN = new Set([
  'scenario', 'recommended_option', 'part_diurne_pct', 'gamme', 'mode_installation',
  'tension_raccordement', 'distributeur', 'categorie_commerciale', 'origine',
  'nombre_proprietes', 'factures_mensuelles_reelles', 'conso_kwh_mensuelles',
  'conso_annuelle', 'toiture', 'attribution',
  // AGR130 — les ENTRÉES v2 du pompage (AGR122) ; plus aucune clé v1.
  'mode_pompe', 'plaque', 'besoin', 'source', 'hmt_entrees', 'type_pompe', 'alim',
  'localisation', 'distance_champ_m', 'options_cochees', 'taille',
  'saisies_economie_pompage', 'attestation_usage_agricole',
  'taux_autoconso', 'taux_couverture', 'payback', 'injection_kwh_an', 'injection_dh_an',
  'repartition_mt', 'etude_kwc_base',
  'chambres', 'occupation_pct', 'piscine', 'chambres_froides', 'horaires', 'cuisson',
  'surface_vente_m2', 'effectif', 'clim', 'lits', 'garde_nuit', 'internat',
  'fermeture_estivale', 'surface_m2', 'chauffe', 'four', 'cuisson_nocturne',
  'temperature_consigne', 'volume_m3', 'saisonnalite_recolte',
])

const horsSchema = (obj) => Object.keys(obj).filter(k => obj[k] !== undefined && !ECRAN.has(k))

const CHOIX = { scenario: 'sans_batterie', recommended_option: 'sans_batterie', nombre_proprietes: null }
const entrees = (conso) => (conso != null ? { conso_annuelle: conso, distributeur: 'onee' } : {})

// CIQ126 — les ENTRÉES C&I v2 (forme `entreesCiV2`, contrat etude_ci_preview).
const ENTREES_CI = {
  mode: 'industriel', site: { ville: null, lat: null, lon: null }, tension: 'mt',
  phases: 'tri', puissance_souscrite_kva: 250, consommation: { kwh_mensuels: null,
    kwh_annuel: 250000, factures_mad: [], registres_mt: null },
  rythme: null, courbe_mesuree: null, toit: null, contraintes: null, options: null,
  taille_explicite_kwc: null,
}
const CLES_V1_RETIREES = [
  'taux_autoconso', 'taux_couverture', 'payback', 'part_diurne_pct', 'etude_kwc_base',
  'injection_kwh_an', 'injection_dh_an', 'tension_raccordement', 'repartition_mt',
  'conso_annuelle', 'distributeur',
]

test('CIQ126 — industriel : seules les ENTRÉES v2 partent, aucune clé écran v1', () => {
  const bloc = projeterEtudeMarche('industriel', {
    choix: CHOIX, entrees, ciEntrees: ENTREES_CI,
  })
  assert.deepEqual(bloc, { ...CHOIX, ...ENTREES_CI })
  for (const k of CLES_V1_RETIREES) assert.ok(!(k in bloc), `${k} ne doit plus sortir`)
})

test('commercial : catégorie + réponses typées, entrées v2, aucune clé v1', () => {
  const bloc = projeterEtudeMarche('commercial', {
    choix: CHOIX, entrees, ciEntrees: { ...ENTREES_CI, mode: 'commercial' },
    categorie: 'hotel', reponses: { chambres: '40', piscine: 1, occupation_pct: '' },
  })
  assert.deepEqual(horsSchema(Object.fromEntries(Object.entries(bloc)
    .filter(([k]) => !(k in ENTREES_CI)))), [])
  for (const k of CLES_V1_RETIREES) assert.ok(!(k in bloc), `${k} ne doit plus sortir`)
  assert.equal(bloc.mode, 'commercial')
  assert.equal(bloc.categorie_commerciale, 'hotel')
  assert.equal(bloc.chambres, 40)
  assert.equal(bloc.piscine, true)
  assert.ok(!('occupation_pct' in bloc))
})

const DERIVEES_POMPAGE = [
  'pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h', 'm3_jour', 'champ_kwc',
  'heures_pompage', 'besoin_mensuel', 'production', 'couverture_pct_mois',
  'controle_conception', 'conception', 'champ', 'hmt_composantes', 'ha_irrigables',
  'autonomie_reservoir_jours', 'kit', 'alertes_pompage', 'hypotheses_pompage',
  'pvgis_fige', 'provenance_pompage',
  // les clés v1 retirées du schéma (AGR122)
  'debit_souhaite_m3h', 'profondeur_m', 'distance_m', 'region', 'crop', 'surface_ha',
  'hmt_static', 'hmt_drawdown', 'irrigation_method',
]

// L'état du corps de l'aperçu, tel que l'écran le tient (nombres en texte).
const ETAT_POMPAGE = {
  mode_pompe: 'neuve', plaque: { kw: '', cv: '5.5' },
  besoin: { mode: 'volume_declare', volume_m3_jour: '135', debit_souhaite_m3h: '12',
    mois_pointe: '7', cultures: [{ crop: 'olivier', surface_ha: '4', irrigation: 'goutte' }], region: '' },
  source: { niveau_statique_m: '32', niveau_dynamique_m: '', rabattement_m: '8',
    profondeur_forage_m: '', compteur: 'oui', debit_exploitation_origine: 'foreur' },
  hmt: { saisie_m: '60', denivele_m: '', conduite: null },
  alim: 'tri', type_pompe: 'immergee', localisation: { ville: '', lat: '', lon: '' },
  distance_champ_m: '30', options_cochees: ['afficheur_variateur'], taille: 'recommandee',
  lead: 7, devis: 12,
}

test('AGR130 — agricole : seules les ENTRÉES v2 partent, typées, aucune dérivée', () => {
  const bloc = projeterEtudeMarche('agricole', {
    choix: CHOIX, entrees,
    pompageEntrees: ETAT_POMPAGE,
    exploitation: {},
  })
  assert.deepEqual(horsSchema(bloc), [])
  for (const cle of DERIVEES_POMPAGE) assert.equal(cle in bloc, false, cle)
  assert.equal(bloc.mode_pompe, 'neuve')
  assert.equal(bloc.plaque, null, 'pas de plaque en mode neuve')
  assert.equal(bloc.besoin.volume_m3_jour, 135)
  assert.equal(bloc.besoin.debit_souhaite_m3h, 12)
  assert.equal(bloc.besoin.region, null)
  assert.equal(bloc.besoin.cultures[0].surface_ha, 4)
  assert.equal(bloc.source.niveau_statique_m, 32)
  assert.equal(bloc.source.compteur, true)
  assert.equal(bloc.source.profondeur_forage_m, null)
  assert.equal(bloc.hmt_entrees.saisie_m, 60)
  assert.equal(bloc.distance_champ_m, 30)
  assert.deepEqual(bloc.options_cochees, ['afficheur_variateur'])
  assert.equal(bloc.taille, 'recommandee')
  assert.equal('lead' in bloc, false)
  assert.equal('devis' in bloc, false)
  assert.equal(bloc.saisies_economie_pompage, null)
  assert.ok(!('conso_annuelle' in bloc))
})

test('AGR130 — mode « existante » : la plaque part, sans CV converti', () => {
  const bloc = projeterEtudeMarche('agricole', {
    choix: {}, entrees: {},
    pompageEntrees: { ...ETAT_POMPAGE, mode_pompe: 'existante',
      plaque: { kw: '5,5', tension_v: '380', phases: 'tri', cv: '', courant_a: '' } },
  })
  assert.deepEqual(bloc.plaque, { kw: 5.5, tension_v: 380, phases: 'tri', cv: null, courant_a: null })
})

test('AGR130 — sans état de pompage : aucune clé pompage, aucun défaut inventé', () => {
  const bloc = projeterEtudeMarche('agricole', { choix: {}, entrees: {} })
  for (const cle of DERIVEES_POMPAGE) assert.equal(cle in bloc, false, cle)
  assert.equal('mode_pompe' in bloc, false)
})

test('AGR130 — lignesDepuisKit : le kit serveur, aucun prix inventé', () => {
  const produits = [
    { id: 314, nom: 'Pompe OSP 30/8', prix_vente: '10000', taux_tva: '20' },
    { id: 3, nom: 'Panneau 710W', prix_vente: '1000', taux_tva: '20' },
  ]
  const kit = {
    inclus: [
      { cle: 'pompe', produit: 314, designation: 'Pompe OSP 30/8', quantite: 1, prix_connu: true },
      { cle: 'panneaux', produit: 3, designation: 'Panneau 710W', quantite: 14, prix_connu: true },
      { cle: 'variateur', produit: null, designation: 'Variateur — prix à renseigner : X', quantite: 1, prix_connu: false },
    ],
    options: [
      { cle: 'afficheur_variateur', libelle: 'Afficheur', produit: 420, prix_connu: false, cochee: true, quantite: 1 },
      { cle: 'sonde', libelle: 'Sonde', produit: null, prix_connu: false, cochee: false, quantite: 1 },
      { cle: 'cable', libelle: 'Câble', produit: 88, prix_connu: true, cochee: true, quantite: null },
    ],
  }
  const lignes = lignesDepuisKit(kit, produits)
  assert.deepEqual(lignes.map(l => [l.produit, l.quantite]),
    [['314', 1], ['3', 14], ['', 1], ['', 1]])
  assert.equal(lignes[0].prix_unit_ttc, 12000)
  assert.equal(lignes[2].prix_unit_ttc, 0)
  assert.equal(lignes[2].designation, 'Variateur — prix à renseigner : X')
  assert.equal(lignes[3].designation, 'Afficheur — prix à renseigner')
  assert.deepEqual(lignesDepuisKit(null, produits), [])
})

test('résidentiel : choix + entrées, objet vide ⇒ null', () => {
  assert.equal(projeterEtudeMarche('residentiel', { choix: {}, entrees: () => ({}) }), null)
  assert.deepEqual(
    projeterEtudeMarche('residentiel', { choix: { scenario: 'avec_batterie' }, entrees: () => ({}) }),
    { scenario: 'avec_batterie' },
  )
})

// ── AGR212 — saisies DÉCLARÉES de l'économie de pompage ────────────────────
const ICI = path.dirname(fileURLToPath(import.meta.url))
const CONTRAT_ECO = JSON.parse(readFileSync(path.resolve(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/economie_pompage.json'),
'utf8'))

test('AGR212 — énergie jamais touchée ⇒ energie_actuelle absente', () => {
  assert.equal(saisiesEconomiePompage(ECO_POMPAGE_VIDE), null)
  const s = saisiesEconomiePompage({ ...ECO_POMPAGE_VIDE, entretien: '1500' },
    { aujourdhui: '2026-10-05' })
  assert.equal('energie_actuelle' in s, false)
  assert.deepEqual(s.entretien_paye_mad_an, { valeur: 1500, saisi_le: '2026-10-05' })
})

test('AGR212 — 2 000 /mois sur 4 mois : 24 000 n’apparaît nulle part', () => {
  const s = saisiesEconomiePompage({
    ...ECO_POMPAGE_VIDE, energie: 'diesel', quantite: '2000', unite: 'litre',
    periode: 'mois', prix: '1', mois: [5, 6, 7, 8], dateDeclaration: '2026-10-05',
  })
  const bloc = projeterEtudeMarche('agricole', {
    choix: {}, entrees: {}, exploitation: { saisiesEconomie: s } })
  const texteBloc = JSON.stringify(bloc)
  assert.equal(texteBloc.includes('24000'), false)
  assert.equal(bloc.saisies_economie_pompage.consommation.quantite, 2000)
  assert.equal(bloc.saisies_economie_pompage.consommation.periode, 'mois')
})

test('AGR212 — aller-retour exact de la forme du contrat', () => {
  const exemple = CONTRAT_ECO.saisies_economie_pompage.exemple
  assert.deepEqual(saisiesEconomiePompage(ecoDepuisSaisies(exemple)), exemple)
})

test('AGR212 — mois du calendrier : provenance « calendrier » puis « déclaré »', () => {
  const base = { ...ECO_POMPAGE_VIDE, energie: 'butane', dateDeclaration: '2026-10-05' }
  const cal = saisiesEconomiePompage(base, { moisCalendrier: [4, 5, 6] })
  assert.deepEqual(cal.mois_irrigation.provenance,
    { origine: 'calculee', detail: 'calendrier_culture', date: '2026-10-05' })
  const conf = saisiesEconomiePompage({ ...base, confirme: true }, { moisCalendrier: [4, 5, 6] })
  assert.equal(conf.mois_irrigation.provenance.origine, 'saisie')
  const touche = saisiesEconomiePompage({ ...base, mois: [6, 4] })
  assert.deepEqual(touche.mois_irrigation.mois, [4, 6])
  assert.equal(touche.mois_irrigation.provenance.origine, 'saisie')
})

// ── AGR218 — attestation d'usage agricole (contrat AGR200) ─────────────────
const CONTRAT_LIGNES = JSON.parse(readFileSync(path.resolve(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/devis_replace_lines_entete.json'),
'utf8'))

test('AGR218 — attestation : aller-retour exact de la forme du contrat', () => {
  const exemple = CONTRAT_LIGNES.corps_agricole.etude_params.attestation_usage_agricole
  assert.deepEqual(attestationUsageAgricole(attestationDepuisEtude(exemple)), exemple)
})

test('AGR218 — rien de coché ni saisi ⇒ null (clé retirée, jamais d’attestation supposée)', () => {
  assert.equal(attestationUsageAgricole(attestationDepuisEtude(null)), null)
  assert.equal(attestationUsageAgricole(undefined), null)
})

test('AGR218 — l’attestation part dans etude_params agricole, clé ECRAN', () => {
  const attestation = { attestee: true, le: '2026-10-02', signataire: 'M. Exploitant' }
  const bloc = projeterEtudeMarche('agricole', {
    choix: {}, entrees: {}, exploitation: { attestation } })
  assert.deepEqual(bloc.attestation_usage_agricole, attestation)
  assert.deepEqual(horsSchema(bloc), [])
})
