/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import {
  BedDouble, CalendarCog, ClipboardList, Handshake, Receipt, ShieldCheck,
  Stethoscope, UserPlus,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

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
// WIR142 — 6 surfaces d'administration santé jusque-là sans écran :
// admissions, conventions/grilles, actes réalisés, factures/paiements,
// configuration agenda.
const AdmissionsScreen = lazy(() => import('./AdmissionsScreen'))
const ConventionsScreen = lazy(() => import('./ConventionsScreen'))
const ActesRealisesScreen = lazy(() => import('./ActesRealisesScreen'))
const FacturationScreen = lazy(() => import('./FacturationScreen'))
const AgendaConfigScreen = lazy(() => import('./AgendaConfigScreen'))

const config = {
  key: 'sante',
  order: 95,
  nav: {
    label: 'SANTÉ',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Stethoscope),
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
      {
        to: '/sante/admissions',
        label: 'Admissions',
        icon: <BedDouble size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/sante/conventions',
        label: 'Conventions & grilles',
        icon: <Handshake size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
      {
        to: '/sante/actes-realises',
        label: 'Actes réalisés',
        icon: <Stethoscope size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/sante/facturation',
        label: 'Facturation',
        icon: <Receipt size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/sante/config-agenda',
        label: 'Configuration agenda',
        icon: <CalendarCog size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
    ],
  },
  titles: [
    ['/sante/reception', 'Réception (Santé)'],
    ['/sante/agenda', 'Agenda (Santé)'],
    ['/sante/nomenclature-actes', 'Nomenclature des actes'],
    ['/sante/prises-en-charge', 'Prises en charge'],
    ['/sante/admissions', 'Admissions'],
    ['/sante/conventions', 'Conventions & grilles tarifaires'],
    ['/sante/actes-realises', 'Actes réalisés'],
    ['/sante/facturation', 'Facturation santé'],
    ['/sante/config-agenda', 'Configuration agenda'],
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
    {
      path: '/sante/admissions', component: AdmissionsScreen,
      roles: ['normal', 'responsable', 'admin'],
    },
    {
      path: '/sante/conventions', component: ConventionsScreen,
      roles: ['responsable', 'admin'],
    },
    {
      path: '/sante/actes-realises', component: ActesRealisesScreen,
      roles: ['normal', 'responsable', 'admin'],
    },
    {
      path: '/sante/facturation', component: FacturationScreen,
      roles: ['normal', 'responsable', 'admin'],
    },
    {
      path: '/sante/config-agenda', component: AgendaConfigScreen,
      roles: ['responsable', 'admin'],
    },
  ],
}

export default config
