/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants. */
import { lazy } from 'react'
import { ShieldCheck, Scale, Send } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   WIR106 — Module Conformité fiscale (NTMAR). Écran « Calendrier fiscal /
   Conformité » (feu tricolore NTMAR16 + échéances). NE DUPLIQUE PAS la gestion
   des obligations fiscales, qui reste dans le module Comptabilité (XACC9) — cet
   écran est une vue conformité en lecture seule (réconciliation WIR106).
   ========================================================================== */

const ConformiteFiscale = lazy(() => import('../../pages/fiscal/ConformiteFiscale'))
// PACT54 — historique de la file de transmission DGI (NTMAR7), jusqu'ici
// complète côté serveur et totalement invisible.
const TransmissionsDGIPage = lazy(() => import('../../pages/fiscal/TransmissionsDGIPage'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'fiscal',
  order: 63,
  nav: {
    label: 'Conformité fiscale',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Scale),
    accent: 'warning',
    items: [
      { to: '/fiscal/conformite', label: 'Conformité fiscale', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      // PACT54 — historique des transmissions DGI (lecture seule).
      { to: '/fiscal/transmissions-dgi', label: 'Transmissions DGI', icon: <Send size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/fiscal/conformite', 'Conformité fiscale'],
    ['/fiscal/transmissions-dgi', 'Transmissions DGI'],
  ],
  sectionLabels: { fiscal: 'Conformité fiscale' },
  routes: [
    { path: '/fiscal/conformite', component: ConformiteFiscale, roles: ROLES },
    // PACT54 — file d'attente de transmission DGI (historique).
    { path: '/fiscal/transmissions-dgi', component: TransmissionsDGIPage, roles: ROLES },
  ],
}

export default config
