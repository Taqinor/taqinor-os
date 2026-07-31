// NTPRT8/20/27 — portée d'un compte PORTAIL (logique pure, node --test comme
// prefetchMap/moduleGating : aucun DOM requis).
//
// Deux invariants de SÉCURITÉ y sont verrouillés :
//   1. le défaut est TOUJOURS `interne` — un `portee` absent, inconnu ou hérité
//      du prototype ne doit JAMAIS accorder un privilège portail ;
//   2. l'entrée dans un shell portail exige l'ÉGALITÉ EXACTE de portée — un
//      compte fournisseur n'entre pas dans l'espace client « parce qu'il est
//      portail ».
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PORTEE_INTERNE, PORTEE_CLIENT, PORTEE_FOURNISSEUR, PORTEE_PARTENAIRE,
  porteeDe, isPortalUser, portalHomePath, portalScopeId, isPortalPath,
  peutEntrerDansPortail,
} from './portalScope.js'

test('porteeDe : un utilisateur absent/incomplet est INTERNE', () => {
  assert.equal(porteeDe(null), PORTEE_INTERNE)
  assert.equal(porteeDe(undefined), PORTEE_INTERNE)
  assert.equal(porteeDe({}), PORTEE_INTERNE)
  assert.equal(porteeDe({ portee: undefined }), PORTEE_INTERNE)
})

test('porteeDe : une portée INCONNUE est traitée comme interne', () => {
  assert.equal(porteeDe({ portee: 'portail_inconnu' }), PORTEE_INTERNE)
  assert.equal(porteeDe({ portee: 'admin' }), PORTEE_INTERNE)
  // Aucune clé du prototype ne doit être prise pour une portée valide.
  assert.equal(porteeDe({ portee: 'constructor' }), PORTEE_INTERNE)
  assert.equal(porteeDe({ portee: 'toString' }), PORTEE_INTERNE)
})

test('porteeDe : les 3 portées portail canoniques sont reconnues', () => {
  assert.equal(porteeDe({ portee: PORTEE_CLIENT }), PORTEE_CLIENT)
  assert.equal(porteeDe({ portee: PORTEE_FOURNISSEUR }), PORTEE_FOURNISSEUR)
  assert.equal(porteeDe({ portee: PORTEE_PARTENAIRE }), PORTEE_PARTENAIRE)
})

test('isPortalUser / portalHomePath : un interne n’a aucun shell portail', () => {
  const interne = { portee: PORTEE_INTERNE }
  assert.equal(isPortalUser(interne), false)
  assert.equal(portalHomePath(interne), null)
  assert.equal(portalHomePath(null), null)
})

test('portalHomePath : chaque portée a SON shell', () => {
  assert.equal(portalHomePath({ portee: PORTEE_CLIENT }), '/portail/client')
  assert.equal(portalHomePath({ portee: PORTEE_FOURNISSEUR }),
    '/portail/fournisseur')
  assert.equal(portalHomePath({ portee: PORTEE_PARTENAIRE }),
    '/portail/partenaire')
})

test('portalScopeId : lit l’id de rattachement de la BONNE portée', () => {
  assert.equal(portalScopeId({
    portee: PORTEE_CLIENT, portail_client_id: 7, portail_fournisseur_id: 9,
  }), 7)
  assert.equal(portalScopeId({
    portee: PORTEE_FOURNISSEUR, portail_client_id: 7,
    portail_fournisseur_id: 9,
  }), 9)
})

test('portalScopeId : null pour un interne ou un rattachement manquant', () => {
  assert.equal(
    portalScopeId({ portee: PORTEE_INTERNE, portail_client_id: 7 }), null)
  assert.equal(portalScopeId({ portee: PORTEE_CLIENT }), null)
  assert.equal(
    portalScopeId({ portee: PORTEE_CLIENT, portail_client_id: null }), null)
  assert.equal(portalScopeId(null), null)
})

test('isPortalPath : reconnaît l’espace portail et rien d’autre', () => {
  assert.equal(isPortalPath('/portail'), true)
  assert.equal(isPortalPath('/portail/client'), true)
  assert.equal(isPortalPath('/portail/fournisseur/bcf'), true)
  assert.equal(isPortalPath('/dashboard'), false)
  assert.equal(isPortalPath('/crm/leads'), false)
  // Piège : le portail PUBLIC tokenisé des contrats n'est PAS cet espace.
  assert.equal(isPortalPath('/portail-contrats/abc'), false)
  assert.equal(isPortalPath(null), false)
})

test('peutEntrerDansPortail : égalité EXACTE de portée exigée', () => {
  const fournisseur = { portee: PORTEE_FOURNISSEUR }
  assert.equal(peutEntrerDansPortail(fournisseur, PORTEE_FOURNISSEUR), true)
  // Un fournisseur n'entre PAS dans l'espace client, même s'il est portail.
  assert.equal(peutEntrerDansPortail(fournisseur, PORTEE_CLIENT), false)
  assert.equal(peutEntrerDansPortail(fournisseur, PORTEE_PARTENAIRE), false)
})

test('peutEntrerDansPortail : un interne est refusé sur tout shell portail', () => {
  const interne = { portee: PORTEE_INTERNE }
  for (const p of [PORTEE_CLIENT, PORTEE_FOURNISSEUR, PORTEE_PARTENAIRE]) {
    assert.equal(peutEntrerDansPortail(interne, p), false)
  }
})

test('peutEntrerDansPortail : « interne » n’est jamais un portail', () => {
  assert.equal(
    peutEntrerDansPortail({ portee: PORTEE_INTERNE }, PORTEE_INTERNE), false)
  assert.equal(peutEntrerDansPortail(null, PORTEE_INTERNE), false)
})
