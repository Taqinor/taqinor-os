/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { LayoutDashboard, Briefcase, Building2, LayoutGrid, FolderKanban, BookOpen, Wallet, Gavel } from 'lucide-react'
import { EmptyState } from '../../ui'

/* ============================================================================
   AOF7 — RÉOUVERTURE de la nav du module AO (WIR166, actée en `docs/PLAN.md`).
   ----------------------------------------------------------------------------
   DÉCISION FONDATEUR 2026-08-01 — WIR166 ROUVERTE : ce module.config portait
   depuis WIR166 (ODX11) la décision « BACKEND-ONLY, requiert confirmation
   explicite du fondateur ». Le besoin métier qui a produit le Groupe AOF
   (`docs/PLAN.md`, en-tête « BUILD QUEUE — App « Appel d'offres » ») EST cette
   confirmation : les écrans SPA sont désormais autorisés. WIR166 reste `[x]`
   (une tâche done ne se réécrit pas) — la réouverture vit ICI, dans le
   commentaire, et dans la ligne DONE LOG de ce même run.

   `order: 57` — et non 56, DÉJÀ pris par `features/adsengine/module.config.jsx`
   (nav « PUBLICITÉ », section réelle). `accent: 'brass'` — même famille
   croissance/commercial que ventes/marketing/pos/adsengine (VX8).

   Les routes ci-dessous pointent, pour Affaires / Tableau de bord /
   Bibliothèque, vers les écrans RÉELS livrés par CETTE MÊME lane
   (`frontend/ao-socle`, AOF170/AOF172/AOF173) — présents dans ce commit ou un
   commit suivant de la même lane. Pour Toitures & relevés / Calepinages /
   Dossiers (lanes SÉPARÉES `frontend/ao-toiture`/`ao-calepinage`/`ao-dossier`,
   hors périmètre de cette tâche) et pour la fiche Rentabilité par affaire
   (lane `frontend/ao-directeur`, AOF161 — Files: `rentabilite/
   RentabiliteRoute.jsx`), la route est PRÉ-CÂBLÉE mais rend un SQUELETTE
   générique (`RouteSquelette` ci-dessous, zéro dépendance externe) tant que
   l'écran réel n'est pas livré par sa propre lane — ce fichier a UN SEUL
   propriétaire dans tout le Groupe AOF (AOF7, jamais retouché ailleurs :
   grep confirmé), donc c'est ICI que les 8 destinations de nav sont fixées
   une fois pour toutes.

   `sectionLabels` existant CONSERVÉ TEL QUEL (ne pas renommer/recréer). La
   section reste gatée par `ModuleToggle` (clé `ao`, propagée automatiquement
   par `router/moduleRoutes.jsx` → `router/moduleGating.js`) : sans le module
   actif pour la société, aucune de ces routes/entrées de nav n'apparaît.
   ========================================================================== */

// Écrans réels de CETTE lane (frontend/ao-socle) — lazy, code-splittés.
const DashboardPage = lazy(() => import('./DashboardPage'))
const AffairesList = lazy(() => import('./AffairesList'))
const AffaireDetail = lazy(() => import('./AffaireDetail'))
const BibliothequePage = lazy(() => import('./bibliotheque/BibliothequePage'))
// AOF190 — « Toitures & relevés » n'est plus un squelette : sur téléphone, une
// entrée de nav qui ne mène à rien EST le bouton mort qu'AOF190 interdit. Cet
// écran rend la lecture réelle des toitures et, sous 768 px, le mode MOBILE
// (refus explicites AVEC leur raison + capture photo → repère conservée).
const ToituresPage = lazy(() => import('./toiture/ToituresPage'))

