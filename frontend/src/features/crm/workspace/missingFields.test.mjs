/* ROUND 5 — « ce qui manque » et le REPLI AUTOMATIQUE, en logique pure.
   L'ordre des sections ne bouge JAMAIS : ce qu'on teste ici, c'est ce qui
   remplace le réordonnancement — un bandeau qui pointe, et un repli qui met
   de côté ce qui est fini.
     node --test src/features/crm/workspace/missingFields.test.mjs */
import test from 'node:test'
import assert from 'node:assert/strict'
import { chipsAComplete, sectionsPointees, missingFieldTarget } from './missingFields.js'
import { sectionAutoRepliee, sectionCoeurKeys, sectionEstVide } from './draftCore.js'
import { QUOTE_SENT_STAGE, FOLLOW_UP_STAGE, PIPELINE_STAGES } from '../stages.js'

const etat = (server = {}, draft = {}) => ({ server, draft, mode: 'edit' })

test('les noms scalaires d’étape sont DÉRIVÉS de la liste canonique (règle #2)', () => {
  assert.equal(QUOTE_SENT_STAGE, PIPELINE_STAGES[2])
  assert.equal(FOLLOW_UP_STAGE, PIPELINE_STAGES[3])
  assert.equal(QUOTE_SENT_STAGE, 'QUOTE_SENT')
  assert.equal(FOLLOW_UP_STAGE, 'FOLLOW_UP')
})

test('rien ne manque → AUCUNE chip (donc aucun bandeau rendu)', () => {
  const s = etat({ stage: PIPELINE_STAGES[0], devis_auto: { pret: true, manquants: [] } })
  assert.deepEqual(chipsAComplete(s), [])
  // C'est l'invariant « zéro chrome quand tout va bien » : le composant ne
  // rend le bandeau QUE si ce tableau n'est pas vide.
})

test('les manquants du devis deviennent des chips cliquables, libellés serveur intacts', () => {
  const s = etat({
    stage: PIPELINE_STAGES[0],
    devis_auto: { pret: false, manquants: ['facture hiver', 'facture été'] },
  })
  const chips = chipsAComplete(s)
  assert.deepEqual(chips.map((c) => c.label), ['facture hiver', 'facture été'])
  // Chaque chip sait où sauter — c'est la MÊME carte que l'onglet Devis.
  assert.deepEqual(
    chips.map((c) => [c.section, c.field]),
    [['energie', 'lf-facture-hiver'], ['energie', 'lf-facture-ete']],
  )
  assert.deepEqual(missingFieldTarget('facture hiver'), chips[0] && { field: chips[0].field, section: chips[0].section })
})

test('chips exactes par type_installation — résidentiel vs agricole', () => {
  // Le serveur produit déjà la bonne liste (devis_auto.py) : on vérifie que
  // les DEUX familles de libellés trouvent leur champ, sans quoi une chip
  // agricole serait un bouton mort.
  const residentiel = chipsAComplete(etat({
    stage: PIPELINE_STAGES[0], type_installation: 'residentiel',
    devis_auto: { pret: false, manquants: ['facture hiver'] },
  }))
  assert.deepEqual(residentiel.map((c) => c.section), ['energie'])

  const agricole = chipsAComplete(etat({
    stage: PIPELINE_STAGES[0], type_installation: 'agricole',
    devis_auto: { pret: false, manquants: ['pompe (CV)', 'HMT', 'débit souhaité'] },
  }))
  assert.deepEqual(agricole.map((c) => c.section), ['pompage', 'pompage', 'pompage'])
  assert.deepEqual(
    agricole.map((c) => c.field),
    ['lf-pompe-cv', 'lf-pompe-hmt', 'lf-pompe-debit'],
  )
})

test('« Relance non planifiée » n’apparaît QUE là où elle est attendue', () => {
  const sansRelance = (stage) => etat({ stage, devis_auto: { pret: true, manquants: [] } })
  const aRelance = (stage) => chipsAComplete(sansRelance(stage)).some((c) => c.id === 'relance')
  // Devis parti / relance en cours : ne pas savoir quand rappeler est une
  // vraie lacune.
  assert.equal(aRelance(QUOTE_SENT_STAGE), true)
  assert.equal(aRelance(FOLLOW_UP_STAGE), true)
  // Avant l'envoi du devis, ou une fois signé/froid : c'est normal, on se tait.
  // Un signal qu'on apprend à ignorer ne vaut rien.
  for (const s of [PIPELINE_STAGES[0], PIPELINE_STAGES[1], PIPELINE_STAGES[4], PIPELINE_STAGES[5]]) {
    assert.equal(aRelance(s), false, `${s} ne devrait rien signaler`)
  }
  // Et elle disparaît dès qu'une relance est posée.
  const planifiee = etat({
    stage: FOLLOW_UP_STAGE, relance_date: '2026-09-01', devis_auto: { pret: true, manquants: [] },
  })
  assert.equal(chipsAComplete(planifiee).some((c) => c.id === 'relance'), false)
})

