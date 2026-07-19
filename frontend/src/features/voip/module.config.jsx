/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Phone, PhoneCall, Settings } from 'lucide-react'

/* ============================================================================
   WIR160 — Configuration du module ERP « Téléphonie / Softphone VoIP ».
   ----------------------------------------------------------------------------
   Le backend (apps/voip : VoipParametres, VoipIdentifiantUtilisateur, Appel,
   provider NoOp swappable, résolution client/lead via selectors CRM, chatter
   automatique) était complet et testé mais SANS aucune UI. Ce fichier
   auto-enregistré par `router/moduleRoutes.jsx` (glob) donne au module une nav
   + des routes : journal + click-to-call (tout rôle), config société VoIP
   (responsable/admin), et « Mes identifiants » SIP (chacun les siens).
   ========================================================================== */

const TOUS = ['responsable', 'admin', 'normal']
const GESTION = ['responsable', 'admin']

const VoipJournalPage = lazy(() => import('./VoipJournalPage'))
const VoipParametresPage = lazy(() => import('./VoipParametresPage'))
const MesIdentifiantsPage = lazy(() => import('./MesIdentifiantsPage'))

const IconPhone = <Phone size={17} strokeWidth={1.75} aria-hidden="true" />
const IconCall = <PhoneCall size={17} strokeWidth={1.75} aria-hidden="true" />
const IconSettings = <Settings size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'voip',
  order: 77,
  nav: {
    label: 'TÉLÉPHONIE',
    accent: 'lune',
    items: [
      { to: '/voip', label: 'Journal & appel', icon: IconCall, roles: TOUS },
      { to: '/voip/mes-identifiants', label: 'Mes identifiants', icon: IconPhone, roles: TOUS },
      { to: '/voip/parametres', label: 'Config société', icon: IconSettings, roles: GESTION },
    ],
  },
  titles: [
    ['/voip/mes-identifiants', 'Mes identifiants VoIP'],
    ['/voip/parametres', 'Configuration VoIP (société)'],
    ['/voip', "Journal d'appels"],
  ],
  sectionLabels: { voip: 'Téléphonie' },
  routes: [
    { path: '/voip/mes-identifiants', component: MesIdentifiantsPage, roles: TOUS },
    { path: '/voip/parametres', component: VoipParametresPage, roles: GESTION },
    { path: '/voip', component: VoipJournalPage, roles: TOUS },
  ],
}
