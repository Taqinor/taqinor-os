// WIR171 — La sémantique de gating d'un item/route de module doit être le
// MIROIR de la garde serveur, pas un ET palier × permission écrit à la main.
// Test structurel + unitaire en node:test (pas de jsdom dans ce worktree).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { estAutoriseEntree, PALIERS_LEGACY } from './moduleGating.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const lire = (...p) => readFileSync(path.join(__dirname, ...p), 'utf8')

// ── 1. La règle elle-même ────────────────────────────────────────────────────

test('sans `perm` : seul le palier décide (comportement historique)', () => {
  const item = { roles: ['responsable', 'admin'] }
  assert.equal(estAutoriseEntree(item, 'admin', []), true)
  assert.equal(estAutoriseEntree(item, 'responsable', []), true)
  assert.equal(estAutoriseEntree(item, 'normal', []), false)
  // Une permission portée ne peut jamais OUVRIR une entrée sans `perm`.
  assert.equal(estAutoriseEntree(item, 'normal', ['litige_voir']), false)
})

test('`perm` SANS `permRepliPalier` : ET strict — aucune ouverture pour un légacy', () => {
  // C'est le miroir de CanViewAoRentabilite (AOF2, aucun repli légacy) et de
  // CanViewActivityLog : relâcher cette branche rouvrirait la fuite de marge.
  const item = { roles: ['responsable', 'admin'], perm: 'ao_rentabilite_voir' }
  assert.equal(estAutoriseEntree(item, 'admin', ['ao_rentabilite_voir']), true)
  // Compte LÉGACY responsable/admin (aucune permission servie) : refusé.
  assert.equal(estAutoriseEntree(item, 'responsable', []), false)
  assert.equal(estAutoriseEntree(item, 'admin', []), false)
  // Rôle fin sans la permission : refusé.
  assert.equal(estAutoriseEntree(item, 'admin', ['crm_voir']), false)
})

test('`permRepliPalier` : un rôle FIN est jugé sur la SEULE permission', () => {
  const item = { roles: ['normal', 'responsable', 'admin'], perm: 'litige_voir', permRepliPalier: true }
  // « Commercial » : palier 'normal' (role_tiers.py) MAIS porteur de litige_voir
  // ⇒ le serveur répond 200, la coquille doit le laisser passer.
  assert.equal(estAutoriseEntree(item, 'normal', ['litige_voir', 'crm_voir']), true)
  // Rôle fin de palier normal SANS la permission ⇒ 403, comme le serveur.
  assert.equal(estAutoriseEntree(item, 'normal', ['crm_voir']), false)
  // Rôle fin de palier responsable sans la permission ⇒ 403 aussi : le palier
  // ne rattrape JAMAIS un rôle fin (sinon ce ne serait plus la règle serveur).
  assert.equal(estAutoriseEntree(item, 'responsable', ['crm_voir']), false)
})

test('`permRepliPalier` : un compte LÉGACY retombe sur le palier responsable/admin', () => {
  const item = { roles: ['normal', 'responsable', 'admin'], perm: 'litige_voir', permRepliPalier: true }
  // /auth/me/ ne sert AUCUNE permission à un compte sans rôle fin
  // (UserSerializer.get_permissions → []) : c'est le signal « légacy ».
  assert.equal(estAutoriseEntree(item, 'admin', []), true)
  assert.equal(estAutoriseEntree(item, 'responsable', []), true)
  // …et le palier limité reste refusé (miroir de user.is_responsable).
  assert.equal(estAutoriseEntree(item, 'normal', []), false)
  assert.deepEqual(PALIERS_LEGACY, ['responsable', 'admin'])
})

test('ce n’est PAS un simple ET palier × permission', () => {
  const item = { roles: ['normal', 'responsable', 'admin'], perm: 'litige_voir', permRepliPalier: true }
  const etStrict = (tier, perms) => item.roles.includes(tier) && perms.includes(item.perm)
  // Le cas exact que l'ET casserait : demo_resp / demo_admin (légacy, 0 perm).
  assert.equal(etStrict('responsable', []), false)
  assert.equal(estAutoriseEntree(item, 'responsable', []), true)
})

test('entrée absente/nulle : refusée (jamais une exception)', () => {
  assert.equal(estAutoriseEntree(null, 'admin', []), false)
  assert.equal(estAutoriseEntree(undefined, 'admin', undefined), false)
})

// ── 2. Les points d'appel partagent bien CETTE source unique ────────────────

