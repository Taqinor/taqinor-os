/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy Paramètres vers le registre (phase 2,
   dernière app du lot, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu
   Administration/Paramètres hard-codé, non touché — `buildModuleRoutes` traite
   `nav` comme optionnel via `.filter(Boolean)`, donc « Sidebar sans doublon »
   tient trivialement ici). Les titres de page (`routes.meta.js` →
   `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà déclarés là-bas pour ces
   chemins et ne sont PAS dupliqués ici. `/journal` est inclus ici (regroupé
   avec Paramètres dans la section ADMINISTRATION de Sidebar.jsx et dans le
   même bloc legacy de index.jsx) — aucune des 6 apps citées par ARC54 ne le
   possède plus naturellement.

   Gating préservé à l'identique (index.jsx:153-160 `roleLoader`) :
   - `/parametres`, `/parametres/alertes-kpi` (XPLT6) :
     `roles: ['responsable','admin']`, aucune `perm`.
   - `/parametres/export` : authLoader (aucun `roles` déclaré ci-dessous) —
     PRÉSERVÉ TEL QUEL malgré le commentaire N97 (« réservé à l'administrateur,
     l'endpoint backend exige le rôle admin ») : le loader CLIENT réel dans
     index.jsx était bien `authLoader` sans roleLoader, la garde effective est
     côté serveur.
   - `/parametres/notifications` : authLoader.
   - `/journal` : `roles: ['normal','responsable','admin']` ET
     `perm: 'journal_activite_voir'` — reflète EXACTEMENT
     `roleLoader(['normal','responsable','admin'], 'journal_activite_voir')`.
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const ParametresEntreprise = lazy(() => import('../../pages/parametres/ParametresEntreprise'))
const ExportSauvegarde = lazy(() => import('../../pages/parametres/ExportSauvegarde'))
const NotificationsPreferences = lazy(() => import('../../pages/parametres/NotificationsPreferences'))
// XPLT6 — CRUD des alertes de seuil sur KPI agrégés (réservé responsable/admin,
// reflète `IsResponsableOrAdmin` côté backend).
const KpiAlertesPage = lazy(() => import('../../pages/parametres/KpiAlertesPage'))
const Journal = lazy(() => import('../../pages/Journal'))
// NTMKT10 — Paramètres → Marketing : domaine d'envoi SPF/DKIM/DMARC (XMKT33).
// Composant déposé sous `features/parametres/` (pas `pages/parametres/`) —
// Files list de NTMKT10 dans docs/plans/PLAN_CRM_VENTES.md.
const DomaineEnvoi = lazy(() => import('./DomaineEnvoi'))
// NTUX23 — rapport « configuration des vues actives » (réservé responsable/
// admin, reflète `IsResponsableOrAdmin` côté backend — `toutes-company/`/
// `export-xlsx/` de SavedViewViewSet).
const VuesConfigurationPage = lazy(() => import('../../pages/parametres/VuesConfigurationPage'))

const config = {
  key: 'parametres',
  order: 90,
  routes: [
    { path: '/parametres', component: ParametresEntreprise, roles: ['responsable', 'admin'] },
    { path: '/parametres/export', component: ExportSauvegarde },
    { path: '/parametres/notifications', component: NotificationsPreferences },
    { path: '/parametres/alertes-kpi', component: KpiAlertesPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/marketing', component: DomaineEnvoi, roles: ['responsable', 'admin'] },
    { path: '/parametres/vues', component: VuesConfigurationPage, roles: ['responsable', 'admin'] },
    {
      path: '/journal',
      component: Journal,
      roles: ['normal', 'responsable', 'admin'],
      perm: 'journal_activite_voir',
    },
  ],
}

export default config
