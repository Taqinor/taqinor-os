/* LANE Q-C — dialogue « Envoyer un questionnaire » : logique pure.
     node --test src/features/crm/workspace/questionnaireLink.test.mjs */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  SECTIONS_QUESTIONNAIRE, questionsDepuisReponse, questionsPourEnvoi,
  nbSectionsChoisies, questionnaireWhatsappText, sectionsVisibles,
  messageRefusSection,
} from './questionnaireLink.js'
import { exempleContrat } from '../../../test/fixtures/contractSamples.js'
import { buildWaUrl } from '../../ventes/clientProposalLink.js'

test('whitelist des clés-sections, dans l’ordre du contrat serveur', () => {
  // Ordre = crm.QuestionnaireLien.SECTIONS_CLES (recherche 25/08/2026) :
  // engagement croissant côté client, `contact` en dernier. Le commercial
  // coche donc dans l'ordre exact où le prospect répondra.
  assert.deepEqual(
    SECTIONS_QUESTIONNAIRE.map((s) => s.key),
    ['occupation', 'equipements', 'energie', 'pompage', 'reseau', 'activite',
      'toiture', 'site', 'gps',
      'photo_facture', 'photo_compteur', 'photo_tableau',
      'photo_pompe', 'photo_forage', 'photo_factures', 'photo_poste',
      'societe', 'contact'],
  )
  // Chaque clé porte un libellé FR non vide — jamais une case sans texte.
  for (const { label } of SECTIONS_QUESTIONNAIRE) {
    assert.ok(label && label.trim().length > 0)
  }
})

test('défaut = manquantes (aucune question déjà stockée)', () => {
  const data = {
    manquantes: { energie: true, toiture: true },
    questions: {},
  }
  const sel = questionsDepuisReponse(data)
  assert.deepEqual(sel, {
    contact: false, gps: false, energie: true, photo_facture: false,
    photo_compteur: false, photo_tableau: false, toiture: true,
    occupation: false, equipements: false,
    pompage: false, photo_pompe: false, photo_forage: false,
    reseau: false, activite: false, site: false, societe: false,
    photo_factures: false, photo_poste: false,
  })
})

test('défaut = manquantes même si `questions` est absent (premier mint)', () => {
  const sel = questionsDepuisReponse({ manquantes: { gps: true } })
  assert.equal(sel.gps, true)
  assert.equal(sel.contact, false)
})

test('réouverture : un lien déjà minté avec des questions choisies REPREND ces questions, pas les manquantes', () => {
  const data = {
    // Le lead a ENTRE-TEMPS renseigné son énergie (donc plus « manquant »),
    // mais le commercial avait explicitement décoché « energie » et coché
    // « toiture » la dernière fois — la vérité serveur (questions) doit
    // gagner sur les manquantes ACTUELLES.
    manquantes: { energie: true },
    questions: {
      contact: false, gps: true, energie: false, photo_facture: false,
      photo_compteur: false, photo_tableau: false, toiture: true,
      occupation: false, equipements: true,
    },
  }
  const sel = questionsDepuisReponse(data)
  assert.deepEqual(sel, data.questions)
  // La preuve que ce n'est PAS `manquantes` qui a gagné : `energie` est
  // manquant côté serveur mais decoché dans `questions` → reste decoché.
  assert.equal(sel.energie, false)
})

test('questionsPourEnvoi ignore toute clé hors whitelist et ne renvoie que les clés connues', () => {
  const payload = questionsPourEnvoi({ toiture: true, hacked_field: true, gps: false })
  assert.deepEqual(
    Object.keys(payload).sort(),
    SECTIONS_QUESTIONNAIRE.map((s) => s.key).sort(),
  )
  assert.equal(payload.toiture, true)
  assert.equal('hacked_field' in payload, false)
})

test('nbSectionsChoisies compte les cases cochées, jamais une clé hors whitelist', () => {
  assert.equal(nbSectionsChoisies({}), 0)
  assert.equal(nbSectionsChoisies({ gps: true, toiture: true, inconnu: true }), 2)
})

test('le message WhatsApp contient l’URL passée', () => {
  const url = 'https://taqinor.ma/questionnaire/jean/tok123'
  const msg = questionnaireWhatsappText('Jean', url)
  assert.ok(msg.includes(url))
  assert.ok(msg.startsWith('Bonjour Jean, '))
})

test('sans prénom, salutation générique (jamais "Bonjour undefined")', () => {
  const msg = questionnaireWhatsappText('', 'https://taqinor.ma/questionnaire/x/y')
  assert.ok(msg.startsWith('Bonjour, '))
})

