/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { MapPin, ListChecks } from 'lucide-react'

/* ============================================================================
   ARC54 — Migration des routes legacy Paramètres vers le registre (phase 2,
   dernière app du lot, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only pour les entrées historiques (aucune section `nav` pour elles :
   Sidebar.jsx garde son menu Administration/Paramètres hard-codé, non touché —
   `buildModuleRoutes` traite `nav` comme optionnel via `.filter(Boolean)`, donc
   « Sidebar sans doublon » tient trivialement ici). Les titres de page
   (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà
   déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici. `/journal`
   est inclus ici (regroupé avec Paramètres dans la section ADMINISTRATION de
   Sidebar.jsx et dans le même bloc legacy de index.jsx) — aucune des 6 apps
   citées par ARC54 ne le possède plus naturellement.

   WIR13 — Territoires (`Territoires.jsx`, NTCRM3) était construit/testé mais
   monté nulle part (ni route, ni menu). `parametres` n'étant PAS l'une des 6
   clés legacy (cf. `LEGACY_NAV_KEYS` dans Sidebar.jsx), une section `nav`
   posée ici est auto-collectée par le registre générique (`moduleNavSections`,
   router/moduleRoutes.jsx) et insérée juste avant ADMINISTRATION — même
   mécanisme que `/parametres/marketing` (nav déclarée dans
   `features/marketing/module.config.jsx`).

   WIR14 — même mécanisme pour Playbooks (`Playbooks.jsx`, NTCRM13, CRUD des
   playbooks/étapes/tâches par stage STAGES.py) : construit/testé, monté nulle
   part. Deux liens dans la section `nav` ci-dessous ; les autres routes
   ci-dessus restent routes-only, comme documenté ci-dessus.

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
// WIR13/NTCRM3 — Territoires (règles d'affectation auto des leads entrants
// par zone/segment/secteur) — réservé responsable/admin, comme documenté en
// tête de `Territoires.jsx` (le backend applique déjà le RBAC réel).
const Territoires = lazy(() => import('./Territoires'))
// WIR14/NTCRM13 — Playbooks (CRUD des playbooks/étapes/tâches par stage) —
// même gating responsable/admin que les autres écrans de configuration CRM.
const Playbooks = lazy(() => import('./Playbooks'))
// WIR8 — Paramètres → Hôtellerie : taxe de séjour (singleton société, réservé
// responsable/admin — reflète `IsResponsableOrAdmin` côté backend).
const TaxeSejourHospitality = lazy(() => import('./TaxeSejourHospitality'))
// WIR26 — Paramètres → Achats (`stock.AchatsParametres`, singleton par
// société) : conformité (XPUR1), RAS-TVA (XPUR2), tolérances 3-voies
// (XPUR10). Écriture réservée responsable/admin (le backend applique déjà
// `stock_modifier`/legacy responsable ; lecture ouverte à tout rôle).
const AchatsParametresPage = lazy(() => import('../../pages/parametres/AchatsParametresPage'))

const config = {
  key: 'parametres',
  order: 90,
  nav: {
    label: 'PARAMÈTRES',
    accent: 'nuit',
    items: [
      { to: '/parametres/territoires', label: 'Territoires', icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/parametres/playbooks', label: 'Playbooks', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
    ],
  },
  routes: [
    { path: '/parametres', component: ParametresEntreprise, roles: ['responsable', 'admin'] },
    { path: '/parametres/export', component: ExportSauvegarde },
    { path: '/parametres/notifications', component: NotificationsPreferences },
    { path: '/parametres/alertes-kpi', component: KpiAlertesPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/marketing', component: DomaineEnvoi, roles: ['responsable', 'admin'] },
    { path: '/parametres/vues', component: VuesConfigurationPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/territoires', component: Territoires, roles: ['responsable', 'admin'] },
    { path: '/parametres/playbooks', component: Playbooks, roles: ['responsable', 'admin'] },
    { path: '/parametres/hospitality/taxe-sejour', component: TaxeSejourHospitality, roles: ['responsable', 'admin'] },
    { path: '/parametres/achats', component: AchatsParametresPage, roles: ['responsable', 'admin'] },
    {
      path: '/journal',
      component: Journal,
      roles: ['normal', 'responsable', 'admin'],
      perm: 'journal_activite_voir',
    },
  ],
}

export default config
