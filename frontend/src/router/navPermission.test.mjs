// WIR171 — la règle d'autorisation partagée (roleLoader + Sidebar + mode Apps)
// doit être le MIROIR de la garde serveur `HasPermissionOrLegacy`, pas un ET
// strict entre palier de menu et permission ERP.
//
// Test PUR (node --test) : `navPermission.js` n'a aucune dépendance React /
// Redux, il est donc importable tel quel dans ce worktree sans node_modules.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { itemAutorise } from './navPermission.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const lire = (...p) => readFileSync(path.join(__dirname, ...p), 'utf8')

// Forme exacte déclarée par les 5 module.config du groupe WIR171.
const LECTURE = {
  roles: ['normal', 'responsable', 'admin'],
  perm: 'litige_voir',
  permLegacyRoles: ['responsable', 'admin'],
}

test('Commercial (rôle fin, palier normal) porteur de la permission : AUTORISÉ', () => {
  assert.equal(
    itemAutorise(LECTURE, {
      tier: 'normal', roleNom: 'Commercial', permissions: ['litige_voir'],
    }),
    true,
  )
})

test('rôle fin au palier normal SANS la permission : REFUSÉ (403)', () => {
  assert.equal(
    itemAutorise(LECTURE, {
      tier: 'normal', roleNom: 'Commercial', permissions: ['stock_voir'],
    }),
    false,
  )
})

test('compte HÉRITÉ (aucun rôle fin, permissions vides) : repli palier inchangé', () => {
  // Responsable/admin hérité gardait l'accès avant WIR171 — il le garde.
  assert.equal(itemAutorise(LECTURE, { tier: 'responsable', permissions: [] }), true)
  assert.equal(itemAutorise(LECTURE, { tier: 'admin', permissions: [] }), true)
  // Palier normal hérité n'y avait pas accès — il ne l'a toujours pas.
  assert.equal(itemAutorise(LECTURE, { tier: 'normal', permissions: [] }), false)
})

test('un item SANS permLegacyRoles garde le ET strict (journal_activite_voir)', () => {
  const strict = { roles: ['normal', 'responsable', 'admin'], perm: 'journal_activite_voir' }
  // L'admin HÉRITÉ est délibérément exclu côté serveur (audit/views.py) : la
  // règle partagée ne doit surtout pas lui inventer un repli palier.
  assert.equal(itemAutorise(strict, { tier: 'admin', permissions: [] }), false)
  assert.equal(
    itemAutorise(strict, {
      tier: 'admin', roleNom: 'Directeur', permissions: ['journal_activite_voir'],
    }),
    true,
  )
})

test('un item SANS perm reste gaté par le seul palier', () => {
  const item = { roles: ['responsable', 'admin'] }
  assert.equal(itemAutorise(item, { tier: 'responsable' }), true)
  assert.equal(itemAutorise(item, { tier: 'normal' }), false)
})

test('roleLoader consomme la règle partagée (aucune copie dans index.jsx)', () => {
  const src = lire('index.jsx')
  assert.match(src, /import \{ itemAutorise \} from '\.\/navPermission'/)
  assert.match(src, /const roleLoader = \(roles, perm, permLegacyRoles\)/)
  // Plus aucun ET strict recopié dans le routeur.
  assert.doesNotMatch(src, /roles\.includes\(tier\) && \(!perm \|\|/)
  // Le contrat VX131 (refus → /403) reste intact.
  assert.match(src, /return allowed \? null : redirect\('\/403'\)/)
})

test('les 4 autres consommateurs importent la règle au lieu de la recopier', () => {
  const fichiers = [
    ['..', 'components', 'layout', 'Sidebar.jsx'],
    ['..', 'components', 'layout', 'BottomTabBar.jsx'],
    ['..', 'lib', 'apps', 'ActiveAppContext.jsx'],
    ['..', 'lib', 'apps', 'useInstalledApps.js'],
  ]
  for (const f of fichiers) {
    const src = lire(...f)
    assert.match(src, /itemAutorise/, `${f.join('/')} doit importer itemAutorise`)
    assert.doesNotMatch(
      src, /!item\.perm \|\| permissions\.includes\(item\.perm\)/,
      `${f.join('/')} ne doit plus recopier le ET strict`,
    )
    assert.doesNotMatch(
      src, /!it\.perm \|\| permissions\.includes\(it\.perm\)/,
      `${f.join('/')} ne doit plus recopier le ET strict`,
    )
  }
})

test('les 5 modules déclarent la permission de lecture + le repli palier', () => {
  const attendus = {
    litiges: 'litige_voir',
    contrats: 'contrat_voir',
    qhse: 'qhse_voir',
    gestion_projet: 'projet_voir',
    kb: 'kb_voir',
  }
  for (const [module, perm] of Object.entries(attendus)) {
    const src = lire('..', 'features', module, 'module.config.jsx')
    assert.match(src, new RegExp(`'${perm}'`), `${module} doit déclarer ${perm}`)
    assert.match(src, /permLegacyRoles/, `${module} doit déclarer son repli palier`)
    assert.match(src, /'normal', 'responsable', 'admin'/, `${module} doit élargir ses roles`)
  }
})

test('le commentaire périmé de litiges (IsResponsableOrAdmin) est corrigé', () => {
  const src = lire('..', 'features', 'litiges', 'module.config.jsx')
  assert.match(src, /litige_voir/)
  // Le terme peut rester cité comme HISTORIQUE, jamais comme description du
  // gating actuel (« est déjà gaté »).
  assert.doesNotMatch(src, /est déjà gaté ``IsResponsableOrAdmin`` côté serveur/)
})
