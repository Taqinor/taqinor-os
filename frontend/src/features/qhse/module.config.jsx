/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import {
  ShieldCheck, AlertOctagon, ClipboardCheck, ShieldAlert, Leaf, Star, UserCheck,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX29–UX33 — Configuration du module QHSE (Qualité · Hygiène · Sécurité ·
   Environnement). Déposé ici, il est collecté automatiquement par
   `router/moduleRoutes.jsx` (glob) — aucune modification du routeur/Sidebar.
   WIR171 — les routes/entrées de menu étaient gatées `['responsable','admin']`
   alors que le serveur gate la LECTURE par `qhse_voir`
   (`HasPermissionOrLegacy`, permission accordée aux 7 rôles) : un Commercial
   recevait 200 et ne voyait rien. Elles portent désormais `...LECTURE` (palier
   élargi + permission + repli palier pour les comptes hérités sans rôle fin).
   Règle unique : `router/navPermission.js`.
   ========================================================================== */

const QhseCockpit = lazy(() => import('./QhseCockpit'))
const NonConformites = lazy(() => import('./NonConformites'))
const Inspections = lazy(() => import('./Inspections'))
const Risques = lazy(() => import('./Risques'))
const Environnement = lazy(() => import('./Environnement'))
// WIR125 — notation de fin de chantier (gate advisory rendue opérable).
const NotationFinChantier = lazy(() => import('./NotationFinChantier'))
// WIR115 — check-in sécurité (technicien seul sur site) + SCAR fournisseur.
const CheckinsSecurite = lazy(() => import('./CheckinsSecurite'))

const ROLES = ['responsable', 'admin']
// WIR171 — sémantique serveur `HasPermissionOrLegacy('qhse_voir')`.
const LECTURE = {
  roles: ['normal', 'responsable', 'admin'],
  perm: 'qhse_voir',
  permLegacyRoles: ROLES,
}

const config = {
  key: 'qhse',
  order: 60,
  nav: {
    label: 'QHSE',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(ShieldCheck),
    accent: 'destructive', // VX8 — sécurité/risque = accent destructive (dérivé)
    items: [
      { to: '/qhse', label: 'Cockpit QHSE', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/non-conformites', label: 'Non-conformités', icon: <AlertOctagon size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/inspections', label: 'Inspections & audits', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/risques', label: 'Risques & permis', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/environnement', label: 'Environnement & ESG', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/notations', label: 'Notation fin de chantier', icon: <Star size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/qhse/checkins-securite', label: 'Check-ins sécurité', icon: <UserCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
    ],
  },
  // routes.meta — du plus spécifique au plus général.
  titles: [
    ['/qhse/non-conformites', 'Non-conformités — QHSE'],
    ['/qhse/inspections', 'Inspections & audits — QHSE'],
    ['/qhse/risques', 'Risques & permis — QHSE'],
    ['/qhse/environnement', 'Environnement & ESG — QHSE'],
    ['/qhse/notations', 'Notation fin de chantier — QHSE'],
    ['/qhse/checkins-securite', 'Check-ins sécurité — QHSE'],
    ['/qhse', 'Cockpit QHSE'],
  ],
  sectionLabels: { qhse: 'QHSE' },
  routes: [
    { path: '/qhse', component: QhseCockpit, ...LECTURE },
    { path: '/qhse/non-conformites', component: NonConformites, ...LECTURE },
    { path: '/qhse/inspections', component: Inspections, ...LECTURE },
    { path: '/qhse/risques', component: Risques, ...LECTURE },
    { path: '/qhse/environnement', component: Environnement, ...LECTURE },
    { path: '/qhse/notations', component: NotationFinChantier, ...LECTURE },
    { path: '/qhse/checkins-securite', component: CheckinsSecurite, ...LECTURE },
  ],
}

export default config
