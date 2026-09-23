import { test } from 'node:test'
import assert from 'node:assert/strict'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples.js'
import {
  SEGMENT_RESIDENTIEL, segmentLivre, guidanceAppel, messageSegmentNonLivre,
  MESSAGE_SEGMENT_A_CONFIRMER,
} from './appelGuidance.js'

// Les charges utiles viennent du contrat COMMITTÉ (PACT10/PACT13) — jamais
// d'un mock tapé à la main : `panneau_appel.json` (CAD147).
const CONTRAT = ['crm', 'panneau_appel']
const exemple = (variante = 'exemple') => exempleContrat(...CONTRAT, variante)

// ── CAD161 — le résidentiel d'abord ─────────────────────────────────────────

test('CAD161 — le contrat porte le champ `segment` dans chacun de ses exemples', () => {
  const doc = documentContrat(...CONTRAT)
  for (const variante of ['exemple', 'exemple_sans_cadence_active', 'exemple_tout_repondu']) {
    assert.ok('segment' in doc[variante], `« segment » absent de ${variante}`)
    assert.ok('segment_libelle' in doc[variante], `« segment_libelle » absent de ${variante}`)
  }
  assert.equal(doc.exemple.segment, SEGMENT_RESIDENTIEL)
})

test('CAD161 — un lead résidentiel reçoit le panneau guidé', () => {
  const g = guidanceAppel(exemple())
  assert.equal(g.livre, true)
  assert.equal(g.segmentAConfirmer, false)
  assert.equal(g.avertissement, null)
})

test('CAD161 — un lead agricole est refusé PROPREMENT : message explicite, jamais une page vide', () => {
  const panneau = exemple('exemple_sans_cadence_active')
  assert.equal(panneau.segment, 'agricole')
  const g = guidanceAppel(panneau)
  assert.equal(g.livre, false)
  assert.equal(g.segment, 'agricole')
  assert.ok(g.message.trim().length > 0)
  assert.match(g.message, /résidentiel/)
  assert.match(g.message, /« Agricole »/)
  assert.equal(g.questions, undefined, 'aucun script résidentiel déguisé')
})

test('CAD161 — industriel et commercial sont refusés avec le libellé servi', () => {
  for (const [segment, segment_libelle] of [['industriel', 'Industriel'], ['commercial', 'Commercial']]) {
    const g = guidanceAppel({ ...exemple(), segment, segment_libelle })
    assert.equal(g.livre, false, segment)
    assert.match(g.message, new RegExp(`« ${segment_libelle} »`))
  }
})

test('CAD161 — un segment non saisi reçoit le résidentiel, marqué « à confirmer »', () => {
  const g = guidanceAppel({ ...exemple(), segment: null, segment_libelle: null })
  assert.equal(g.livre, true)
  assert.equal(g.segmentAConfirmer, true)
  assert.equal(g.avertissement, MESSAGE_SEGMENT_A_CONFIRMER)
})

test('CAD161 — segmentLivre : seul le résidentiel (ou le vide) est livré', () => {
  assert.equal(segmentLivre('residentiel'), true)
  assert.equal(segmentLivre(null), true)
  assert.equal(segmentLivre(''), true)
  assert.equal(segmentLivre('agricole'), false)
  assert.equal(segmentLivre('industriel'), false)
  assert.equal(segmentLivre('commercial'), false)
})

test('CAD161 — les textes du refus ne portent ni crochet ni chiffre', () => {
  const textes = [
    MESSAGE_SEGMENT_A_CONFIRMER,
    messageSegmentNonLivre({ segment: 'agricole', segment_libelle: 'Agricole' }),
  ]
  for (const texte of textes) {
    assert.doesNotMatch(texte, /[[\]]/)
    assert.doesNotMatch(texte, /[0-9]/)
  }
})
