/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import { ShieldCheck, ShieldAlert, LayoutDashboard, ClipboardCheck } from 'lucide-react'

/* ============================================================================
   NTASS25 — Configuration du module ERP « Assurances » (registre des polices
   d'entreprise & sinistres transverses).
   ----------------------------------------------------------------------------
   Un seul fichier auto-enregistré par `router/moduleRoutes.jsx` (glob) : nav
   Sidebar gatée, titres de page, libellé de fil d'Ariane, routes lazy. Aucune
   édition du routeur / de la Sidebar / de routes.meta.

   Données SENSIBLES (primes, sinistres, indemnisations) : gaté par défaut au
   palier responsable/admin (aligné sur le backend `assurances_voir`/`gerer`).
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const PolicesList = lazy(() => import('./PolicesList'))
const PoliceDetail = lazy(() => import('./PoliceDetail'))
const SinistresPage = lazy(() => import('./SinistresPage'))
// WIR145 — tableau de bord assurances + exigences par marché.
const TableauBordAssurances = lazy(() => import('./TableauBordAssurances'))
const ExigencesMarche = lazy(() => import('./ExigencesMarche'))

const SC = <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />
const SA = <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />
const TB = <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />
const EX = <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'assurances',
  order: 75,
  nav: {
    label: 'ASSURANCES',
    accent: 'lune', // documentaire/financier = accent lune (dérivé)
    items: [
      { to: '/assurances', label: 'Polices', icon: SC, roles: ROLES },
      { to: '/assurances/tableau-bord', label: 'Tableau de bord', icon: TB, roles: ROLES },
      { to: '/assurances/exigences', label: 'Exigences marché', icon: EX, roles: ROLES },
      { to: '/assurances/sinistres', label: 'Sinistres', icon: SA, roles: ROLES },
    ],
  },
  // routes.meta : du plus spécifique au plus général.
  titles: [
    ['/assurances/tableau-bord', 'Tableau de bord assurances'],
    ['/assurances/exigences', 'Exigences d\'assurance par marché'],
    ['/assurances/sinistres', 'Sinistres transverses'],
    ['/assurances', "Polices d'assurance"],
  ],
  sectionLabels: { assurances: 'Assurances' },
  routes: [
    { path: '/assurances', component: PolicesList, roles: ROLES },
    // WIR145 — routes STATIQUES déclarées AVANT la route dynamique `:id`.
    { path: '/assurances/tableau-bord', component: TableauBordAssurances, roles: ROLES },
    { path: '/assurances/exigences', component: ExigencesMarche, roles: ROLES },
    // NTASS27 — sinistres : route STATIQUE déclarée AVANT la route dynamique
    // `:id` pour qu'elle ne soit jamais capturée comme un id de police.
    { path: '/assurances/sinistres', component: SinistresPage, roles: ROLES },
    // NTASS26 — fiche police détail (onglets).
    { path: '/assurances/:id', component: PoliceDetail, roles: ROLES },
  ],
}
