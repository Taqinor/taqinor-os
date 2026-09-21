/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Building2, Users, ClipboardCheck } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   IMMOBILIER (Groupe NTPRO) — configuration du module « Immobilier »
   (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/immobilier/` ; le registre
   `router/moduleRoutes.jsx` la collecte via `import.meta.glob` — SANS toucher
   au routeur, à la Sidebar ni à routes.meta. Les écrans vivent dans
   `src/pages/immobilier/` (chargés en lazy, code-splitting préservé).
   ========================================================================== */

const PatrimoineTree = lazy(() => import('../../pages/immobilier/PatrimoineTree'))
const RentabiliteActif = lazy(() => import('../../pages/immobilier/RentabiliteActif'))
const ChargesPage = lazy(() => import('../../pages/immobilier/ChargesPage'))
// WIR148 — écran de gestion des Baux (signature/révision/dépôt/échéancier/
// quittancement/impayés) : le cycle de vie complet était backend-only.
const BauxPage = lazy(() => import('../../pages/immobilier/BauxPage'))
// WIR147 — écran Locataires (CRUD + résolution client ventes), jusqu'ici sans
// route alors que `LocataireViewSet` existe côté backend.
const LocatairesPage = lazy(() => import('../../pages/immobilier/LocatairesPage'))
// PACT77 — états des lieux d'entrée/sortie (NTPRO15/16), jusque-là sans
// aucun écran. Déposé dans `features/immobilier/` (à côté de ce fichier),
// contrairement aux autres écrans du module (`pages/immobilier/`).
const EtatsLieux = lazy(() => import('./EtatsLieux'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'immobilier',
  order: 60,
  nav: {
    label: 'IMMOBILIER',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Building2),
    items: [
      {
        to: '/immobilier',
        label: 'Patrimoine',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/rentabilite',
        label: 'Rentabilité',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/charges',
        label: 'Charges',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/baux',
        label: 'Baux',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/locataires',
        label: 'Locataires',
        icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/etats-lieux',
        label: 'États des lieux',
        icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/immobilier/rentabilite', 'Rentabilité'],
    ['/immobilier/charges', 'Charges'],
    ['/immobilier/baux', 'Baux'],
    ['/immobilier/locataires', 'Locataires'],
    ['/immobilier/etats-lieux', 'États des lieux'],
    ['/immobilier', 'Immobilier'],
  ],
  sectionLabels: { immobilier: 'Immobilier' },
  routes: [
    { path: '/immobilier', component: PatrimoineTree, roles: ROLES },
    { path: '/immobilier/rentabilite', component: RentabiliteActif, roles: ROLES },
    { path: '/immobilier/charges', component: ChargesPage, roles: ROLES },
    { path: '/immobilier/baux', component: BauxPage, roles: ROLES },
    { path: '/immobilier/locataires', component: LocatairesPage, roles: ROLES },
    { path: '/immobilier/etats-lieux', component: EtatsLieux, roles: ROLES },
  ],
}

export default config
