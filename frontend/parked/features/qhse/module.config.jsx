/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import {
  ShieldCheck, AlertOctagon, ClipboardCheck, ShieldAlert, Leaf, Star, UserCheck,
  Award,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX29–UX33 — Configuration du module QHSE (Qualité · Hygiène · Sécurité ·
   Environnement). Déposé ici, il est collecté automatiquement par
   `router/moduleRoutes.jsx` (glob) — aucune modification du routeur/Sidebar.

   WIR171 — les routes et entrées de menu n'étaient gatées que par le palier
   `['responsable','admin']`, alors que le serveur gate QHSE par `qhse_voir` /
   `qhse_gerer` (YRBAC3) via `HasPermissionOrLegacy` : un Commercial /
   Technicien / Viewer porte `qhse_voir` mais relève du palier 'normal' — le
   serveur lui répondait 200 pendant que la coquille le renvoyait en 403.
   Chaque entrée déclare donc la permission de LECTURE + `permRepliPalier`
   (sémantique serveur exacte, cf. `router/moduleGating.js`) ; le palier
   élargi ne sert plus que de repli documentaire.
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
// WIR276 — registres ISO QHSE (rappels produit, certifications, programme
// d'audit, revues de direction, objectifs) jusqu'ici sans écran.
const IsoQhse = lazy(() => import('./IsoQhse'))

const ROLES = ['normal', 'responsable', 'admin']
// WIR171 — gate commun à toutes les entrées/routes du module (étalé par `...`).
const GATE = { roles: ROLES, perm: 'qhse_voir', permRepliPalier: true }

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
      { to: '/qhse', label: 'Cockpit QHSE', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/non-conformites', label: 'Non-conformités', icon: <AlertOctagon size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/inspections', label: 'Inspections & audits', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/risques', label: 'Risques & permis', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/environnement', label: 'Environnement & ESG', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/notations', label: 'Notation fin de chantier', icon: <Star size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/checkins-securite', label: 'Check-ins sécurité', icon: <UserCheck size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/qhse/iso', label: 'Registres ISO', icon: <Award size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
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
    ['/qhse/iso', 'Registres ISO — QHSE'],
    ['/qhse', 'Cockpit QHSE'],
  ],
  sectionLabels: { qhse: 'QHSE' },
  routes: [
    { path: '/qhse', component: QhseCockpit, ...GATE },
    { path: '/qhse/non-conformites', component: NonConformites, ...GATE },
    { path: '/qhse/inspections', component: Inspections, ...GATE },
    { path: '/qhse/risques', component: Risques, ...GATE },
    { path: '/qhse/environnement', component: Environnement, ...GATE },
    { path: '/qhse/notations', component: NotationFinChantier, ...GATE },
    { path: '/qhse/checkins-securite', component: CheckinsSecurite, ...GATE },
    { path: '/qhse/iso', component: IsoQhse, ...GATE },
  ],
}

export default config
