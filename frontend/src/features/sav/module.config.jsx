/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { Boxes, Wrench } from 'lucide-react'

/* ============================================================================
   ARC48 — Migration des routes legacy SAV (Après-vente) vers le registre.
   ----------------------------------------------------------------------------
   Pilote ARC48 (avec `stock`) : `index.jsx` gardait ~90 routes hard-codées
   pour les apps métier legacy avant ODX7 (qui migre la NAV de Sidebar.jsx,
   voir la section `nav` plus bas). Ce fichier migre les ROUTES. Les titres de
   page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà
   déclarés là-bas pour `/equipements` et `/sav*` et ne sont PAS dupliqués ici.

   Gating préservé à l'identique (index.jsx:172-179 `roleLoader`) :
   - `/equipements`, `/sav`, `/sav/contrats`, `/sav/warranty-claims`,
     `/sav/alarmes`, `/sav/kb` : authLoader (aucun `roles` déclaré ci-dessous
     → `buildModuleRoutes` applique `authLoader`, cf. router/moduleRoutes.jsx).
   - `/sav/parametres` (ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23), `/sav/sla-rapport`
     (XSAV8), `/sav/action-requise` (ZSAV6) : `roles: ['responsable','admin']`,
     aucune `perm` — identique à `roleLoader(['responsable','admin'])`.

   ODX7 — la section `nav` ci-dessous est le littéral APRÈS-VENTE qui vivait
   dans `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (regroupement
   fonctionnel only, zéro changement visuel). Sidebar lit désormais cette
   section par clé (`navFor('sav')`), à la même place dans l'ordre d'affichage.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const EquipementsPage = lazy(() => import('../../pages/sav/EquipementsPage'))
const TicketsPage = lazy(() => import('../../pages/sav/TicketsPage'))
// ContratsMaintenance exporte un named `Component` (pas de default export).
const ContratsMaintenance = lazy(() =>
  import('../../pages/sav/ContratsMaintenance').then((m) => ({ default: m.Component })),
)
// FG83 — réclamations garantie fournisseur (flux RMA).
const WarrantyClaimsPage = lazy(() => import('../../pages/sav/WarrantyClaimsPage'))
// ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23 — référentiels SAV (responsable/admin, écriture gardée côté serveur).
const SavParametresPage = lazy(() => import('../../pages/sav/SavParametresPage'))
// XSAV8 — rapport de conformité SLA + KPI avancés.
const SavSlaReportPage = lazy(() => import('../../pages/sav/SavSlaReportPage'))
// Alarmes onduleur (FG280).
const SavAlarmesPage = lazy(() => import('../../pages/sav/SavAlarmesPage'))
// ZSAV6 — file d'action (tickets ouverts groupés par action attendue).
const SavActionBoardPage = lazy(() => import('../../pages/sav/SavActionBoardPage'))
// FG87 — base de connaissances SAV (articles KB).
const KbArticlesPage = lazy(() => import('../../pages/sav/KbArticlesPage'))

const RESPONSABLE_ADMIN = ['responsable', 'admin']

const config = {
  key: 'sav',
  order: 30,
  nav: {
    label: 'APRÈS-VENTE', labelKey: 'nav.section.apres_vente',
    accent: 'destructive',
    items: [
      { to: '/equipements',          label: 'Équipements',      k: 'nav.equipements', icon: navIcon(Boxes), roles: ['normal','responsable','admin'] },
      { to: '/sav',                  label: 'Tickets SAV',      k: 'nav.tickets_sav', icon: navIcon(Wrench),         roles: ['normal','responsable','admin'] },
      { to: '/sav/contrats',         label: 'Contrats maintenance', k: 'nav.contrats_maintenance', icon: navIcon(Wrench), roles: ['responsable','admin'] },
      { to: '/sav/warranty-claims',  label: 'Garanties fournisseur (RMA)', k: 'nav.warranty_claims', icon: navIcon(Wrench), roles: ['responsable','admin'] },
      { to: '/sav/kb',               label: 'Base de connaissances SAV', k: 'nav.sav_kb', icon: navIcon(Wrench), roles: ['normal','responsable','admin'] },
      { to: '/sav/alarmes',          label: 'Alarmes onduleur',  k: 'nav.sav_alarmes', icon: navIcon(Wrench), roles: ['normal','responsable','admin'] },
      { to: '/sav/action-requise',   label: 'Action requise',    k: 'nav.sav_action_requise', icon: navIcon(Wrench), roles: ['responsable','admin'] },
      { to: '/sav/sla-rapport',      label: 'Rapport SLA SAV',   k: 'nav.sav_sla_rapport', icon: navIcon(Wrench), roles: ['responsable','admin'] },
      { to: '/sav/parametres',       label: 'Paramètres SAV',    k: 'nav.sav_parametres', icon: navIcon(Wrench), roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/equipements', component: EquipementsPage },
    { path: '/sav', component: TicketsPage },
    { path: '/sav/contrats', component: ContratsMaintenance },
    { path: '/sav/warranty-claims', component: WarrantyClaimsPage },
    { path: '/sav/parametres', component: SavParametresPage, roles: RESPONSABLE_ADMIN },
    { path: '/sav/sla-rapport', component: SavSlaReportPage, roles: RESPONSABLE_ADMIN },
    { path: '/sav/alarmes', component: SavAlarmesPage },
    { path: '/sav/action-requise', component: SavActionBoardPage, roles: RESPONSABLE_ADMIN },
    { path: '/sav/kb', component: KbArticlesPage },
  ],
}

export default config
