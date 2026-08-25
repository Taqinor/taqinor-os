/* LANE Q-C — dialogue « Envoyer un questionnaire » : logique pure.
     node --test src/features/crm/workspace/questionnaireLink.test.mjs */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  SECTIONS_QUESTIONNAIRE, questionsDepuisReponse, questionsPourEnvoi,
  nbSectionsChoisies, questionnaireWhatsappText,
} from './questionnaireLink.js'
import { buildWaUrl } from '../../ventes/clientProposalLink.js'

test('whitelist des clés-sections, dans l’ordre du contrat serveur', () => {
  assert.deepEqual(
    SECTIONS_QUESTIONNAIRE.map((s) => s.key),
    ['contact', 'gps', 'energie', 'photo_facture', 'photo_compteur',
      'photo_tableau', 'toiture', 'occupation', 'equipements'],
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
