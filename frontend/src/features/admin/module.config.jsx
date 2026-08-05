/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { LayoutDashboard } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   ARC54 — Migration des routes legacy Administration vers le registre (phase
   2, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Les ROUTES restent routes-only ici (aucun changement — leurs entrées de
   menu vivent désormais dans `features/parametres/module.config.jsx`, voir
   ODY23 ci-dessous, exactement comme Journal pointe vers une route déclarée
   dans `reporting`). Les titres de page (`routes.meta.js` →
   `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà déclarés là-bas pour ces
   chemins et ne sont PAS dupliqués ici.

   ODY23 — « Dashboard → app Tableau de bord » (distincte de l'app
   Paramètres qui absorbe le reste d'Administration, cf.
   `features/parametres/module.config.jsx`). `pages/Dashboard.jsx` et sa route
   `/dashboard` restent HORS PÉRIMÈTRE (propriété ODY27, déjà un cockpit VX15
   ModuleHero) : ce fichier n'ajoute qu'un item de nav qui y pointe — aucune
   route nouvelle, aucun fichier touché en dehors de celui-ci. Choix assumé
   (à revoir si le fondateur préfère un fichier `features/dashboard/` dédié,
   hors périmètre ODY23 qui ne peut créer de nouveau module.config) : la clé
   `admin` de ce fichier porte donc DEUX rôles au sens ERP-Apps — ses `routes`
   restent des écrans d'Administration, sa `nav` (nouvelle) représente
   l'app Tableau de bord. Un futur renommage de fichier/clé est un
   changement mécanique, pas une restructuration — cf. rapport de tâche ODY23.

   Gating préservé à l'identique (index.jsx:153-160 `roleLoader`) :
   - `/admin/users`, `/admin/roles` : `roles: ['responsable','admin']`.
   - `/admin/tenants` (SCA22 — console fondateur, le serveur exige superuser) :
     `roles: ['admin']` seul.
   - `/dashboard` : `authLoader` (aucun rôle — ouvert à tout authentifié,
     index.jsx:339, INCHANGÉ).
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
// NTADM32 — assistant « Demander une session support » (le serveur exige
// `is_taqinor_support` : 403 sinon).
const ImpersonationWizard = lazy(() => import('../../pages/admin/ImpersonationWizard'))
// NTADM22 — consentement du tenant : autoriser / refuser une session support.
const ImpersonationConsentement = lazy(() => import('../../pages/admin/ImpersonationConsentement'))

const config = {
  key: 'admin',
  order: 80,
  nav: {
    label: 'TABLEAU DE BORD', labelKey: 'nav.section.dashboard',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(LayoutDashboard),
    // VX8 — l'une des 7 clés --module-accent-* réelles de tokens.css (pas
    // 'primary', qui n'en fait pas partie malgré son usage dans quelques
    // module.config verticaux préexistants).
    accent: 'azur',
    items: [
      { to: '/dashboard', label: 'Tableau de bord', k: 'nav.dashboard', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['normal', 'responsable', 'admin'] },
    ],
  },
  routes: [
    { path: '/admin/users', component: UsersManagement, roles: ['responsable', 'admin'] },
    { path: '/admin/roles', component: RolesManagement, roles: ['responsable', 'admin'] },
    { path: '/admin/tenants', component: TenantsConsole, roles: ['admin'] },
    // WIR134 — Sécurité & Identité (admin only : le backend exige IsAdminRole).
    { path: '/admin/securite-identite', component: SecuriteIdentitePage, roles: ['admin'] },
    // WIR135 — Gouvernance des accès (admin only : le backend exige IsAdminRole).
    { path: '/admin/gouvernance-acces', component: GouvernanceAccesPage, roles: ['admin'] },
    // NTADM32 — demande de session support (le serveur exige is_taqinor_support).
    { path: '/admin/impersonation/demander', component: ImpersonationWizard, roles: ['admin'] },
    // NTADM22 — consentement du tenant (le serveur exige l'Administrateur).
    { path: '/admin/impersonation', component: ImpersonationConsentement, roles: ['admin'] },
  ],
}

export default config
