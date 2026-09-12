/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants,
   le fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes`). */
import { lazy } from 'react'
import { ClipboardCheck, CalendarCheck, CalendarPlus, ListChecks, Microscope } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   VTA8 — Module frontend « Visites terrain » (apps.visites), SORTI du CRM.
   ----------------------------------------------------------------------------
   Pourquoi une app à part : l'utilisateur de ces écrans est un COMMERCIAL
   TERRAIN qui n'a aucun accès au CRM (rôle « Commercial terrain », VTA4). Tant
   que les 4 écrans vivaient dans `features/crm/module.config.jsx`, ouvrir une
   visite voulait dire ouvrir l'app CRM — impossible pour lui. Clé `visites`
   IDENTIQUE au manifeste backend (VTA1, `apps/visites/apps.py` →
   `module_manifest.key`), vérifiée par `scripts/check_modules.py`.

   Accueil de l'app = « Ma journée » à `/visites` (VTA9). PAS `/ma-journee` :
   ce chemin appartient déjà au module `installations` (journée du technicien
   d'intervention) — deux apps, deux journées, deux chemins.

   Gating : `visites_voir` est large (tout commercial voit SES visites — le
   serveur impose `commercial=self` sans `visites_valider`, VTA6). « Toutes les
   visites » et « Revue technique » demandent `visites_valider` : ce sont les
   vues d'ÉQUIPE (et le feu vert bureau d'études). Même patron que
   `veille_ao` : `roles` reflète le palier, `perm` porte la permission fine
   que le serveur vérifie réellement.
   ========================================================================== */

const MaJourneePage = lazy(() => import('../../pages/visites/MaJourneePage'))
const VisitesListPage = lazy(() => import('../../pages/visites/VisitesListPage'))
const VisiteWizardPage = lazy(() => import('../../pages/visites/VisiteWizardPage'))
const VisiteBureauEtudesPage = lazy(() => import('../../pages/visites/VisiteBureauEtudesPage'))
const PlanifierVisitePage = lazy(() => import('../../pages/visites/PlanifierVisitePage'))
const CalageToitPage = lazy(() => import('../../pages/visites/CalageToitPage'))

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Palier : un commercial terrain relève du palier 'normal'.
const ROLES = ['normal', 'responsable', 'admin']
const ROLES_VALIDER = ['responsable', 'admin']

const config = {
  key: 'visites',
  // Juste après `crm` (40) et `portail` (41) : la visite est la suite du lead.
  order: 42,
  nav: {
    icon: appGlyph(ClipboardCheck),
    label: 'VISITES',
    accent: 'foret',
    items: [
      {
        to: '/visites',
        label: 'Ma journée',
        icon: navIcon(CalendarCheck),
        roles: ROLES,
        perm: 'visites_voir',
        permRepliPalier: true,
      },
      {
        to: '/visites/toutes',
        label: 'Toutes les visites',
        icon: navIcon(ListChecks),
        roles: ROLES_VALIDER,
        perm: 'visites_valider',
      },
      {
        // VTA16 — administration légère : le chemin bureau sans ouvrir le CRM.
        to: '/visites/planifier',
        label: 'Planifier une visite',
        icon: navIcon(CalendarPlus),
        roles: ROLES_VALIDER,
        perm: 'visites_valider',
      },
      {
        to: '/visites/revue',
        label: 'Revue technique',
        icon: navIcon(Microscope),
        roles: ROLES_VALIDER,
        perm: 'visites_valider',
      },
    ],
  },
  titles: [
    ['/visites/toutes', 'Visites — Toutes les visites'],
    ['/visites/planifier', 'Visites — Planifier une visite'],
    ['/visites/revue', 'Visites — Revue technique'],
    ['/visites/', 'Visites — Visite terrain'],
    ['/visites', 'Visites — Ma journée'],
  ],
  sectionLabels: { visites: 'Visites' },
  routes: [
    // VTA9 — accueil de l'app : la journée de l'utilisateur (jour + retards).
    { path: '/visites', component: MaJourneePage, roles: ROLES, perm: 'visites_voir', permRepliPalier: true },
    { path: '/visites/toutes', component: VisitesListPage, roles: ROLES_VALIDER, perm: 'visites_valider' },
    { path: '/visites/planifier', component: PlanifierVisitePage, roles: ROLES_VALIDER, perm: 'visites_valider' },
    { path: '/visites/revue', component: VisiteBureauEtudesPage, roles: ROLES_VALIDER, perm: 'visites_valider' },
    // Wizard d'une visite : atteint depuis « Ma journée »/la liste/la fiche
    // lead, jamais depuis la nav (route dynamique, hors garde « zéro route
    // orpheline », comme `/crm/leads/:id`).
    { path: '/visites/:id', component: VisiteWizardPage, roles: ROLES, perm: 'visites_voir', permRepliPalier: true },
    // VT11 — calage du toit réaliste, atteint depuis le wizard (catégorie
    // toiture).
    { path: '/visites/:id/calage', component: CalageToitPage, roles: ROLES, perm: 'visites_voir', permRepliPalier: true },
  ],
}

export default config
