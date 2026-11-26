import { createElement, lazy } from 'react'
import {
  CalendarDays, Users, Target, Map, UserPlus, TrendingUp, LayoutDashboard, Globe,
  Swords, Trophy, CalendarClock, ClipboardCheck, Radar,
} from 'lucide-react'
import { REPLI_ROLES } from '../../router/moduleGating'

/* ============================================================================
   ARC54 — Migration des routes legacy CRM vers le registre (phase 2, après les
   pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes migrées ici (section `nav` ajoutée depuis par ODX7, voir plus bas).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   ODX7 — la section `nav` ci-dessous est le littéral CRM qui vivait dans
   `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (regroupement
   fonctionnel only, zéro changement visuel). Sidebar lit désormais cette
   section par clé (`navFor('crm')`), à la même place dans l'ordre d'affichage.
   ========================================================================== */

const navIcon = (Comp) => createElement(Comp, { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' })

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
// ODY15 — Cockpit CRM : porte d'entrée de l'app (ModuleHero + actions + KPI).
const CrmCockpit = lazy(() => import('../../pages/crm/CrmCockpit'))
const ClientList = lazy(() => import('../../pages/crm/ClientList'))
const LeadsPage = lazy(() => import('../../pages/crm/leads/LeadsPage'))
// VX22 — fiche lead adressable (deep-link, F5, ctrl-clic nouvel onglet).
const LeadDetailPage = lazy(() => import('../../pages/crm/leads/LeadDetailPage'))
const MesActivitesPage = lazy(() => import('../../pages/activities/MesActivitesPage'))
const CalendarPage = lazy(() => import('../../pages/CalendarPage'))
const CartePage = lazy(() => import('../../pages/CartePage'))
const ParrainagePage = lazy(() => import('../../pages/crm/ParrainagePage'))
// QX16 — rejeu des payloads leads site web (« jamais perdre un lead »).
const WebsiteLeadPayloadsPage = lazy(() => import('../../pages/crm/WebsiteLeadPayloadsPage'))
// WIR15/NTCRM7 — vue manager Forecast (Commit/Best Case/Pipeline/Total par
// commercial + sous-total équipe) — construite/testée, montée nulle part.
// Aucun travail backend : `forecast-entries/`/`forecast/rollup/`/
// `forecast/historique/` existent déjà (`IsAnyRole`, filtre équipe côté
// serveur pour un Responsable non-Admin).
const ForecastPage = lazy(() => import('../../pages/crm/forecast/ForecastPage'))
// WIR99/DC12 — création/édition du profil site réutilisable par client
// (`SiteProfile`), qui pré-remplit le générateur de devis SANS lead.
const SiteProfilePage = lazy(() => import('../../pages/crm/SiteProfilePage'))
// PACT103 — Concurrents sur affaires perdues (FG242) : aucun écran, y
// compris le popover « perdu » existant, ne l'appelait avant ce lot.
const ConcurrentsPertePage = lazy(() => import('./ConcurrentsPerte'))
// NTCRM24 — leaderboard des défis d'équipe (NTCRM23), visible de toute l'équipe.
const DefisPage = lazy(() => import('../../pages/crm/defis/DefisPage'))
// MRY31 — écran « Suivi des relances » : les touches de cadence par jour et
// leur statut (au-delà de la file « aujourd'hui + retard » du Cockpit).
const RelancesSuiviPage = lazy(() => import('../../pages/crm/RelancesSuiviPage'))
// VIS1 (fondateur 14/09/2026) — écran « Visiteurs & alertes » : la place pour
// revoir qui a ouvert quels devis/liens externes, et marquer un appareil
// équipe pour l'exclure du comptage/des alertes anti-fraude.
const VisiteursPage = lazy(() => import('../../pages/crm/VisiteursPage'))
// Attribution des leads par le responsable d'équipe (fondateur 27/10/2026).
const AttributionLeadsPage = lazy(() => import('../../pages/crm/AttributionLeadsPage'))
const CockpitEquipePage = lazy(() => import('../../pages/crm/CockpitEquipePage'))
// VTA8 — les 4 écrans de visite technique terrain ont QUITTÉ le CRM : ils
// vivent dans l'app autonome « Visites » (`features/visites/module.config.jsx`,
// routes `/visites/...`), parce que le commercial terrain qui les utilise n'a
// aucun accès au CRM. Ne les remonter ici sous aucun prétexte.

/* T4-X8-016 (lot 8) — les règles de lecture du CRM, lues À LA FOIS par l'entrée de menu et par sa route
   (`router/moduleGating.js::estAutoriseEntree`, la même fonction pour la Sidebar, le lanceur et `roleLoader`).
   Chaque écran porte la garde de SA première lecture serveur — jamais plus stricte, jamais plus large :
   • `LECTURE_CRM` (`crm_voir`) : Leads (`HasPermissionOrLegacy('crm_voir')`, `apps/crm/views.py::LeadViewSet`),
     Concurrents (rien ne s'y fait sans la recherche de leads, même garde ; la liste des concurrents ne se lit
     qu'après), Cockpit (liste des leads + `DroitDeLaGrille('crm_voir')`), Suivi des relances
     (`DroitDeLaGrille('crm_voir')` et `HasPermissionOrLegacy('crm_voir')`, `apps/crm/cadence_views.py`) ;
   • `LECTURE_MODULE_CRM` (`permModule: 'crm'`, miroir de `LectureDuModule` : n'importe quel code `crm_*`, ou le
     palier admin) : Défis (`clients_views.py::DefiViewSet`), Parrainage (`ParrainageViewSet`, liste + stats),
     Profils site (`views.py::SiteProfileViewSet`) — un rôle personnalisé `crm_creer` sans `crm_voir` les lit.
   Un compte LÉGACY (aucune permission servie) garde le palier de l'entrée (`REPLI_ROLES`). Le Technicien (aucun
   `crm_*`) ne voit plus ces sept entrées, et leur route le renvoie sur « Accès refusé » (`/403`) AVANT que la
   page ne lance une seule requête. Inchangées : Calendrier, Clients, Forecast, Carte, Visiteurs, Attribution,
   Cockpit d'équipe ; la fiche `/crm/leads/:id` n'est pas touchée. */
const ROLES_CRM = ['normal', 'responsable', 'admin']
const LECTURE_CRM = { roles: ROLES_CRM, perm: 'crm_voir', permRepliPalier: REPLI_ROLES }
const LECTURE_MODULE_CRM = { roles: ROLES_CRM, permModule: 'crm', permRepliPalier: REPLI_ROLES }

const config = {
  key: 'crm',
  order: 40,
  nav: {
    label: 'CRM', labelKey: 'nav.section.crm',
    accent: 'azur',
    // APX1 — l'icône de l'APP est déclarée par le MODULE, jamais dérivée de
    // `items[0].icon`. Sans ce champ, l'ordre des items décidait le glyphe
    // affiché au lanceur / aux épinglés / au Menu d'accueil : remonter Leads en
    // tête aurait suffi à changer l'icône du CRM. Le glyphe est désormais
    // STABLE quel que soit le futur réordonnancement des items.
    icon: navIcon(Target),
    items: [
      // APX1 (fondateur 2026-08-01, « the Lead part is the opening of the
      // CRM ») — LA PORTE du CRM est `/crm/leads`, donc `items[0]`.
      // ATTENTION : `nav.items[0].to` est la convention « cockpit du module »
      // lue par AppLauncher, PinnedApps ET la préférence d'atterrissage
      // (`prefs.js` VX46) — trois surfaces corrigées par cette seule ligne.
      // ODY15 avait mis `/crm/cockpit` ici ; le cockpit reste une entrée de
      // nav parfaitement atteignable, simplement plus la porte d'entrée.
      { to: '/crm/leads',            label: 'Leads',            k: 'nav.leads',      icon: navIcon(Target),        roles: ['normal','responsable','admin'], ...LECTURE_CRM },
      // ODY15 — cockpit CRM (ModuleHero + actions + KPI), désormais 2ᵉ.
      { to: '/crm/cockpit',          label: 'Cockpit',          k: 'nav.crm_cockpit', icon: navIcon(LayoutDashboard), roles: ['normal','responsable','admin'], ...LECTURE_CRM },
      { to: '/calendrier',           label: 'Calendrier',       k: 'nav.calendrier', icon: navIcon(CalendarDays),   roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          k: 'nav.clients',    icon: navIcon(Users),      roles: ['normal','responsable','admin'] },
      // ODY15 — fermait un trou réel (module.config.test.jsx le documentait
      // comme sans entrée de nav) : QX16, rejeu des leads site web en échec.
      { to: '/crm/payloads-site-web', label: 'Leads site web',  k: 'nav.leads_site_web', icon: navIcon(Globe), roles: ['responsable','admin'] },
      { to: '/crm/forecast',         label: 'Forecast',         k: 'nav.forecast',   icon: navIcon(TrendingUp),    roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            k: 'nav.carte',      icon: navIcon(Map),           roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       k: 'nav.parrainage', icon: navIcon(UserPlus),   roles: ['normal','responsable','admin'], ...LECTURE_MODULE_CRM },
      // WIR99/DC12 — profil site réutilisable par client (pré-remplit le devis).
      { to: '/crm/profils-site',     label: 'Profils site',     k: 'nav.profils_site', icon: navIcon(Users),   roles: ['normal','responsable','admin'], ...LECTURE_MODULE_CRM },
      // PACT103 — intelligence concurrentielle par lead perdu.
      { to: '/crm/concurrents-perte', label: 'Concurrents (perdus)', k: 'nav.concurrents_perte', icon: navIcon(Swords), roles: ['normal','responsable','admin'], ...LECTURE_CRM },
      // NTCRM24 — classement des défis d'équipe : visible de toute l'équipe
      // (gamification), pas juste le manager.
      { to: '/crm/defis',            label: 'Défis',            k: 'nav.defis',      icon: navIcon(Trophy),     roles: ['normal','responsable','admin'], ...LECTURE_MODULE_CRM },
      // MRY31 — suivi des relances par jour (au-delà du widget Cockpit) :
      // visible de toute l'équipe, le filtre Responsable se réserve lui-même
      // aux rôles responsable/admin à l'intérieur de l'écran.
      { to: '/crm/relances',         label: 'Suivi des relances', k: 'nav.relances_suivi', icon: navIcon(CalendarClock), roles: ['normal','responsable','admin'], ...LECTURE_CRM },
      // VIS1 — Visiteurs & alertes : visible de toute l'équipe (lecture), les
      // actions d'exclusion « appareil équipe » se réservent elles-mêmes aux
      // rôles responsable/admin à l'intérieur de l'écran (la garde réelle
      // reste serveur, sur l'écriture d'`appareils-equipe/`).
      { to: '/crm/visiteurs',        label: 'Visiteurs & alertes', k: 'nav.visiteurs', icon: navIcon(Radar), roles: ['normal','responsable','admin'] },
      { to: '/crm/attribution',     label: 'Attribution des leads', icon: navIcon(UserPlus), roles: ['normal','responsable','admin'] },
      { to: '/crm/cockpit-equipe',  label: 'Cockpit d’équipe', icon: navIcon(Users), roles: ['normal','responsable','admin'] },
      // VTA8 — « Visites terrain » et « Revue technique » sont passées à l'app
      // Visites (nav `features/visites/module.config.jsx`).
    ],
  },
  routes: [
    // ODY15 — cockpit CRM (porte d'entrée de l'app).
    { path: '/crm/cockpit', component: CrmCockpit, ...LECTURE_CRM },
    { path: '/crm', component: ClientList },
    { path: '/crm/leads', component: LeadsPage, ...LECTURE_CRM },
    // VX22 — page dédiée : deep-link partageable, F5 recharge via crmApi.getLead.
    { path: '/crm/leads/:id', component: LeadDetailPage },
    { path: '/activites', component: MesActivitesPage },
    { path: '/calendrier', component: CalendarPage },
    { path: '/carte', component: CartePage },
    { path: '/crm/parrainage', component: ParrainagePage, ...LECTURE_MODULE_CRM },
    // WIR99/DC12 — écran minimal create/edit du profil site par client.
    { path: '/crm/profils-site', component: SiteProfilePage, ...LECTURE_MODULE_CRM },
    // QX16 — rejeu des payloads leads site web.
    { path: '/crm/payloads-site-web', component: WebsiteLeadPayloadsPage },
    // WIR15/NTCRM7 — Forecast (manager rollup).
    { path: '/crm/forecast', component: ForecastPage },
    // PACT103 — Concurrents sur affaires perdues.
    { path: '/crm/concurrents-perte', component: ConcurrentsPertePage, ...LECTURE_CRM },
    // NTCRM24 — leaderboard des défis d'équipe.
    { path: '/crm/defis', component: DefisPage, ...LECTURE_MODULE_CRM },
    // MRY31 — suivi des relances par jour.
    { path: '/crm/relances', component: RelancesSuiviPage, ...LECTURE_CRM },
    // VIS1 — Visiteurs & alertes (anti-fraude anonyme/appareil équipe).
    { path: '/crm/visiteurs', component: VisiteursPage },
    { path: '/crm/attribution', component: AttributionLeadsPage },
    { path: '/crm/cockpit-equipe', component: CockpitEquipePage },
    // VTA8 — les 4 routes `/crm/visites*` sont parties dans l'app Visites
    // (`/visites`, `/visites/toutes`, `/visites/revue`, `/visites/:id[/calage]`).
  ],
}

export default config
