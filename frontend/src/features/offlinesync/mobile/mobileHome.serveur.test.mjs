// ALEA31 — « Dashboard suit la route du serveur ».
// Run : node --test src/features/offlinesync/mobile/mobileHome.serveur.test.mjs
//
// Le serveur (`authentication.selectors.default_mobile_home_route`) est la
// SEULE table de l'accueil mobile ; `/auth/me/` la sert dans
// `mobile_home_route_suggeree`. Les profils ci-dessous ont la forme de
// `/auth/me/` (MeSerializer) pour les trois rôles canoniques de la tâche, avec
// la route que le serveur suggère (backend :
// authentication/tests/test_alea_mobile_home_serveur.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { mobileHomeAction, routeSuggereeServeur } from './mobileHome.js'

const ici = dirname(fileURLToPath(import.meta.url))

const PROFILS = [
  { role_nom: 'Commercial terrain', mobile_home_route: null, mobile_home_route_suggeree: '/visites' },
  { role_nom: 'Commercial responsable', mobile_home_route: null, mobile_home_route_suggeree: '/mobile/equipe-commerciale' },
  { role_nom: 'Technicien responsable', mobile_home_route: null, mobile_home_route_suggeree: '/mobile/equipe-terrain' },
]

// Ce que Dashboard.jsx exécute : la décision pure nourrie par la route du serveur.
const decisionDashboard = (user) => mobileHomeAction({
  isMobile: true,
  hasFullProfile: true,
  mobileHomeRoute: user.mobile_home_route,
  suggestedRoute: routeSuggereeServeur(user),
})

test('Dashboard suit la route du serveur', () => {
  for (const user of PROFILS) {
    assert.deepEqual(decisionDashboard(user),
      { type: 'decide', suggested: user.mobile_home_route_suggeree }, user.role_nom)
  }
})

test('Commercial terrain → /visites, jamais /mobile/commercial', () => {
  assert.equal(decisionDashboard(PROFILS[0]).suggested, '/visites')
})

test('route déjà mémorisée → navigue dessus ; opt-out explicite → rien', () => {
  assert.deepEqual(decisionDashboard({ ...PROFILS[0], mobile_home_route: '/visites' }),
    { type: 'navigate', to: '/visites' })
  assert.equal(decisionDashboard({ ...PROFILS[0], mobile_home_route: '' }), null)
})

test('sans suggestion serveur (rôle non mappé) → dashboard générique', () => {
  assert.equal(routeSuggereeServeur({ role_nom: 'Viewer', mobile_home_route_suggeree: '' }), '')
  assert.equal(routeSuggereeServeur({ role_nom: 'Viewer' }), '')
  assert.deepEqual(decisionDashboard({ role_nom: 'Viewer', mobile_home_route: null }),
    { type: 'decide', suggested: '' })
})

test('desktop ou profil pas encore chargé → aucune action', () => {
  assert.equal(mobileHomeAction({ isMobile: false, hasFullProfile: true, mobileHomeRoute: null, suggestedRoute: '/visites' }), null)
  assert.equal(mobileHomeAction({ isMobile: true, hasFullProfile: false, mobileHomeRoute: undefined, suggestedRoute: '' }), null)
})

test('Dashboard.jsx nourrit la décision avec la route du serveur, sans table de rôles', () => {
  const dashboard = readFileSync(join(ici, '../../../pages/Dashboard.jsx'), 'utf8')
  assert.match(dashboard, /suggestedRoute:\s*routeSuggereeServeur\(user\)/)
  assert.doesNotMatch(dashboard, /defaultMobileHomeRoute/)
  const module = readFileSync(join(ici, 'mobileHome.js'), 'utf8')
  // ALEA31 : mobileHome.js ne contient aucun littéral de route d'accueil.
  assert.doesNotMatch(module, /'\/mobile\/commercial'|'\/mobile\/cockpit'|'\/ma-journee'/)
})
