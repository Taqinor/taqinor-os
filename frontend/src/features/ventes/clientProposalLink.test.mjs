// L5 — lien PAGE CLIENT + message WhatsApp de la fiche lead (DevisTab).
// Exécutés en CI : node --test src/features/ventes/clientProposalLink.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clientProposalUrl, proposalWhatsappText, buildWaUrl, DEFAULT_PUBLIC_SITE_URL,
} from './clientProposalLink.js'

test('clientProposalUrl : préfixe le chemin relatif par le site public', () => {
  assert.equal(
    clientProposalUrl('/proposition/jean-dupont/abc123', 'https://taqinor.ma'),
    'https://taqinor.ma/proposition/jean-dupont/abc123',
  )
})

test('clientProposalUrl : retombe sur DEFAULT_PUBLIC_SITE_URL si aucun site fourni', () => {
  assert.equal(
    clientProposalUrl('/proposition/x/y'),
    `${DEFAULT_PUBLIC_SITE_URL}/proposition/x/y`,
  )
})

test('clientProposalUrl : tolère un site avec slash final et un chemin sans slash initial', () => {
  assert.equal(
    clientProposalUrl('proposition/x/y', 'https://taqinor.ma/'),
    'https://taqinor.ma/proposition/x/y',
  )
})

test('clientProposalUrl : chemin absent -> juste l’origine (jamais une exception)', () => {
  assert.equal(clientProposalUrl(undefined, 'https://taqinor.ma'), 'https://taqinor.ma/')
})

test('proposalWhatsappText : MÊME format que ToitureDesign.jsx designWhatsappText', () => {
  assert.equal(
    proposalWhatsappText('Karim', 'https://taqinor.ma/proposition/karim/abc'),
    "Bonjour Karim, voici votre proposition d'installation solaire Taqinor : "
    + 'https://taqinor.ma/proposition/karim/abc N\'hésitez pas à me poser vos questions.',
  )
})

test('proposalWhatsappText : nom vide -> salutation générique, jamais "Bonjour undefined"', () => {
  assert.match(proposalWhatsappText('', 'https://x/y'), /^Bonjour, voici/)
  assert.match(proposalWhatsappText(undefined, 'https://x/y'), /^Bonjour, voici/)
  assert.match(proposalWhatsappText('   ', 'https://x/y'), /^Bonjour, voici/)
})

test('buildWaUrl : encode le texte et pose le numéro déjà normalisé', () => {
  assert.equal(
    buildWaUrl('212612345678', 'Bonjour, voici le lien : https://x/y'),
    'https://wa.me/212612345678?text='
    + encodeURIComponent('Bonjour, voici le lien : https://x/y'),
  )
})

test('buildWaUrl : aucun numéro -> null, jamais un lien wa.me/ invalide', () => {
  assert.equal(buildWaUrl(null, 'texte'), null)
  assert.equal(buildWaUrl('', 'texte'), null)
  assert.equal(buildWaUrl(undefined, 'texte'), null)
})