test('ADDENDUM — le message WhatsApp ne contient JAMAIS url_interne (jeton distinct de l’aperçu commercial)', () => {
  const reponseServeur = {
    url: 'https://taqinor.ma/questionnaire/jean/tok-client-abc',
    url_interne: 'https://taqinor.ma/questionnaire/jean/tok-interne-xyz',
  }
  const msg = questionnaireWhatsappText('Jean', reponseServeur.url)
  assert.ok(msg.includes(reponseServeur.url))
  assert.ok(!msg.includes(reponseServeur.url_interne))
  assert.ok(!msg.includes('tok-interne-xyz'))

  const waUrl = buildWaUrl('212600000000', msg)
  assert.ok(!waUrl.includes(reponseServeur.url_interne))
  assert.ok(!waUrl.includes('tok-interne'))
})

// AGR419 — les sections viennent de la réponse du serveur (contrat partagé
// `questionnaire_lien_mint.json`, check_api_shapes), jamais d'une liste devinée.
test('AGR419 — un lead agricole voit pompage et ses photos, jamais equipements', () => {
  const data = exempleContrat('crm', 'questionnaire_lien_mint', 'exemple_agricole')
  const cles = sectionsVisibles(data).map((s) => s.key)
  assert.deepEqual(cles, ['pompage', 'gps', 'photo_compteur', 'photo_pompe', 'photo_forage', 'contact'])
  for (const interdite of ['equipements', 'occupation', 'energie', 'toiture', 'photo_facture', 'photo_tableau']) {
    assert.ok(!cles.includes(interdite), interdite)
  }
  // Chaque section servie a un libellé français non vide.
  for (const { label } of sectionsVisibles(data)) assert.ok(label.trim().length > 0)
  // Le défaut des cases = les manquantes servies ; le POST ne nomme que les
  // sections visibles (jamais equipements → pas de 400).
  const sel = questionsDepuisReponse(data)
  assert.deepEqual(Object.keys(questionsPourEnvoi(sel, sectionsVisibles(data))), cles)
  assert.equal(nbSectionsChoisies(sel, sectionsVisibles(data)), 5)
})

test('AGR419 — un lead résidentiel voit la liste d’avant (les 9 sections)', () => {
  const data = exempleContrat('crm', 'questionnaire_lien_mint')
  assert.deepEqual(
    sectionsVisibles(data).map((s) => s.key),
    ['occupation', 'equipements', 'energie', 'toiture', 'gps',
      'photo_facture', 'photo_compteur', 'photo_tableau', 'contact'],
  )
  // Pas encore de réponse serveur : périmètre historique, jamais pompage.
  assert.deepEqual(
    sectionsVisibles(null).map((s) => s.key),
    ['occupation', 'equipements', 'energie', 'toiture', 'gps',
      'photo_facture', 'photo_compteur', 'photo_tableau', 'contact'],
  )
})

// CIQ421 — fixtures du contrat partagé `questionnaire_lien_mint.json`
// (`exemple_pro`, check_api_shapes) : la vérité vient du serveur (CIQ412).
test('CIQ421 — un lead commercial voit réseau, activité, site et société, jamais équipements', () => {
  const data = exempleContrat('crm', 'questionnaire_lien_mint', 'exemple_pro')
  const cles = sectionsVisibles(data).map((s) => s.key)
  for (const attendue of ['reseau', 'activite', 'site', 'societe', 'photo_factures', 'photo_poste', 'contact']) {
    assert.ok(cles.includes(attendue), attendue)
  }
  for (const interdite of ['equipements', 'occupation', 'energie', 'toiture', 'pompage']) {
    assert.ok(!cles.includes(interdite), interdite)
  }
  for (const { label } of sectionsVisibles(data)) assert.ok(label.trim().length > 0)
  // Le POST ne nomme que les sections servies (jamais une résidentielle).
  const sel = questionsDepuisReponse(data)
  assert.deepEqual(Object.keys(questionsPourEnvoi(sel, sectionsVisibles(data))), cles)
})

test('CIQ421 — un refus 400 d’une section résidentielle pour un pro nomme la section', () => {
  const err = { response: { data: { detail: 'Section « occupation » non posée à un lead professionnel : le questionnaire pro ne pose ni occupation.' } } }
  const msg = messageRefusSection(err)
  assert.ok(msg.includes('Présence en journée'))
  assert.ok(msg.includes('occupation'))
})

test('AGR419 — un refus 400 est affiché avec la section qu’il nomme', () => {
  const err = { response: { data: { detail: 'Section « equipements » non posée à un lead agricole : le questionnaire pompage ne pose ni factures.' } } }
  const msg = messageRefusSection(err)
  assert.ok(msg.includes('Équipements (piscine, VE, clim, chauffe-eau)'))
  assert.ok(msg.includes('equipements'))
  assert.equal(messageRefusSection({ response: { data: { detail: 'Autre erreur.' } } }), null)
  assert.equal(messageRefusSection(null), null)
})
