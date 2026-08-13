/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import {
  CalendarDays, Users, Target, Map, UserPlus, TrendingUp, LayoutDashboard, Globe,
  Handshake, Swords, Trophy,
} from 'lucide-react'

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

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

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
// PACT102 — Partenaires (FG234/235/237) : agrément, soumissions, commissions
// — le backend est complet, aucun écran interne n'existait avant ce lot.
const PartenairesPage = lazy(() => import('./Partenaires'))
// PACT103 — Concurrents sur affaires perdues (FG242) : aucun écran, y
// compris le popover « perdu » existant, ne l'appelait avant ce lot.
const ConcurrentsPertePage = lazy(() => import('./ConcurrentsPerte'))
// NTCRM24 — leaderboard des défis d'équipe (NTCRM23), visible de toute l'équipe.
const DefisPage = lazy(() => import('../../pages/crm/defis/DefisPage'))

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
      { to: '/crm/leads',            label: 'Leads',            k: 'nav.leads',      icon: navIcon(Target),        roles: ['normal','responsable','admin'] },
      // ODY15 — cockpit CRM (ModuleHero + actions + KPI), désormais 2ᵉ.
      { to: '/crm/cockpit',          label: 'Cockpit',          k: 'nav.crm_cockpit', icon: navIcon(LayoutDashboard), roles: ['normal','responsable','admin'] },
      { to: '/calendrier',           label: 'Calendrier',       k: 'nav.calendrier', icon: navIcon(CalendarDays),   roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          k: 'nav.clients',    icon: navIcon(Users),      roles: ['normal','responsable','admin'] },
      // ODY15 — fermait un trou réel (module.config.test.jsx le documentait
      // comme sans entrée de nav) : QX16, rejeu des leads site web en échec.
      { to: '/crm/payloads-site-web', label: 'Leads site web',  k: 'nav.leads_site_web', icon: navIcon(Globe), roles: ['responsable','admin'] },
      { to: '/crm/forecast',         label: 'Forecast',         k: 'nav.forecast',   icon: navIcon(TrendingUp),    roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            k: 'nav.carte',      icon: navIcon(Map),           roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       k: 'nav.parrainage', icon: navIcon(UserPlus),   roles: ['normal','responsable','admin'] },
      // WIR99/DC12 — profil site réutilisable par client (pré-remplit le devis).
      { to: '/crm/profils-site',     label: 'Profils site',     k: 'nav.profils_site', icon: navIcon(Users),   roles: ['normal','responsable','admin'] },
      // PACT102 — agrément partenaire + soumissions + commissions (argent : responsable/admin).
      { to: '/crm/partenaires',      label: 'Partenaires',      k: 'nav.partenaires', icon: navIcon(Handshake), roles: ['responsable','admin'] },
      // PACT103 — intelligence concurrentielle par lead perdu.
      { to: '/crm/concurrents-perte', label: 'Concurrents (perdus)', k: 'nav.concurrents_perte', icon: navIcon(Swords), roles: ['normal','responsable','admin'] },
      // NTCRM24 — classement des défis d'équipe : visible de toute l'équipe
      // (gamification), pas juste le manager.
      { to: '/crm/defis',            label: 'Défis',            k: 'nav.defis',      icon: navIcon(Trophy),     roles: ['normal','responsable','admin'] },
    ],
  },
  routes: [
    // ODY15 — cockpit CRM (porte d'entrée de l'app).
    { path: '/crm/cockpit', component: CrmCockpit },
    { path: '/crm', component: ClientList },
    { path: '/crm/leads', component: LeadsPage },
    // VX22 — page dédiée : deep-link partageable, F5 recharge via crmApi.getLead.
    { path: '/crm/leads/:id', component: LeadDetailPage },
    { path: '/activites', component: MesActivitesPage },
    { path: '/calendrier', component: CalendarPage },
    { path: '/carte', component: CartePage },
    { path: '/crm/parrainage', component: ParrainagePage },
    // WIR99/DC12 — écran minimal create/edit du profil site par client.
    { path: '/crm/profils-site', component: SiteProfilePage },
    // QX16 — rejeu des payloads leads site web.
    { path: '/crm/payloads-site-web', component: WebsiteLeadPayloadsPage },
    // WIR15/NTCRM7 — Forecast (manager rollup).
    { path: '/crm/forecast', component: ForecastPage },
    // PACT102 — Partenaires (agrément, soumissions, commissions).
    { path: '/crm/partenaires', component: PartenairesPage, roles: ['responsable', 'admin'] },
    // PACT103 — Concurrents sur affaires perdues.
    { path: '/crm/concurrents-perte', component: ConcurrentsPertePage },
    // NTCRM24 — leaderboard des défis d'équipe.
    { path: '/crm/defis', component: DefisPage },
  ],
}

export default config
