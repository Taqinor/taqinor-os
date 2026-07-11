/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC48 — Migration des routes legacy SAV (Après-vente) vers le registre.
   ----------------------------------------------------------------------------
   Pilote ARC48 (avec `stock`) : `index.jsx` gardait ~90 routes hard-codées
   pour les apps métier legacy après ODX7 (qui ne migre que la NAV de
   Sidebar.jsx). Ce fichier migre les ROUTES SEULES (aucune section `nav` :
   Sidebar.jsx garde son menu Après-vente hard-codé, non touché —
   `buildModuleRoutes` traite `nav` comme optionnel via `.filter(Boolean)`,
   donc « Sidebar sans doublon » tient trivialement ici). Les titres de page
   (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà
   déclarés là-bas pour `/equipements` et `/sav*` et ne sont PAS dupliqués ici.

   Gating préservé à l'identique (index.jsx:172-179 `roleLoader`) :
   - `/equipements`, `/sav`, `/sav/contrats`, `/sav/warranty-claims`,
     `/sav/alarmes`, `/sav/kb` : authLoader (aucun `roles` déclaré ci-dessous
     → `buildModuleRoutes` applique `authLoader`, cf. router/moduleRoutes.jsx).
   - `/sav/parametres` (ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23), `/sav/sla-rapport`
     (XSAV8), `/sav/action-requise` (ZSAV6) : `roles: ['responsable','admin']`,
     aucune `perm` — identique à `roleLoader(['responsable','admin'])`.
   ========================================================================== */

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
