/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   NTMOB4/NTMOB5 — Accueils mobiles par rôle (Commercial / Dirigeant).
   Auto-enregistrés via le registre de modules (router/moduleRoutes.jsx) —
   aucune modification du routeur, de la Sidebar ni de routes.meta. Pas de
   section `nav` : ces écrans sont atteints par redirection automatique
   (sélecteur de démarrage par rôle, NTMOB6) plutôt que par un lien de menu
   permanent — cohérent avec `/ma-journee` qui n'a pas non plus d'entrée nav
   dédiée pour son usage « accueil du jour ».
   ========================================================================== */

const CommercialHome = lazy(() => import('./mobile/CommercialHome'))
const CockpitHome = lazy(() => import('./mobile/CockpitHome'))

const config = {
  key: 'offlinesync',
  order: 65,
  routes: [
    { path: '/mobile/commercial', component: CommercialHome },
    { path: '/mobile/cockpit', component: CockpitHome },
  ],
}

export default config
