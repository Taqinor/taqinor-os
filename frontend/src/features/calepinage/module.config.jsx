import { lazy } from 'react'
import {
  BadgeCheck, Columns3, FileStack, Grid3x3, Library, LayoutGrid, MoveHorizontal, PlusCircle, SlidersHorizontal,
  Wrench,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   CAL34 — LA PORTE AUTONOME du module Calepinage.
   ----------------------------------------------------------------------------
   DÉCISION FONDATEUR (Reda, 19/09/2026, n°3, verbatim) : « the new calpinage
   module should work exactly the same as it is right now in the CRM just have
   more features. and of course we can access it from the standalone module, and
   pick whatever client or lead and make its calpinage. »

   D3 — cette porte n'existait pas à l'origine : le seul accès au calepinage
   passait par un devis (`router/index.jsx`). Ce module est une porte SUPPLÉMENTAIRE, jamais un
   remplacement : aucune ligne de `LeadWorkspace.jsx` ni du mode `devis` de
   `ToitureDesign.jsx` n'est touchée par cette lane.

   `key: 'calepinage'` — IDENTIQUE au `module_manifest` backend posé par CAL4
   (`apps/calepinage/apps.py`). C'est l'ancrage de corrélation vérifié par
   `scripts/check_modules.py` ET la clé que `router/moduleRoutes.jsx` propage
   automatiquement vers `router/moduleGating.js` : module éteint pour la société
   ⇒ zéro entrée de nav et routes en 404, sans aucun tableau à tenir à la main.

   `order: 98` — 97 est le maximum occupé par un `module.config.jsx` du dépôt au
   moment de cette lane (vérifié), 98 est donc libre ; une collision d'`order`
   est attrapée par le test de registre existant.

   `nav.icon` (ODY34) — `Grid3x3`, le quadrillage des modules posés sur un pan
   de toit. Glyphe UNIQUE sur tout le portail : `lib/apps/appGlyph.test.jsx`
   interdit tout doublon, et `LayoutGrid` reste réservé à l'item de liste ci-dessous, jamais au glyphe d'app.

   ORDRE DES ROUTES — `/calepinage/nouveau` est déclarée AVANT `/calepinage/:id`.
   Inversées, « nouveau » serait capté comme un identifiant de calepinage et
   l'écran de création deviendrait injoignable.
   ========================================================================== */

const ROLES = ['normal', 'responsable', 'admin']

/* R2-20 (recette 22/11/2026, Q4) — l'app n'apparaît dans le lanceur, la nav et
   les routes que pour un compte qui a le droit de la LIRE : même clé que le
   serveur (`apps/calepinage/permissions.py::CAL_VOIR`) et même sémantique de
   repli (`HasPermissionOrLegacy` : rôle fin → la permission décide ; compte
   légacy → palier responsable/admin). Un Technicien (qui n'a pas
   `calepinage_voir`) ne voit plus une app qui refuse tout. Aucun droit ajouté
   ni retiré ; son « plan de pose » de chantier ne passe pas par cette app. */
const GARDE_LECTURE = { roles: ROLES, perm: 'calepinage_voir', permRepliPalier: true }

/* ── L'ATELIER 3D DU CALEPINAGE — le MÊME builder, un quatrième mode ───────
   `pages/ventes/ToitureDesign` héberge déjà le builder 3D et sert les modes
   `lead`, `devis` et `calepinage` sur le MÊME écran ; le mode `calepinage` (CAL37, lane
   `frontend/atelier`) le réutilise tel quel sur un CALEPINAGE. Une seconde
   implémentation de la toiture 3D serait la garantie de deux calepinages qui
   divergent.
   `buildModuleRoutes` monte `<Comp />` SANS props : le mode est donc figé par
   cette enveloppe lazy. */
const AtelierCalepinage = lazy(async () => {
  const { default: ToitureDesign } = await import('../../pages/ventes/ToitureDesign')
  return { default: () => <ToitureDesign mode="calepinage" /> }
})

/* ACAL407 — les 13 routes profondes `/calepinage/:id/<cle>` ne montent plus de
   panneau : elles REDIRIGENT vers `/calepinage/:id?onglet=<cle>` (une adresse
   par panneau). `variantes` et `photos` redirigent aussi (ACAL409 : onglets du rail). */
const RedirectionOnglet = lazy(() => import('./atelier/RedirectionOnglet'))
/* Coque (maquettes 22/11) — l'atelier et les deux écrans de téléphone sont PLEIN ÉCRAN
   (`plein: true` : ni barre latérale ni en-tête de l'ERP, `router/moduleRoutes.jsx`). */
const ReleveVisite = lazy(() => import('./releve/ReleveVisite'))
const VueClient = lazy(() => import('./client/VueClient'))
// Coque — la page « Démarrage rapide » des réglages (le composant de la lane réglages, dans son cadre).
const DemarrageRapidePage = lazy(() => import('./DemarrageRapidePage'))

// CAL35 — la LISTE réelle : vignettes, filtres RÉELLEMENT servis par CAL16,
// pagination et état vide qui explique le geste de création.
const CalepinageList = lazy(() => import('./CalepinageList'))
// CAL36 — l'écran de CRÉATION : choisir un lead OU un client, recherche bornée
// société côté serveur, contexte géographique lu et jamais deviné.
const CalepinageNouveau = lazy(() => import('./CalepinageNouveau'))
// ACAL409 — `VariantesCompare` (CAL42) et `PhotoSiteCalage` (CAL53) sont des onglets du rail (`atelier/onglets.js`).
// CAL201 — la bibliothèque du module (presets, kits, modèles, favoris) :
// société active respectée, lecture seule sans `calepinage_gerer`.
const Bibliotheque = lazy(() => import('./Bibliotheque'))
/* CAL165 — les SOURCES des paramètres normatifs de la société (coefficients de
   norme électrique, paramètres de lestage, dégagements) : un paramètre sans
   provenance déclarée y est marqué « non sourcée » et sa valeur n'est pas
   affichée. Réglages SOCIÉTÉ, donc un item de nav permanent et non un
   deep-link : il n'y a aucun calepinage à désigner. */
const SourcesNormatives = lazy(() => import('./commun/Provenance'))
/* CALX69 — les RÉGLAGES de simulation et d'électrique de la société
   (`services/parametres_cles.py`, sections `simulation`/`electrique_societe`
   ouvertes par CALX145) : chaque clé se saisit avec sa provenance, sans quoi
   elle n'est pas enregistrée. Réglages SOCIÉTÉ comme CAL165 ci-dessus, donc
   un item de nav permanent et non un deep-link : il n'y a aucun calepinage à
   désigner. */
const ReglagesSimulation = lazy(() => import('./reglages/ReglagesSimulation'))
// ACAL242 — le dépôt des gabarits de dossiers réglementaires (lien depuis les réglages).
const ReglagesGabarits = lazy(() => import('./reglages/ReglagesGabarits'))
// ACAL559 — le catalogue des systèmes de fixation de la société (niveau expert).
const ReglagesFixation = lazy(() => import('./reglages/ReglagesFixation'))
// ACAL893 — le défaut de la société (allée technique, allées de circulation par pays), sorti de l'atelier.
const ReglagesAllees = lazy(() => import('./reglages/ReglagesAllees'))
/* CALX342 — la COMPARAISON de 1 à 5 calepinages distincts (contrat
   `calepinage_comparaison_projets.json`, CALX331). Elle ne désigne AUCUN
   calepinage dans son chemin (la sélection voyage en `?ids=`) : une route de
   LISTE, atteinte depuis `CalepinageList.jsx` (mode « Comparer »). */
const ComparaisonProjets = lazy(() => import('./ComparaisonProjets'))

const config = {
  key: 'calepinage',
  order: 98,
  nav: {
    icon: appGlyph(Grid3x3),
    label: 'CALEPINAGE',
    // Même famille visuelle que les modules métier solaires (ventes).
    accent: 'brass',
    items: [
      {
        to: '/calepinage',
        label: 'Calepinages',
        icon: <LayoutGrid size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        to: '/calepinage/nouveau',
        label: 'Nouveau calepinage',
        icon: <PlusCircle size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // CAL201 — presets/kits/modèles/favoris : un item de nav PERMANENT,
        // contrairement aux panneaux contextuels d'UN calepinage ci-dessous.
        to: '/calepinage/bibliotheque',
        label: 'Bibliothèque',
        icon: <Library size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // CAL165 — la provenance des paramètres normatifs de la société.
        to: '/calepinage/sources',
        label: 'Sources des paramètres',
        icon: <BadgeCheck size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // CALX69 — les réglages de simulation et d'électrique de la société.
        to: '/calepinage/reglages',
        label: 'Réglages simulation',
        icon: <SlidersHorizontal size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // ACAL242 — les gabarits des dossiers réglementaires de la société.
        to: '/calepinage/reglages/gabarits',
        label: 'Gabarits des dossiers',
        icon: <FileStack size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // ACAL559 — les systèmes de fixation de la société (rails, crochets, lests).
        to: '/calepinage/reglages/fixation',
        label: 'Systèmes de fixation',
        icon: <Wrench size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // ACAL893 — le défaut de la société pour les allées (plus dans l'atelier).
        to: '/calepinage/reglages/allees',
        label: 'Allées',
        icon: <MoveHorizontal size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
      {
        // CALX342 — la comparaison de 1 à 5 calepinages ; sans sélection,
        // l'écran renvoie choisir dans la liste (mode « Comparer »).
        to: '/calepinage/comparaison',
        label: 'Comparer',
        icon: <Columns3 size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GARDE_LECTURE,
      },
    ],
  },
  // `titles` — correspondance par PRÉFIXE, du plus spécifique au plus général.
  titles: [
    ['/calepinage/nouveau', 'Calepinage — Nouveau calepinage'],
    ['/calepinage/bibliotheque', 'Calepinage — Bibliothèque'],
    ['/calepinage/sources', 'Calepinage — Sources des paramètres'],
    ['/calepinage/reglages/gabarits', 'Calepinage — Gabarits des dossiers'],
    ['/calepinage/reglages/fixation', 'Calepinage — Systèmes de fixation'],
    ['/calepinage/reglages/allees', 'Calepinage — Allées'],
    ['/calepinage/reglages/demarrage-rapide', 'Calepinage — Démarrage rapide'],
    ['/calepinage/reglages', 'Calepinage — Réglages simulation'],
    ['/calepinage/comparaison', 'Calepinage — Comparaison'],
    ['/calepinage/', 'Calepinage — Atelier'],
    ['/calepinage', 'Calepinage — Calepinages'],
  ],
  sectionLabels: { calepinage: 'Calepinage' },
  routes: [
    { path: '/calepinage', component: CalepinageList, ...GARDE_LECTURE },
    // AVANT `/calepinage/:id` — sinon « nouveau »/« bibliotheque » seraient lus
    // comme un identifiant.
    { path: '/calepinage/nouveau', component: CalepinageNouveau, ...GARDE_LECTURE },
    { path: '/calepinage/bibliotheque', component: Bibliotheque, ...GARDE_LECTURE },
    // CAL165 — AVANT `/calepinage/:id` : « sources » n'est pas un identifiant.
    { path: '/calepinage/sources', component: SourcesNormatives, ...GARDE_LECTURE },
    // CALX69 — AVANT `/calepinage/:id` : « reglages » n'est pas un identifiant.
    { path: '/calepinage/reglages', component: ReglagesSimulation, ...GARDE_LECTURE },
    // ACAL242 — AVANT `/calepinage/:id` : « reglages/gabarits » n'est pas un identifiant.
    { path: '/calepinage/reglages/gabarits', component: ReglagesGabarits, ...GARDE_LECTURE },
    // ACAL559 — AVANT `/calepinage/:id` : « reglages/fixation » n'est pas un identifiant.
    { path: '/calepinage/reglages/fixation', component: ReglagesFixation, ...GARDE_LECTURE },
    // ACAL893 — AVANT `/calepinage/:id` : « reglages/allees » n'est pas un identifiant.
    { path: '/calepinage/reglages/allees', component: ReglagesAllees, ...GARDE_LECTURE },
    // Coque — AVANT `/calepinage/:id` ; lien depuis le volet « Avancé » de l'atelier.
    { path: '/calepinage/reglages/demarrage-rapide', component: DemarrageRapidePage, ...GARDE_LECTURE },
    // CALX342 — AVANT `/calepinage/:id` : « comparaison » n'est pas un identifiant.
    { path: '/calepinage/comparaison', component: ComparaisonProjets, ...GARDE_LECTURE },
    /* Atelier d'UN calepinage — deep-link, jamais un item de nav : il est
       contextuel à un objet. C'est la cible de
       la redirection après création (CAL36).

       CALX1 — C'EST AUSSI L'ADRESSE DE TOUS LES ONGLETS : `/calepinage/:id
       ?onglet=<cle>`, où `<cle>` est une clé de `atelier/onglets.js` et vaut
       EXACTEMENT le dernier segment de la route profonde correspondante
       ci-dessous. Le rail est monté par `AtelierPanneaux.jsx`. Les routes
       profondes restent DÉCLARÉES comme liens profonds (un lien envoyé hier doit
       encore s'ouvrir demain) mais REDIRIGENT vers `?onglet=` (ACAL407), et
       aucune n'est à ajouter ici pour un onglet neuf — un panneau de plus,
       c'est une ligne de plus dans `atelier/onglets.js`, rien d'autre. */
    { path: '/calepinage/:id', component: AtelierCalepinage, plein: true, ...GARDE_LECTURE },
    // contextuelle: le relevé de visite au téléphone d'UN calepinage, ouvert depuis son atelier (volet « Avancé »).
    { path: '/calepinage/:id/releve', component: ReleveVisite, plein: true, ...GARDE_LECTURE },
    // contextuelle: la vue à montrer au client d'UN calepinage, ouverte depuis son atelier (volet « Avancé »).
    { path: '/calepinage/:id/client', component: VueClient, plein: true, ...GARDE_LECTURE },
    // contextuelle: comparatif d'UN calepinage, ouvert depuis son atelier (CAL37) — une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/variantes', component: RedirectionOnglet, ...GARDE_LECTURE },
    // CAL121
    // contextuelle: les fiches techniques trouées des équipements de CE calepinage — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/fiches', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL159) le dimensionnement de pompage de CE calepinage — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/pompage', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL63) caler le plan importé de CE calepinage sur la carte — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/plan', component: RedirectionOnglet, ...GARDE_LECTURE },
    // CAL53 — caler une photo de site (CAL52) de CE calepinage sur la carte.
    { path: '/calepinage/:id/photos', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL58) la pente de CE calepinage, par l'un des trois modes de saisie — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/pente', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL89) le champ au SOL de CE calepinage (mode terrain) — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/terrain', component: RedirectionOnglet, ...GARDE_LECTURE },
    // CAL91 — l'ombrière / carport de CE calepinage.
    { path: '/calepinage/:id/ombriere', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: le schéma unifilaire d'UN calepinage, ouvert depuis son atelier (CAL195) — une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/schema', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL236) le panneau Production de CE calepinage — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/production', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL143) le diagramme de pertes de CE calepinage — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/pertes', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: (CAL93) l'horizon lointain d'UN calepinage — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/horizon', component: RedirectionOnglet, ...GARDE_LECTURE },
    // CAL96 — contextuelle : la course du soleil par pan d'UN calepinage.
    { path: '/calepinage/:id/course-soleil', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: les dossiers réglementaires d'UN calepinage, ouverts depuis son atelier (CAL196) — une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/dossiers', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: l'affectation des chaînes d'UN calepinage, corrigée à la main depuis son atelier (CAL234) — une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/affectation', component: RedirectionOnglet, ...GARDE_LECTURE },
    // contextuelle: la détection IA du toit de CE calepinage (ACAL488) — onglet du rail de l'atelier (onglets.js) aussi ouvrable en lien direct ; une entrée de menu permanente n'aurait aucun calepinage à désigner.
    { path: '/calepinage/:id/detection-toit', component: RedirectionOnglet, ...GARDE_LECTURE },
  ],
}

export default config
