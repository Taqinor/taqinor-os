/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Database } from 'lucide-react'

/* ============================================================================
   NTMIG — Config du module « Migration ERP », auto-enregistrée par le registre
   router/moduleRoutes.jsx (nav Sidebar, titres, routes lazy).
   ----------------------------------------------------------------------------
   Réservé au palier Administrateur/Directeur (roles: ['admin']). La garde
   SERVEUR (IsDirecteurOuAdmin) reste la seule source de vérité : ce gating
   d'écran ne fait que masquer une entrée de menu.
   ========================================================================== */

const MigrationProjetsList = lazy(() => import('./MigrationProjetsList'))
const MigrationWizard = lazy(() => import('./MigrationWizard'))

const config = {
  key: 'migration',
  order: 97,
  nav: {
    label: 'MIGRATION',
    accent: 'primary',
    items: [
      {
        to: '/migration',
        label: 'Projets de migration',
        icon: <Database size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['admin'],
      },
    ],
  },
  titles: [
    // Le plus spécifique d'abord : /migration/projet ne doit pas hériter du
    // titre de la liste.
    ['/migration/projet', 'Assistant de migration'],
    ['/migration', 'Migration ERP'],
  ],
  sectionLabels: { migration: 'Migration' },
  routes: [
    { path: '/migration', component: MigrationProjetsList, roles: ['admin'] },
    {
      path: '/migration/projet/:id',
      component: MigrationWizard,
      roles: ['admin'],
    },
  ],
}

export default config
