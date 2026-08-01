import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  REGISTRE_VOCABULAIRE,
  detecterMotsInterdits,
  contientMotInterdit,
  detecterSurChamps,
} from './sanitisation.js'

/* AOF107 (3/3) — le lexique nommé par le ticket : « client », « croquis »,
   « maximum posable », toute mention de marge ou de prix d'achat — avec
   formulation de remplacement quand il en existe une. */

test('« client » est détecté et propose une reformulation datée', () => {
  const trouvailles = detecterMotsInterdits('Le client a confirmé la position.', { date: '27/07/2026' })
  assert.equal(trouvailles.length, 1)
  assert.equal(trouvailles[0].code, 'client')
  assert.equal(trouvailles[0].remplacement, 'décision d’études du 27/07/2026')
})

test('« croquis » est détecté et propose une reformulation datée', () => {
  const trouvailles = detecterMotsInterdits('D’après le croquis fourni.', { date: '01/08/2026' })
  assert.equal(trouvailles.length, 1)
  assert.equal(trouvailles[0].code, 'croquis')
  assert.equal(trouvailles[0].remplacement, 'relevé contradictoire du 01/08/2026')
})

test('« maximum posable », « marge » et « prix d’achat » sont BLOQUANTS — aucun remplacement proposé', () => {
  for (const [texte, code] of [
    ['Le maximum posable du site est de 630.', 'maximum_posable'],
    ['La marge sur ce lot est confortable.', 'marge'],
    ["Le prix d'achat du produit a baissé.", 'prix_achat'],
  ]) {
    const trouvailles = detecterMotsInterdits(texte)
    assert.equal(trouvailles.length, 1, `attendu une trouvaille pour : ${texte}`)
    assert.equal(trouvailles[0].code, code)
    assert.equal(trouvailles[0].remplacement, null)
  }
})

test('accepte l’apostrophe courbe ET droite pour « prix d’achat »', () => {
  assert.equal(detecterMotsInterdits("prix d'achat trop élevé").length, 1)
  assert.equal(detecterMotsInterdits('prix d’achat trop élevé').length, 1)
})

test('insensible à la casse et au pluriel (« marges », « clients »)', () => {
  assert.equal(detecterMotsInterdits('MARGES excessives').length, 1)
  assert.equal(detecterMotsInterdits('Les Clients ont validé').length, 1)
})

test('un texte propre ne déclenche RIEN', () => {
  assert.deepEqual(detecterMotsInterdits('Le maître d’ouvrage confirme le relevé du 27/07.'), [])
  assert.equal(contientMotInterdit('Aucun mot sensible ici.'), false)
})

test('plusieurs mots interdits dans le MÊME texte sont TOUS détectés, triés par position', () => {
  const trouvailles = detecterMotsInterdits('Le client a vu le croquis puis évoqué la marge.')
  assert.equal(trouvailles.length, 3)
  assert.deepEqual(trouvailles.map((t) => t.code), ['client', 'croquis', 'marge'])
  // Triées par position d'apparition dans le texte.
  assert.ok(trouvailles[0].index < trouvailles[1].index)
  assert.ok(trouvailles[1].index < trouvailles[2].index)
})

test('`contientMotInterdit` est un simple booléen dérivé de la détection', () => {
  assert.equal(contientMotInterdit('Le client valide.'), true)
  assert.equal(contientMotInterdit('Tout est conforme.'), false)
})

test('`detecterSurChamps` ne rend QUE les champs fautifs, nommés', () => {
  const parChamp = detecterSurChamps({
    question: 'Le grand rectangle est-il confirmé néant ?',
    reponse: 'Le client confirme : néant.',
    decision: 'Confirmé.',
  })
  assert.deepEqual(Object.keys(parChamp), ['reponse'])
  assert.equal(parChamp.reponse[0].code, 'client')
})

test('un texte vide ou non-chaîne ne lève jamais', () => {
  assert.deepEqual(detecterMotsInterdits(''), [])
  assert.deepEqual(detecterMotsInterdits(null), [])
  assert.deepEqual(detecterMotsInterdits(undefined), [])
})

test('le registre couvre EXACTEMENT les 5 codes nommés par le ticket AOF107', () => {
  assert.deepEqual(
    REGISTRE_VOCABULAIRE.map((r) => r.code).sort(),
    ['client', 'croquis', 'marge', 'maximum_posable', 'prix_achat'].sort(),
  )
})
