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
// NTMOB25 — accueil mobile du RESPONSABLE d'équipe terrain, distinct des
// accueils individuels ci-dessus.
const EquipeTerrainHome = lazy(() => import('./mobile/EquipeTerrainHome'))
// NTMOB26 — accueil mobile du Commercial responsable (onglets Moi/Équipe).
const EquipeCommercialeHome = lazy(() => import('./mobile/EquipeCommercialeHome'))
// NTMOB2 — écran d'arbitrage des conflits de synchronisation. Atteint depuis
// l'état « en attente de synchro » (badge/bandeau), jamais par un lien de menu
// permanent : dans le cas nominal il n'y a AUCUN conflit à montrer.
const SyncConflictsPanel = lazy(() => import('./SyncConflictsPanel'))

const config = {
  key: 'offlinesync',
  order: 65,
  routes: [
    { path: '/mobile/commercial', component: CommercialHome },
    { path: '/mobile/cockpit', component: CockpitHome },
    { path: '/mobile/equipe-terrain', component: EquipeTerrainHome },
    { path: '/mobile/equipe-commerciale', component: EquipeCommercialeHome },
    { path: '/synchro/conflits', component: SyncConflictsPanel }, // contextuelle: atteinte depuis l'état « en attente de synchro » (badge/bandeau) ; dans le cas nominal il n'y a AUCUN conflit, une entrée de menu permanente serait du bruit.
  ],
}

export default config
