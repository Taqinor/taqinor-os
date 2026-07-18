/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { ClipboardList, ShieldCheck, Stethoscope, UserPlus } from 'lucide-react'

/* ============================================================================
   NTSAN — Config du module Santé (cabinet/clinique), auto-enregistrée.
   ----------------------------------------------------------------------------
   Collectée par le registre ``router/moduleRoutes.jsx`` via glob (nav Sidebar,
   routes.meta, fil d'Ariane, route lazy). Le grain RBAC fin (rôles
   secretaire_medicale/praticien/caissier_sante) est posé par NTSAN17 — en
   attendant, gaté comme les autres modules internes (normal/responsable/admin).
   ========================================================================== */

const SanteAgenda = lazy(() => import('./SanteAgenda'))
const NomenclatureActesScreen = lazy(() => import('./NomenclatureActesScreen'))
const ReceptionScreen = lazy(() => import('./ReceptionScreen'))
// WIR53(b) — destination réelle du lien de notification
// `sante.alertes_prise_en_charge_expirant` (`/sante/prises-en-charge?id=`),
// jusque-là non enregistrée (404 systématique).
const PrisesEnChargePage = lazy(() => import('./PrisesEnChargePage'))

const config = {
  key: 'sante',
  order: 95,
  nav: {
    label: 'SANTÉ',
    accent: 'primary',
    items: [
      {
        to: '/sante/reception',
        label: 'Réception',
        icon: <UserPlus size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/sante/agenda',
        label: 'Agenda',
        icon: <Stethoscope size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/sante/nomenclature-actes',
        label: 'Nomenclature des actes',
        icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
      {
        to: '/sante/prises-en-charge',
        label: 'Prises en charge',
        icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
    ],
  },
  titles: [
    ['/sante/reception', 'Réception (Santé)'],
    ['/sante/agenda', 'Agenda (Santé)'],
    ['/sante/nomenclature-actes', 'Nomenclature des actes'],
    ['/sante/prises-en-charge', 'Prises en charge'],
  ],
  sectionLabels: { sante: 'Santé' },
  routes: [
    {
      path: '/sante/reception', component: ReceptionScreen,
      roles: ['normal', 'responsable', 'admin'],
    },
    {
      path: '/sante/agenda', component: SanteAgenda,
      roles: ['normal', 'responsable', 'admin'],
    },
    {
      path: '/sante/nomenclature-actes', component: NomenclatureActesScreen,
      roles: ['responsable', 'admin'],
    },
    {
      path: '/sante/prises-en-charge', component: PrisesEnChargePage,
      roles: ['normal', 'responsable', 'admin'],
    },
  ],
}

export default config
