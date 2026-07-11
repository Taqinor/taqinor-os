/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas — comme moduleRoutes.jsx. */
import { lazy } from 'react'
import { Wallet, FileText, SlidersHorizontal, Banknote, ReceiptText } from 'lucide-react'

/* ============================================================================
   Module PAIE (paie marocaine) — configuration auto-enregistrée.
   ----------------------------------------------------------------------------
   Dépose UN SEUL fichier (glob dans router/moduleRoutes.jsx) : nav Sidebar
   gatée, titres routes.meta, libellés de fil d'Ariane, et routes lazy. Aucune
   édition du routeur / de la Sidebar / de routes.meta. Le palier paie est
   Administrateur/Responsable, SAUF « Mes bulletins » (self-service, tout rôle).
   ========================================================================== */

const PaieRunWizard = lazy(() => import('./PaieRunWizard.jsx'))
const BulletinList = lazy(() => import('./BulletinList.jsx'))
const BulletinDetail = lazy(() => import('./BulletinDetail.jsx'))
const PaieParametres = lazy(() => import('./PaieParametres.jsx'))
const PaieDeclarations = lazy(() => import('./PaieDeclarations.jsx'))
const MesBulletins = lazy(() => import('./MesBulletins.jsx'))

const ICON = { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' }
const PALIER = ['responsable', 'admin']
const TOUS = ['normal', 'responsable', 'admin']

export default {
  key: 'paie',
  order: 30,
  nav: {
    label: 'PAIE',
    accent: 'azur', // VX8 — RH/paie = accent azur (dérivé)
    items: [
      { to: '/paie', label: 'Run de paie',
        icon: <Wallet {...ICON} />, roles: PALIER },
      { to: '/paie/bulletins', label: 'Bulletins',
        icon: <FileText {...ICON} />, roles: PALIER },
      { to: '/paie/parametres', label: 'Paramètres',
        icon: <SlidersHorizontal {...ICON} />, roles: PALIER },
      { to: '/paie/declarations', label: 'Déclarations',
        icon: <Banknote {...ICON} />, roles: PALIER },
      // UX14 — self-service : visible pour TOUS les rôles.
      { to: '/paie/mes-bulletins', label: 'Mes bulletins',
        icon: <ReceiptText {...ICON} />, roles: TOUS },
    ],
  },
  // routes.meta : du plus spécifique au plus général.
  titles: [
    ['/paie/mes-bulletins', 'Mes bulletins'],
    ['/paie/declarations', 'Déclarations & virements'],
    ['/paie/parametres', 'Paramètres de paie'],
    ['/paie/bulletins', 'Bulletins de paie'],
    ['/paie', 'Run de paie'],
  ],
  sectionLabels: { paie: 'Paie' },
  routes: [
    { path: '/paie', component: PaieRunWizard, roles: PALIER },
    { path: '/paie/bulletins', component: BulletinList, roles: PALIER },
    { path: '/paie/bulletins/:id', component: BulletinDetail, roles: PALIER },
    { path: '/paie/parametres', component: PaieParametres, roles: PALIER },
    { path: '/paie/declarations', component: PaieDeclarations, roles: PALIER },
    // Route self-service : pas de `roles` → authLoader (tout utilisateur connecté).
    { path: '/paie/mes-bulletins', component: MesBulletins },
  ],
}
