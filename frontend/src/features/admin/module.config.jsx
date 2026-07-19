/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy Administration vers le registre (phase
   2, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu
   Administration hard-codé, non touché — `buildModuleRoutes` traite `nav`
   comme optionnel via `.filter(Boolean)`, donc « Sidebar sans doublon » tient
   trivialement ici). Les titres de page (`routes.meta.js` →
   `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà déclarés là-bas pour ces
   chemins et ne sont PAS dupliqués ici.

   Gating préservé à l'identique (index.jsx:153-160 `roleLoader`) :
   - `/admin/users`, `/admin/roles` : `roles: ['responsable','admin']`.
   - `/admin/tenants` (SCA22 — console fondateur, le serveur exige superuser) :
     `roles: ['admin']` seul.
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const UsersManagement = lazy(() => import('../../pages/admin/UsersManagement'))
const RolesManagement = lazy(() => import('../../pages/admin/RolesManagement'))
// SCA22 — console fondateur des tenants (le serveur exige superuser : 403 sinon).
const TenantsConsole = lazy(() => import('../../pages/admin/TenantsConsole'))
// WIR134 — écran « Sécurité & Identité » (apps/identity, gouverné IsAdminRole).
const SecuriteIdentitePage = lazy(() => import('../../pages/admin/SecuriteIdentitePage'))
// WIR135 — écran « Gouvernance des accès » (accessreview + rapport roles).
const GouvernanceAccesPage = lazy(() => import('../../pages/admin/GouvernanceAccesPage'))

const config = {
  key: 'admin',
  order: 80,
  routes: [
    { path: '/admin/users', component: UsersManagement, roles: ['responsable', 'admin'] },
    { path: '/admin/roles', component: RolesManagement, roles: ['responsable', 'admin'] },
    { path: '/admin/tenants', component: TenantsConsole, roles: ['admin'] },
    // WIR134 — Sécurité & Identité (admin only : le backend exige IsAdminRole).
    { path: '/admin/securite-identite', component: SecuriteIdentitePage, roles: ['admin'] },
    // WIR135 — Gouvernance des accès (admin only : le backend exige IsAdminRole).
    { path: '/admin/gouvernance-acces', component: GouvernanceAccesPage, roles: ['admin'] },
  ],
}

export default config