test('la chip lit le DRAFT, pas seulement le serveur (une relance tapée compte tout de suite)', () => {
  const s = etat({ stage: FOLLOW_UP_STAGE, devis_auto: { pret: true, manquants: [] } },
    { relance_date: '2026-09-01' })
  assert.equal(chipsAComplete(s).length, 0)
})

test('sectionsPointees rassemble les sections visées par le bandeau', () => {
  const chips = chipsAComplete(etat({
    stage: FOLLOW_UP_STAGE,
    devis_auto: { pret: false, manquants: ['facture hiver'] },
  }))
  assert.deepEqual([...sectionsPointees(chips)].sort(), ['energie', 'pipeline'])
})

/* ── Repli automatique ─────────────────────────────────────────────────── */

test('le cœur « énergie » suit le marché — miroir de devis_auto.champs_manquants', () => {
  const coeur = (server) => sectionCoeurKeys(etat(server), 'energie')
  assert.deepEqual(coeur({ type_installation: 'residentiel' }), ['facture_hiver'])
  assert.deepEqual(coeur({}), ['facture_hiver']) // non renseigné = résidentiel
  assert.deepEqual(coeur({ ete_differente: true }), ['facture_hiver', 'facture_ete'])
  assert.deepEqual(coeur({ type_installation: 'commercial' }), ['conso_mensuelle_kwh'])
  assert.deepEqual(coeur({ type_installation: 'industriel' }), ['conso_mensuelle_kwh'])
  // En agricole l'énergie ne se saisit pas ici : tout est dans « Pompage ».
  assert.deepEqual(coeur({ type_installation: 'agricole' }), [])
})

test('une section dont le CŒUR est complet s’ouvre repliée', () => {
  const s = etat({ telephone: '0600000000', ville: 'Marrakech' })
  assert.equal(sectionAutoRepliee(s, 'contact'), true)
  // Un seul champ du cœur manquant suffit à la garder ouverte : c'est bien le
  // cœur qu'on juge, pas « au moins quelque chose ».
  assert.equal(sectionAutoRepliee(etat({ telephone: '0600000000' }), 'contact'), false)
})

test('une section VIDE sans cœur déclaré s’ouvre repliée ; dès qu’elle porte quelque chose, non', () => {
  assert.equal(sectionEstVide(etat({}), 'visite'), true)
  assert.equal(sectionAutoRepliee(etat({}), 'visite'), true)
  assert.equal(sectionAutoRepliee(etat({ visite_notes: 'RDV pris' }), 'visite'), false)
  assert.equal(sectionAutoRepliee(etat({}), 'divers'), true)
  assert.equal(sectionAutoRepliee(etat({ note: 'à rappeler' }), 'divers'), false)
})

test('une section POINTÉE par le bandeau reste ouverte, même si son cœur est complet', () => {
  // Se replier tout en se montrant du doigt serait se contredire dans le même
  // écran.
  const s = etat({ telephone: '0600000000', ville: 'Marrakech' })
  assert.equal(sectionAutoRepliee(s, 'contact', { porteUnManquant: true }), false)
})

test('la zone de TRAVAIL (pipeline) n’est JAMAIS repliée automatiquement', () => {
  // Complète, vide, pointée : dans tous les cas elle reste ouverte — c'est
  // l'outil qu'on a en main.
  assert.equal(sectionAutoRepliee(etat({}), 'pipeline'), false)
  assert.equal(sectionAutoRepliee(etat({ relance_date: '2026-09-01', priorite: 'haute' }), 'pipeline'), false)
  assert.equal(sectionAutoRepliee(etat({}), 'pipeline', { porteUnManquant: true }), false)
})

test('toiture : cœur = surface + orientation + type', () => {
  assert.deepEqual(sectionCoeurKeys(etat({}), 'toiture'),
    ['surface_toiture_m2', 'orientation', 'type_toiture'])
  const complete = etat({ surface_toiture_m2: 90, orientation: 'sud', type_toiture: 'terrasse' })
  assert.equal(sectionAutoRepliee(complete, 'toiture'), true)
  // Une toiture où on n'a rempli QUE des détails reste ouverte.
  assert.equal(sectionAutoRepliee(etat({ ombrage_notes: 'arbre au sud' }), 'toiture'), false)
})