// Squelette générique RÉUTILISABLE pour toute destination de nav dont
// l'écran réel appartient à une AUTRE lane, non encore livré dans CE commit.
// Zéro logique, zéro appel réseau — juste un état vide nommé (jamais une
// page blanche/une erreur). `lazy(() => Promise.resolve(...))` évite tout
// import vers un fichier qui n'existe pas encore.
function RouteSquelette({ titre }) {
  return (
    <EmptyState
      icon={Gavel}
      title={titre}
      description="Écran en construction (lane dédiée du Groupe AOF) — le module reste pleinement exploitable via l'API en attendant."
    />
  )
}
const squelette = (titre) => lazy(() => Promise.resolve({ default: () => <RouteSquelette titre={titre} /> }))

const ROLES = ['normal', 'responsable', 'admin']
// AOF161/l'en-tête du groupe : `ao_rentabilite_voir` est une ELEVATED_PERMISSION
// (non octroyable à un non-admin) — jamais mappée aux rôles Responsable/
// Commercial/Technicien/Viewer.
const ROLES_RENTABILITE = ['admin']
const PERM_RENTABILITE = 'ao_rentabilite_voir'

const config = {
  key: 'ao',
  order: 57,
  nav: {
    label: "APPELS D'OFFRES",
    accent: 'brass',
    items: [
      { to: '/ao', label: 'Tableau de bord', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/affaires', label: 'Affaires', icon: <Briefcase size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/toitures', label: 'Toitures & relevés', icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/calepinages', label: 'Calepinages', icon: <LayoutGrid size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/dossiers', label: 'Dossiers', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/bibliotheque', label: 'Bibliothèque', icon: <BookOpen size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      // L'ÉCONOMIE EST RÉSERVÉE AU DIRECTEUR (en-tête du Groupe AOF) — absente
      // de la nav pour quiconque n'a pas `ao_rentabilite_voir` (jamais un rôle
      // Responsable/Commercial/Technicien).
      { to: '/ao/rentabilite', label: 'Rentabilité', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
    ],
  },
  // routes.meta — du plus spécifique au plus général (voir adsengine, même patron).
  titles: [
    ['/ao/affaires/', "Appels d'offres — Affaire"],
    ['/ao/affaires', "Appels d'offres — Affaires"],
    ['/ao/toitures', "Appels d'offres — Toitures & relevés"],
    ['/ao/calepinages', "Appels d'offres — Calepinages"],
    ['/ao/dossiers', "Appels d'offres — Dossiers"],
    ['/ao/bibliotheque', "Appels d'offres — Bibliothèque"],
    ['/ao/rentabilite', "Appels d'offres — Rentabilité"],
    ['/ao', "Appels d'offres — Tableau de bord"],
  ],
  // sectionLabels — EXISTANT, conservé TEL QUEL (ne pas renommer/recréer).
  sectionLabels: { ao: "Appels d'offres" },
  routes: [
    { path: '/ao', component: DashboardPage, roles: ROLES },
    { path: '/ao/affaires', component: AffairesList, roles: ROLES },
    // AOF171 (cette lane) — fiche affaire, deep-link (pas d'item de nav dédié,
    // même patron que `/publicite/ad/:id`).
    { path: '/ao/affaires/:id', component: AffaireDetail, roles: ROLES },
    { path: '/ao/toitures', component: ToituresPage, roles: ROLES },
    { path: '/ao/calepinages', component: squelette('Calepinages'), roles: ROLES },
    { path: '/ao/dossiers', component: squelette('Dossiers'), roles: ROLES },
    { path: '/ao/bibliotheque', component: BibliothequePage, roles: ROLES },
    { path: '/ao/rentabilite', component: squelette('Rentabilité'), roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
    // AOF161 (lane frontend/ao-directeur) — fiche rentabilité PAR AFFAIRE,
    // deep-link (jamais d'item de nav : contextuel à une affaire). Squelette
    // pour l'instant (même raison que toitures/calepinages/dossiers ci-dessus :
    // `rentabilite/RentabiliteRoute.jsx` n'existe pas encore dans CE commit).
    { path: '/ao/:id/rentabilite', component: squelette('Rentabilité'), roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
  ],
}

export default config
