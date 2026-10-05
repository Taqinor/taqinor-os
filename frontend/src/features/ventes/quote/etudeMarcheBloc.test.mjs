// QJR542 — la projection « étude du marché → clés etude_params légales »
// vit dans UNE fonction pure partagée (générateur + devis automatique).
// Run : node --test src/features/ventes/quote/etudeMarcheBloc.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  projeterEtudeMarche, saisiesEconomiePompage, ecoDepuisSaisies, ECO_POMPAGE_VIDE,
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
  'pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h', 'm3_jour', 'champ_kwc',
  'irrigation_method', 'debit_souhaite_m3h', 'heures_pompage', 'type_pompe', 'alim',
  'profondeur_m', 'distance_m', 'region', 'crop', 'surface_ha',
  'saisies_economie_pompage', 'hmt_static', 'hmt_drawdown',
  'taux_autoconso', 'taux_couverture', 'payback', 'injection_kwh_an', 'injection_dh_an',
  'repartition_mt', 'etude_kwc_base',
  'chambres', 'occupation_pct', 'piscine', 'chambres_froides', 'horaires', 'cuisson',
  'surface_vente_m2', 'effectif', 'clim', 'lits', 'garde_nuit', 'internat',
  'fermeture_estivale', 'surface_m2', 'chauffe', 'four', 'cuisson_nocturne',
  'temperature_consigne', 'volume_m3', 'saisonnalite_recolte',
])

const horsSchema = (obj) => Object.keys(obj).filter(k => obj[k] !== undefined && !ECRAN.has(k))

// Étude BRUTE (forme computeEtudeIndustrielle) : kwc / prix_kwc /
// economies_annuelles n'ont rien à faire dans etude_params via l'écran.
const ETUDE_BRUTE = {
  kwc: 120, prix_kwc: 7000, economies_annuelles: 210000, production_annuelle: 190000,
  conso_annuelle: '250000', taux_autoconso: '82.5', taux_couverture: 61,
  payback: '4.2', injection_kwh_an: 12000, injection_dh_an: 'x',
}
const CHOIX = { scenario: 'sans_batterie', recommended_option: 'sans_batterie', nombre_proprietes: null }
const entrees = (conso) => (conso != null ? { conso_annuelle: conso, distributeur: 'onee' } : {})

test('industriel : aucune clé hors ECRAN, étude brute filtrée, état fixe identique', () => {
  const bloc = projeterEtudeMarche('industriel', {
    etude: ETUDE_BRUTE, choix: CHOIX, entrees, partDiurne: '65',
    tensionRaccordement: 'mt', repartitionMt: { pointe: '20', pleines: '50', creuses: '' },
  })
  assert.deepEqual(horsSchema(bloc), [])
  for (const k of ['kwc', 'prix_kwc', 'economies_annuelles', 'production_annuelle']) {
    assert.ok(!(k in bloc), `${k} ne doit pas sortir`)
  }
  assert.deepEqual(bloc, {
    scenario: 'sans_batterie', recommended_option: 'sans_batterie', nombre_proprietes: null,
    conso_annuelle: 250000, distributeur: 'onee',
    taux_autoconso: 82.5, taux_couverture: 61, payback: 4.2,
    injection_kwh_an: 12000, injection_dh_an: null, etude_kwc_base: 120,
    part_diurne_pct: 65,
    tension_raccordement: 'mt', repartition_mt: { pointe: 20, pleines: 50 },
  })
})

test('commercial : catégorie + réponses typées, pas de part diurne, BT ⇒ repartition null', () => {
  const bloc = projeterEtudeMarche('commercial', {
    etude: ETUDE_BRUTE, choix: CHOIX, entrees, partDiurne: '65',
    tensionRaccordement: 'bt', repartitionMt: { pointe: '20' },
    categorie: 'hotel', reponses: { chambres: '40', piscine: 1, occupation_pct: '' },
  })
  assert.deepEqual(horsSchema(bloc), [])
  assert.equal(bloc.part_diurne_pct, undefined)
  assert.equal(bloc.repartition_mt, null)
  assert.equal(bloc.categorie_commerciale, 'hotel')
  assert.equal(bloc.chambres, 40)
  assert.equal(bloc.piscine, true)
  assert.ok(!('occupation_pct' in bloc))
})

test('agricole : pompe_cv est un nombre, seules des clés ECRAN sortent', () => {
  const pompage = {
    pompe_cv: '5.5', pompe_kw: 4, debit_hmt_m3h: 12.4, m3_jour: 86.8, champ_kwc: 5.6,
    // clés BRUTES de buildEtudePompage hors schéma :
    pompe_designation: 'OSP 30-5', kwc: 5.6, prix: 1000,
  }
  const bloc = projeterEtudeMarche('agricole', {
    choix: CHOIX, entrees,
    pompage,
    saisiePompage: { hmt: '60', debit: '12', heures: '7', typePompe: 'immergee', alim: 'solaire', profondeur: '', distance: '30' },
    exploitation: { irrigation: 'goutte', region: '', crop: 'olivier', surfaceHa: '4', hmtStatic: '', hmtDrawdown: '5' },
  })
  assert.deepEqual(horsSchema(bloc), [])
  assert.equal(typeof bloc.pompe_cv, 'number')
  assert.equal(bloc.pompe_cv, 5.5)
  assert.equal(bloc.hmt_m, 60)
  assert.equal(bloc.profondeur_m, null)
  assert.equal(bloc.region, null)
  assert.equal('current_fuel' in bloc, false)
  assert.equal('fuel_spend_current' in bloc, false)
  assert.equal(bloc.saisies_economie_pompage, null)
  assert.ok(!('conso_annuelle' in bloc))
})

test('agricole sans pompe retenue : dérivées nulles, entrées de l\'écran gardées', () => {
  const bloc = projeterEtudeMarche('agricole', {
    choix: {}, entrees: {}, pompage: {}, saisiePompage: { hmt: '40' },
  })
  assert.equal(bloc.pompe_cv, null)
  assert.equal(bloc.hmt_m, 40)
  assert.deepEqual(horsSchema(bloc), [])
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
    choix: {}, entrees: {}, pompage: {}, exploitation: { saisiesEconomie: s } })
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
