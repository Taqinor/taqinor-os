/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { CalendarDays, Users, Target, Map, UserPlus } from 'lucide-react'

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

const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
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

const config = {
  key: 'crm',
  order: 40,
  nav: {
    label: 'CRM', labelKey: 'nav.section.crm',
    accent: 'azur',
    items: [
      { to: '/calendrier',           label: 'Calendrier',       k: 'nav.calendrier', icon: navIcon(CalendarDays),   roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          k: 'nav.clients',    icon: navIcon(Users),      roles: ['normal','responsable','admin'] },
      { to: '/crm/leads',            label: 'Leads',            k: 'nav.leads',      icon: navIcon(Target),        roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            k: 'nav.carte',      icon: navIcon(Map),           roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       k: 'nav.parrainage', icon: navIcon(UserPlus),   roles: ['normal','responsable','admin'] },
    ],
  },
  routes: [
    { path: '/crm', component: ClientList },
    { path: '/crm/leads', component: LeadsPage },
    // VX22 — page dédiée : deep-link partageable, F5 recharge via crmApi.getLead.
    { path: '/crm/leads/:id', component: LeadDetailPage },
    { path: '/activites', component: MesActivitesPage },
    { path: '/calendrier', component: CalendarPage },
    { path: '/carte', component: CartePage },
    { path: '/crm/parrainage', component: ParrainagePage },
    // QX16 — rejeu des payloads leads site web.
    { path: '/crm/payloads-site-web', component: WebsiteLeadPayloadsPage },
  ],
}

export default config
