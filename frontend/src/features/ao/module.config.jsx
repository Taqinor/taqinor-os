/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Link } from 'react-router-dom'
import {
  Trophy, LayoutDashboard, Briefcase, Building2, LayoutGrid, FolderKanban, BookOpen, Wallet,
  FileCheck2,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'
import { Button, EmptyState } from '../../ui'

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

   RECÂBLAGE 2026-08-03 — quatre destinations rendaient un squelette « écran
   en construction » alors que, pour certaines, l'écran RÉEL dormait sur le
   disque sans être importé nulle part. Chacune a été revérifiée fichier par
   fichier ; le résultat est écrit route par route ci-dessous. Trois régimes,
   et un seul principe : **on ne monte jamais un écran sans les données qu'il
   exige** (il tomberait en erreur, ce qui est pire qu'une explication), et on
   ne laisse jamais une entrée de nav ne mener nulle part.
     * écran réel branché  — Tableau de bord, Affaires, fiche affaire, création
       d'affaire, Toitures & relevés, Bibliothèque, dossier `/ao/dossiers/:id` ;
     * écran réel CONTEXTUEL, atteint depuis une affaire — la destination de
       premier niveau (Calepinages, Dossiers) explique le chemin et y renvoie
       (`RouteViaAffaire`) plutôt que de charger un objet sans identifiant ;
     * écran INEXISTANT à l'époque — Rentabilité, qui gardait un squelette
       disant honnêtement qu'il n'était pas encore construit. PACT75
       (2026-08-07) l'a remplacé par `EconomieDirecteur`, réel.
   Ce fichier a UN SEUL propriétaire dans tout le Groupe AOF (AOF7), donc c'est
   ICI que les destinations de nav sont fixées une fois pour toutes.

   `sectionLabels` existant CONSERVÉ TEL QUEL (ne pas renommer/recréer). La
   section reste gatée par `ModuleToggle` (clé `ao`, propagée automatiquement
   par `router/moduleRoutes.jsx` → `router/moduleGating.js`) : sans le module
   actif pour la société, aucune de ces routes/entrées de nav n'apparaît.
   ========================================================================== */

// Écrans réels de CETTE lane (frontend/ao-socle) — lazy, code-splittés.
const DashboardPage = lazy(() => import('./DashboardPage'))
const AffairesList = lazy(() => import('./AffairesList'))
const AffaireDetail = lazy(() => import('./AffaireDetail'))
// Formulaire de CRÉATION d'une affaire. Sans lui, le module n'avait AUCUN
// chemin de création : la liste pouvait tout lister sauf produire une affaire.
const AffaireForm = lazy(() => import('./AffaireForm'))
const BibliothequePage = lazy(() => import('./bibliotheque/BibliothequePage'))
// Écran RÉEL du dossier de soumission. Il lit son identifiant dans l'URL
// (`useParams().id`, avec repli sur une prop `dossierId`) : il se monte donc
// en deep-link `/ao/dossiers/:id`, JAMAIS sur `/ao/dossiers` sans identifiant
// (il interrogerait le serveur sur un id `undefined` → écran en erreur).
const DossierPage = lazy(() => import('./dossier/DossierPage'))
// AOF190 — « Toitures & relevés » n'est plus un squelette : sur téléphone, une
// entrée de nav qui ne mène à rien EST le bouton mort qu'AOF190 interdit. Cet
// écran rend la lecture réelle des toitures et, sous 768 px, le mode MOBILE
// (refus explicites AVEC leur raison + capture photo → repère conservée).
const ToituresPage = lazy(() => import('./toiture/ToituresPage'))
// PACT73 — bibliothèque des pièces administratives (AOF137), scopée société :
// une pièce (attestation fiscale, CNSS, RC…) s'enregistre une fois et se
// rattache à plusieurs affaires. Écran de premier niveau, comme Bibliothèque.
const PiecesAdministratives = lazy(() => import('./PiecesAdministratives'))
// PACT75 — économie DIRECTEUR (coût de revient, cibles de marge). Remplace le
// squelette honnête « pas encore construit » des DEUX routes de rentabilité :
// `aoRentabiliteApi` (export SÉPARÉ) était câblé au bon endpoint sans écran.
const EconomieDirecteur = lazy(() => import('./economie/EconomieDirecteur'))

// PACT75 — `RouteSquelette`/`squelette()` ont PERDU leur dernier appelant
// (Rentabilité montait le squelette honnête « pas encore construit » sur ses
// deux routes ; les deux montent désormais `EconomieDirecteur`). Retirés —
// pas de fonction morte qui se croit vivante (même principe que la garde
// `check_ecrans_atteignables.py`).

/* Destination dont l'écran EXISTE, mais qui est CONTEXTUELLE : elle a besoin
   de l'identifiant d'un objet (un dossier, un calepinage) et n'a donc de sens
   qu'ouverte depuis une affaire. Il n'existe pas d'écran de LISTE pour ces
   objets, et on n'en invente pas un ici : monter l'écran réel sans les données
   qu'il exige produirait une erreur — pire qu'une explication. On dit donc où
   la trouver, avec le lien qui y mène. */
function RouteViaAffaire({ titre, description, icon }) {
  return (
    <EmptyState
      icon={icon}
      title={titre}
      description={description}
      action={(
        <Button asChild size="sm" variant="outline">
          <Link to="/ao/affaires">Ouvrir la liste des affaires</Link>
        </Button>
      )}
    />
  )
}
const viaAffaire = (props) => lazy(() => Promise.resolve({ default: () => <RouteViaAffaire {...props} /> }))

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
    // Glyphe d'APP (contrat ODY34/appGlyph — unique sur tout le portail) :
    // le trophée = l'appel d'offres GAGNÉ, distinct du Briefcase des affaires.
    icon: appGlyph(Trophy),
    label: "APPELS D'OFFRES",
    accent: 'brass',
    items: [
      { to: '/ao', label: 'Tableau de bord', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/affaires', label: 'Affaires', icon: <Briefcase size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/toitures', label: 'Toitures & relevés', icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/calepinages', label: 'Calepinages', icon: <LayoutGrid size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/dossiers', label: 'Dossiers', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/ao/bibliotheque', label: 'Bibliothèque', icon: <BookOpen size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      {
        to: '/ao/pieces-administratives',
        label: 'Pièces administratives',
        icon: <FileCheck2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      // L'ÉCONOMIE EST RÉSERVÉE AU DIRECTEUR (en-tête du Groupe AOF) — absente
      // de la nav pour quiconque n'a pas `ao_rentabilite_voir` (jamais un rôle
      // Responsable/Commercial/Technicien).
      { to: '/ao/rentabilite', label: 'Rentabilité', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
    ],
  },
  // routes.meta — du plus spécifique au plus général (voir adsengine, même patron).
  titles: [
    // `/ao/affaires/nouveau` AVANT `/ao/affaires/` : la correspondance se fait
    // par PRÉFIXE, du plus spécifique au plus général — inversés, la création
    // s'intitulerait « Affaire ».
    ['/ao/affaires/nouveau', "Appels d'offres — Nouvelle affaire"],
    ['/ao/affaires/', "Appels d'offres — Affaire"],
    ['/ao/affaires', "Appels d'offres — Affaires"],
    ['/ao/toitures', "Appels d'offres — Toitures & relevés"],
    ['/ao/calepinages', "Appels d'offres — Calepinages"],
    ['/ao/dossiers/', "Appels d'offres — Dossier de soumission"],
    ['/ao/dossiers', "Appels d'offres — Dossiers"],
    ['/ao/bibliotheque', "Appels d'offres — Bibliothèque"],
    ['/ao/pieces-administratives', "Appels d'offres — Pièces administratives"],
    ['/ao/rentabilite', "Appels d'offres — Rentabilité"],
    ['/ao', "Appels d'offres — Tableau de bord"],
  ],
  // sectionLabels — EXISTANT, conservé TEL QUEL (ne pas renommer/recréer).
  sectionLabels: { ao: "Appels d'offres" },
  routes: [
    { path: '/ao', component: DashboardPage, roles: ROLES },
    { path: '/ao/affaires', component: AffairesList, roles: ROLES },
    // CRÉATION D'UNE AFFAIRE. **Déclarée AVANT `/ao/affaires/:id`** : sinon
    // « nouveau » serait capté comme un identifiant d'affaire et l'écran de
    // création serait injoignable.
    { path: '/ao/affaires/nouveau', component: AffaireForm, roles: ROLES },
    // AOF171 (cette lane) — fiche affaire, deep-link (pas d'item de nav dédié,
    // même patron que `/publicite/ad/:id`).
    { path: '/ao/affaires/:id', component: AffaireDetail, roles: ROLES },
    { path: '/ao/toitures', component: ToituresPage, roles: ROLES },
    // `CalepinageStudio` existe (`calepinage/CalepinageStudio.jsx`) mais exige
    // `{ calepinageId }`, et son hook interroge `aoApi.calepinages.*`, que le
    // client API déclare NON CONSTRUIT côté serveur (501 nommé). Le monter ici
    // sans identifiant afficherait donc une erreur, pas un atelier. Aucun écran
    // de liste des calepinages n'existe : on n'en fabrique pas un faux.
    {
      path: '/ao/calepinages',
      component: viaAffaire({
        titre: 'Calepinages',
        icon: LayoutGrid,
        description: "Un calepinage s’ouvre depuis l’affaire à laquelle il appartient : ouvrez l’affaire, puis sa toiture. Il n’y a pas de vue d’ensemble des calepinages.",
      }),
      roles: ROLES,
    },
    // L'écran RÉEL du dossier vit sur `/ao/dossiers/:id` (juste en dessous).
    // Cette entrée de premier niveau ne peut pas lui inventer un identifiant —
    // elle indique où le trouver plutôt que de charger un dossier `undefined`.
    {
      path: '/ao/dossiers',
      component: viaAffaire({
        titre: 'Dossiers de soumission',
        icon: FolderKanban,
        description: "Un dossier de soumission appartient à une affaire : ouvrez l’affaire concernée pour accéder à ses pièces, ses échéances et ses contrôles avant dépôt.",
      }),
      roles: ROLES,
    },
    // Écran réel, deep-link (il lit `:id` via `useParams`).
    { path: '/ao/dossiers/:id', component: DossierPage, roles: ROLES },
    { path: '/ao/bibliotheque', component: BibliothequePage, roles: ROLES },
    { path: '/ao/pieces-administratives', component: PiecesAdministratives, roles: ROLES },
    // RENTABILITÉ — PACT75 : `EconomieDirecteur` remplace le squelette. Le
    // client `aoRentabiliteApi` était câblé au bon endpoint (AOF161) sans
    // écran ; les DEUX routes gardent EXACTEMENT le même rôle/permission
    // élevés qu'avant — c'est la garde qui protège la marge, jamais retouchée
    // ici.
    { path: '/ao/rentabilite', component: EconomieDirecteur, roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
    // AOF161 — fiche rentabilité PAR AFFAIRE, deep-link (jamais d'item de nav :
    // contextuel à une affaire, l'id de l'URL est celui de L'AFFAIRE — voir
    // `EconomieDirecteur`, qui résout l'économie via `aoRentabiliteApi.parAffaire`).
    { path: '/ao/:id/rentabilite', component: EconomieDirecteur, roles: ROLES_RENTABILITE, perm: PERM_RENTABILITE },
  ],
}

export default config
