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

const MODULES = [
  ['litiges', 'litige_voir'],
  ['contrats', 'contrat_voir'],
  ['qhse', 'qhse_voir'],
  ['gestion_projet', 'projet_voir'],
  ['kb', 'kb_voir'],
]

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

// ── 3. Les 5 modules déclarent la permission de lecture + le palier élargi ──

MODULES.forEach(([module, perm]) => {
  test(`module « ${module} » : perm ${perm} + permRepliPalier + palier élargi`, () => {
    const src = lire('..', 'features', module, 'module.config.jsx')
    assert.match(src, new RegExp(`perm: '${perm}'`))
    assert.match(src, /permRepliPalier: true/)
    assert.match(src, /\['normal', 'responsable', 'admin'\]/)
    // Plus aucune entrée gatée UNIQUEMENT sur ['responsable','admin'].
    assert.doesNotMatch(src, /roles: \['responsable', 'admin'\]/)
  })
})

test('litiges : le commentaire périmé « IsResponsableOrAdmin » est corrigé', () => {
  const src = lire('..', 'features', 'litiges', 'module.config.jsx')
  assert.match(src, /HasPermissionOrLegacy/)
  // Le mot peut rester dans l'explication du correctif, mais plus comme la
  // description ACTUELLE de la garde serveur.
  assert.doesNotMatch(src, /est déjà gaté ``IsResponsableOrAdmin`` côté serveur/)
})
