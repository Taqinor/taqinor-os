/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Wallet, ShieldAlert } from 'lucide-react'

/* ============================================================================
   WIR55 — Configuration du module ERP « Crédit client » (limites, exposition,
   dérogations, conditions par segment).
   ----------------------------------------------------------------------------
   Les 7 composants (FicheCreditClient, CreditBadge, CreditWarningBanner,
   DefinirLimiteWizard, DemandeDerogationWizard, ConditionsSegmentScreen,
   ExpositionCreditPage) étaient CONSTRUITS mais jamais montés (module mort).
   Ce fichier auto-enregistré par `router/moduleRoutes.jsx` (glob) leur donne
   une nav + des routes — comme `fpa`/`assurances`. Aucune édition du routeur /
   de la Sidebar.

   Données SENSIBLES (limites, encours, dérogations) : gaté au palier
   responsable/admin côté nav ; le backend re-vérifie strictement
   (`IsDirecteurOrAdmin` : superuser, palier admin, ou rôle fin
   Directeur/Administrateur) — la nav est un raccourci, le backend est la garde.
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const ExpositionCreditPage = lazy(() => import('./ExpositionCreditPage'))
const DerogationsPage = lazy(() => import('./DerogationsPage'))
const FicheCreditClientPage = lazy(() => import('./FicheCreditClientPage'))
const ConditionsSegmentScreen = lazy(() => import('./ConditionsSegmentScreen'))

const IconWallet = <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />
const IconDerog = <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'credit',
  order: 76,
  nav: {
    label: 'CRÉDIT CLIENT',
    accent: 'lune', // financier = accent lune (dérivé), comme Assurances/Compta
    items: [
      { to: '/credit/exposition', label: 'Exposition', icon: IconWallet, roles: ROLES },
      { to: '/credit/derogations', label: 'Dérogations', icon: IconDerog, roles: ROLES },
    ],
  },
  // routes.meta : du plus spécifique au plus général.
  titles: [
    ['/credit/exposition', 'Exposition crédit'],
    ['/credit/derogations', 'Dérogations crédit'],
    ['/credit/conditions', 'Conditions de paiement par segment'],
    ['/credit/clients', 'Fiche crédit client'],
  ],
  sectionLabels: { credit: 'Crédit client' },
  routes: [
    { path: '/credit/exposition', component: ExpositionCreditPage, roles: ROLES },
    { path: '/credit/derogations', component: DerogationsPage, roles: ROLES },
    { path: '/credit/conditions', component: ConditionsSegmentScreen, roles: ROLES },
    // Fiche crédit d'un client atteinte depuis l'exposition (sans URL tapée).
    { path: '/credit/clients/:id', component: FicheCreditClientPage, roles: ROLES },
  ],
}
