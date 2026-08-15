/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  Wallet, ShieldAlert, CreditCard, Upload, ShieldCheck, Users, Settings,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

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
const ImportLimitesCreditPage = lazy(() => import('./ImportLimitesCreditPage'))
const PolicesAssuranceCreditPage = lazy(() => import('./PolicesAssuranceCreditPage'))
const SegmentsClientPage = lazy(() => import('./SegmentsClientPage'))
// WIR185/NTCRD3 — reglages credit societe (politique de hold, seuils).
const ReglagesCreditPage = lazy(() => import('./ReglagesCreditPage'))

const IconWallet = <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />
const IconDerog = <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />
const IconImport = <Upload size={17} strokeWidth={1.75} aria-hidden="true" />
const IconAssurance = <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />
const IconSegments = <Users size={17} strokeWidth={1.75} aria-hidden="true" />
const IconReglages = <Settings size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'credit',
  order: 76,
  nav: {
    label: 'CRÉDIT CLIENT',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(CreditCard),
    accent: 'lune', // financier = accent lune (dérivé), comme Assurances/Compta
    items: [
      { to: '/credit/exposition', label: 'Exposition', icon: IconWallet, roles: ROLES },
      { to: '/credit/derogations', label: 'Dérogations', icon: IconDerog, roles: ROLES },
      { to: '/credit/import-limites', label: 'Import des limites', icon: IconImport, roles: ROLES },
      { to: '/credit/assurance', label: 'Assurance-crédit', icon: IconAssurance, roles: ROLES },
      { to: '/credit/segments-clients', label: 'Segments clients', icon: IconSegments, roles: ROLES },
      // WIR185 — la politique de hold de la societe (ecriture gardee serveur
      // par IsDirecteurOrAdmin ; l'ecran degrade en lecture seule sinon).
      { to: '/credit/reglages', label: 'Réglages crédit', icon: IconReglages, roles: ROLES },
    ],
  },
  // routes.meta : du plus spécifique au plus général.
  titles: [
    ['/credit/import-limites', 'Import des limites de crédit'],
    ['/credit/assurance', 'Assurance-crédit (polices et encours garantis)'],
    ['/credit/segments-clients', 'Segments crédit des clients'],
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
    { path: '/credit/import-limites', component: ImportLimitesCreditPage, roles: ROLES },
    { path: '/credit/assurance', component: PolicesAssuranceCreditPage, roles: ROLES },
    { path: '/credit/segments-clients', component: SegmentsClientPage, roles: ROLES },
    { path: '/credit/reglages', component: ReglagesCreditPage, roles: ROLES },
    // Fiche crédit d'un client atteinte depuis l'exposition (sans URL tapée).
    { path: '/credit/clients/:id', component: FicheCreditClientPage, roles: ROLES },
  ],
}
