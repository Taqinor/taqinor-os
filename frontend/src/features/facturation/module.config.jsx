/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { Receipt, FileMinus, Wallet, CalendarClock } from 'lucide-react'

/* ============================================================================
   ODX18 — App Facturation (équivalent Odoo Invoicing, séparé de Sales).
   ----------------------------------------------------------------------------
   Regroupement FONCTIONNEL only : la section « Facturation » (Factures, Avoirs,
   Encaissements, Recouvrement) est EXTRAITE de la section VENTES vers son propre
   module « coquille ». Mêmes routes (/ventes/factures…), mêmes pages, mêmes
   gardes de rôles, mêmes hooks DOM e2e — zéro page reconstruite. Les routes API
   correspondantes sont servies sous DEUX préfixes (/api/django/facturation/… et
   /api/django/ventes/… historique). Les PDFs facture restent le legacy
   (règle #4 — seul le devis passe par /proposal).
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const FactureList = lazy(() => import('../../pages/ventes/FactureList'))
const AvoirsPage = lazy(() => import('../../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../../pages/ventes/RelancesPage'))
const PaiementsPage = lazy(() => import('../../pages/ventes/PaiementsPage'))

const config = {
  key: 'facturation',
  order: 51,
  nav: {
    label: 'FACTURATION', labelKey: 'nav.section.facturation',
    accent: 'lune',
    items: [
      { to: '/ventes/factures',  label: 'Factures',          k: 'nav.factures',      icon: navIcon(Receipt),       roles: ['normal','responsable','admin'] },
      { to: '/ventes/avoirs',    label: 'Avoirs',            k: 'nav.avoirs',        icon: navIcon(FileMinus),     roles: ['normal','responsable','admin'] },
      { to: '/ventes/paiements', label: 'Encaissements',     k: 'nav.encaissements', icon: navIcon(Wallet),        roles: ['normal','responsable','admin'] },
      { to: '/ventes/relances',  label: 'Relances / Impayés', k: 'nav.relances',     icon: navIcon(CalendarClock), roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/ventes/factures', component: FactureList },
    { path: '/ventes/avoirs', component: AvoirsPage },
    { path: '/ventes/relances', component: RelancesPage },
    { path: '/ventes/paiements', component: PaiementsPage },
  ],
}

export default config
