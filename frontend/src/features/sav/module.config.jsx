/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { Boxes, Wrench, LayoutDashboard } from 'lucide-react'

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

   ODY19 — passe « app complète ». Deux ajouts :
   1) `/sav/cockpit` (SavCockpitPage, premier item de nav) : porte d'entrée
      de l'app — ModuleHero VX15 + actions rapides + KPI (réutilise
      `savApi.getSavFileAction()`, ZSAV6, déjà éprouvé par SavActionBoardPage
      — zéro nouvel endpoint). `/sav` N'A PAS été repointé vers ce cockpit :
      trop de points d'entrée EXISTANTS visent `/sav` pour ouvrir la liste de
      tickets précise (Dashboard « Mes activités », Rapports.jsx,
      lib/search/entityRoutes ROUTE.ticket, OwnerChain, RelationCounters,
      pages/CalendarPage, activities/MesActivitesPage) — aucun n'est dans le
      périmètre fichiers de cette tâche, donc `/sav` reste TicketsPage et le
      cockpit est additif.
   2) DÉCISION Monitoring (flotte solaire/CO2/analytics, `pages/monitoring/`) :
      `features/monitoring/module.config.jsx` N'EST PAS créé ici. Ces écrans
      (`/production*`) sont DÉJÀ rattachés — depuis la migration ARC54/ODX7,
      donc avant ce plan ODY — à `features/installations/module.config.jsx`
      (app Chantiers), section nav CHANTIERS, zéro route orpheline vérifiée.
      `features/installations/module.config.jsx` est un fichier d'une AUTRE
      lane ODY (ODY18, @lane frontend/app-chantiers) et donc hors périmètre
      fichiers de cette tâche : le déplacer créerait soit une double
      inscription de route (si copié dans un nouveau module `monitoring` sans
      retrait côté installations — interdit, « jamais un 2ᵉ registre »), soit
      une modification d'un fichier appartenant à une autre lane (interdit).
      Le host app retenu pour Monitoring reste donc Installations/Chantiers —
      cohérent thématiquement (parc terrain post-installation) et déjà
      complet ; SAV n'obtient PAS de tuile Monitoring séparée.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
// ODY19 — cockpit de l'app (porte d'entrée), en tête de nav.
const SavCockpitPage = lazy(() => import('../../pages/sav/SavCockpitPage'))
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
    // ODY19 — vérifié VX8 : accent cohérent avec les autres apps « risque/
    // urgence » (litiges, qhse) — un ticket SAV ouvert EST une urgence client.
    accent: 'destructive',
    items: [
      // ODY19 — cockpit de l'app en tête de nav (pas de `k` : clé i18n non
      // créée, `tr(key, label)` retombe déjà sur `label` quand `key` est
      // absent — cf. Sidebar.jsx `tr`).
      { to: '/sav/cockpit',          label: 'Cockpit',          icon: navIcon(LayoutDashboard), roles: ['normal','responsable','admin'] },
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
    { path: '/sav/cockpit', component: SavCockpitPage },
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
