// ADOC119 — un chemin de mot de passe temporaire par portée portail.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PORTEE_INTERNE, PORTEE_CLIENT, PORTEE_FOURNISSEUR, PORTEE_PARTENAIRE,
  cheminMotDePassePortail, portalHomePath,
} from './portalScope.js'

test('cheminMotDePassePortail : un chemin pour les trois portées', () => {
  assert.equal(cheminMotDePassePortail(PORTEE_CLIENT), '/portail/client/mot-de-passe')
  assert.equal(cheminMotDePassePortail(PORTEE_FOURNISSEUR), '/portail/fournisseur/mot-de-passe')
  assert.equal(cheminMotDePassePortail(PORTEE_PARTENAIRE), '/portail/partenaire/mot-de-passe')
})

test('cheminMotDePassePortail : interne/inconnu/prototype → null', () => {
  assert.equal(cheminMotDePassePortail(PORTEE_INTERNE), null)
  assert.equal(cheminMotDePassePortail('nimporte'), null)
  assert.equal(cheminMotDePassePortail('constructor'), null)
})

test('le chemin commence par la racine du shell de la portée', () => {
  for (const portee of [PORTEE_CLIENT, PORTEE_FOURNISSEUR, PORTEE_PARTENAIRE]) {
    const racine = portalHomePath({ portee })
    assert.ok(cheminMotDePassePortail(portee).startsWith(`${racine}/`))
  }
})