test('roleLoader délègue à estAutoriseEntree et reçoit permRepliPalier', () => {
  const routerSrc = lire('index.jsx')
  assert.match(routerSrc, /const roleLoader = \(roles, perm, permRepliPalier\)/)
  assert.match(
    routerSrc,
    /estAutoriseEntree\(\{ roles, perm, permRepliPalier \}, tier, permissions\)/,
  )
  // Plus aucune copie locale de la règle dans le routeur.
  assert.doesNotMatch(routerSrc, /roles\.includes\(tier\) && \(!perm/)
  // buildModuleRoutes transmet le drapeau depuis la route du module.config.
  assert.match(lire('moduleRoutes.jsx'), /roleLoader\(r\.roles, r\.perm, r\.permRepliPalier\)/)
})

test('Sidebar, BottomTabBar, appNavItems et buildInstalledApps appellent la MÊME règle', () => {
  const fichiers = [
    lire('..', 'components', 'layout', 'Sidebar.jsx'),
    lire('..', 'components', 'layout', 'BottomTabBar.jsx'),
    lire('..', 'lib', 'apps', 'ActiveAppContext.jsx'),
    lire('..', 'lib', 'apps', 'useInstalledApps.js'),
  ]
  fichiers.forEach((src) => {
    assert.match(src, /estAutoriseEntree/)
    // Aucune ré-implémentation locale du ET palier × permission.
    assert.doesNotMatch(src, /roles\??\.?\.includes\(role\) && \(!it\.perm/)
    assert.doesNotMatch(src, /roles\?\.includes\(role\) && \(!item\.perm/)
  })
})

// ── 3. Un module KEPT déclare perm + permRepliPalier + palier élargi ───────
// (SOLMVP40, 21/09/2026 : litiges/contrats/qhse/gestion_projet/kb — les 5
// modules d'origine de ce bloc — sont sortis du MVP solaire vers
// frontend/parked/. `visites` (VTA6) est le seul module KEPT qui porte
// `permRepliPalier`, avec la même sémantique : un rôle fin est jugé sur la
// SEULE permission, un compte légacy retombe sur le palier.)

test('module « visites » : perm visites_voir + permRepliPalier + palier élargi', () => {
  const src = lire('..', 'features', 'visites', 'module.config.jsx')
  assert.match(src, /perm: 'visites_voir'/)
  assert.match(src, /permRepliPalier: true/)
  assert.match(src, /\['normal', 'responsable', 'admin'\]/)
  // Plus aucune entrée « Ma journée »/wizard/calage gatée UNIQUEMENT sur
  // ['responsable','admin'] (ce serait perdre le repli légacy VTA6).
  assert.doesNotMatch(src, /roles: \['responsable', 'admin'\], perm: 'visites_voir'/)
})

// ── 4. Les cas ET STRICT (perm SANS permRepliPalier) sur des modules KEPT ──
// journal_activite_voir : déclaré à la fois dans `parametres` (la route) et
// `reporting` (l'entrée de nav dupliquée, ODY23) — miroir du test unitaire
// ligne 33-43 : AUCUN des deux ne porte permRepliPalier, donc un rôle fin
// sans la permission reste refusé même au palier responsable/admin, comme le
// serveur (`roleLoader(['normal','responsable','admin'], 'journal_activite_voir')`).

test('parametres : journal_activite_voir est un ET strict (pas de permRepliPalier)', () => {
  const src = lire('..', 'features', 'parametres', 'module.config.jsx')
  assert.match(src, /roles: \['normal', 'responsable', 'admin'\],\s*\n\s*perm: 'journal_activite_voir'/)
  assert.doesNotMatch(src, /permRepliPalier/)
})

test('reporting : journal_activite_voir est un ET strict (pas de permRepliPalier)', () => {
  const src = lire('..', 'features', 'reporting', 'module.config.jsx')
  assert.match(src, /roles: \['normal','responsable','admin'\], perm: 'journal_activite_voir'/)
  assert.doesNotMatch(src, /permRepliPalier/)
})

// La 6ᵉ sous-tâche d'origine (« litiges : le commentaire périmé
// IsResponsableOrAdmin est corrigé ») verrouillait une correction de
// documentation propre au fichier `litiges/module.config.jsx` (SOLMVP40 : ce
// module est désormais dans frontend/parked/). Aucun module KEPT ne porte le
// même commentaire périmé (grep vérifié : `HasPermissionOrLegacy` et « est
// déjà gaté IsResponsableOrAdmin côté serveur » n'apparaissent dans aucun
// `features/*/module.config.jsx` restant) — un ré-ancrage forcerait donc une
// tautologie ; le cas est retiré plutôt que dénaturé.
