import { describe, it, expect } from 'vitest'
import { NAV_SECTIONS } from '../components/layout/Sidebar'

/* ============================================================================
   YRBAC10 — Test de DÉRIVE gating frontend ↔ backend.
   ----------------------------------------------------------------------------
   Le backend expose (admin) `GET /api/django/roles/permission-catalog/` avec
   une carte route→rôles RÉELLEMENT enforced, dérivée de la matrice canonique
   YRBAC2 (`core/rbac_matrix.py`). Ce test verrouille la PARITÉ : pour les
   routes de RÉFÉRENCE (crm/ventes/stock, la partie verte de la matrice), il
   compare le gating de la NAV (Sidebar.NAV_SECTIONS, source du menu) au verdict
   backend et échoue sur tout décalage — un lien caché pour un palier alors que
   le backend ouvre l'endpoint à tous (ou l'inverse).

   Le test ne peut pas importer la matrice Python ; il en fige le SOUS-ENSEMBLE
   de référence sous forme de contrat versionné. Le pendant backend
   (`apps/roles/tests_permission_catalog.py`) prouve, lui, que ce contrat est
   bien DÉRIVÉ de `core.rbac_matrix` (aucune liste parallèle) — les deux tests
   se rejoignent sur la même matrice.

   ROBUSTESSE (anti-faux-vert) : si un chemin de référence disparaît de la nav,
   le test échoue (la route n'est plus gatée là où le backend l'enforce encore).
   ========================================================================== */

// Contrat de référence : verdict backend attendu (miroir du sous-ensemble
// crm/ventes/stock de core.rbac_matrix — GET de liste ouverts à TOUS les rôles
// canoniques). `allRoles: true` = aucun palier ne doit être exclu dans la nav.
const BACKEND_LIST_ROUTES = [
  { path: '/crm', allRoles: true },        // GET /crm/clients/  → _all(ALLOW)
  { path: '/crm/leads', allRoles: true },  // GET /crm/leads/    → _all(ALLOW)
  { path: '/ventes/devis', allRoles: true }, // GET /ventes/devis/ → _all(ALLOW)
  { path: '/ventes/factures', allRoles: true }, // GET /ventes/factures/
  { path: '/stock', allRoles: true },      // GET /stock/produits/ → _all(ALLOW)
]

// Les 3 paliers machine du frontend (auth.role). « Tous les rôles » côté nav =
// l'item est visible pour les trois paliers.
const ALL_TIERS = ['normal', 'responsable', 'admin']

// Index plat des items de nav par chemin `to` → liste de paliers `roles`.
function navRolesByPath() {
  const map = {}
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      map[item.to] = item.roles
    }
  }
  return map
}

describe('YRBAC10 — parité gating nav ↔ backend (routes de référence)', () => {
  const navMap = navRolesByPath()

  it('chaque route de référence backend existe bien dans la nav (pas de trou de gating)', () => {
    for (const route of BACKEND_LIST_ROUTES) {
      expect(navMap[route.path], `route « ${route.path} » absente de la nav`)
        .toBeTruthy()
    }
  })

  it('backend ouvre à TOUS les rôles ⇒ la nav ne cache la route à AUCUN palier', () => {
    for (const route of BACKEND_LIST_ROUTES) {
      if (!route.allRoles) continue
      const navRoles = navMap[route.path]
      // Décalage = un palier exclu côté nav alors que le backend l'autorise.
      for (const tier of ALL_TIERS) {
        expect(
          navRoles.includes(tier),
          `DÉRIVE : « ${route.path} » est caché pour le palier « ${tier} » ` +
          `alors que le backend (matrice YRBAC2) l'ouvre à tous les rôles`,
        ).toBe(true)
      }
    }
  })
})
