/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import { Leaf, Gauge } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   NTESG6 — Configuration du module ESG / RSE (reporting ESG/durabilité
   consolidé). Déposé ici, collecté automatiquement par
   `router/moduleRoutes.jsx` (glob) — AUCUNE modification du routeur/Sidebar.
   Distinct de `/qhse/environnement` (saisie environnement QHSE) : ce module
   consolide la COUCHE reporting (périodes figées, agrégation cross-app,
   catalogue GRI-lite) — voir `apps/esg` côté backend.
   ========================================================================== */

const EsgCockpit = lazy(() => import('../../pages/esg/EsgCockpit'))
// NTESG12 — matrice de matérialité (registre des parties prenantes RSE).
const MatriceMaterialite = lazy(() => import('../../pages/esg/MatriceMaterialite'))
// WIR130 — bibliothèque de facteurs d'émission versionnée (NTESG16).
const FacteursEmission = lazy(() => import('../../pages/esg/FacteursEmission'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'esg',
  order: 62,
  nav: {
    label: 'ESG / RSE',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Leaf),
    accent: 'success',
    items: [
      { to: '/esg', label: 'Cockpit ESG', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/esg/materialite', label: 'Matrice de matérialité', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/esg/facteurs', label: "Facteurs d'émission", icon: <Gauge size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/esg', 'Cockpit ESG'],
    ['/esg/materialite', 'Matrice de matérialité'],
    ['/esg/facteurs', "Facteurs d'émission"],
  ],
  sectionLabels: { esg: 'ESG / RSE' },
  routes: [
    { path: '/esg', component: EsgCockpit, roles: ROLES },
    { path: '/esg/materialite', component: MatriceMaterialite, roles: ROLES },
    { path: '/esg/facteurs', component: FacteursEmission, roles: ROLES },
  ],
}

export default config
