import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   CAL33 — Client API du module Calepinage autonome (`apps/calepinage`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), JAMAIS un `axios.get`
   direct dans `features/calepinage/`.

   **LA VÉRITÉ EST LE SERVEUR, PAS CE FICHIER.**
   `frontend/src/api/aoApi.js` a longtemps prétendu « publier le contrat que le
   backend enregistre ensuite » : construites en parallèle, les deux lanes ont
   divergé et neuf chemins appelés n'existaient sous AUCUNE route (404 constatée
   en production le 03/08/2026 sur la Bibliothèque AO). Ce fichier-ci ne rejoue
   pas cette faute : chaque chemin ci-dessous est RECOPIÉ d'une source écrite
   AVANT lui, et son test jumeau (`calepinageApi.test.mjs`) le relit à cette
   source — jamais à une supposition.

   LES DEUX SOURCES, DANS CET ORDRE :
     1. `backend/django_core/apps/calepinage/contract_samples/*.json` (PACT10) —
        la clé `endpoint` de chaque échantillon porte le verbe + le chemin EXACT
        tel qu'il sera enregistré. Ces fichiers ont atterri SEULS sur `main`
        avant toute lane productrice, précisément pour que les deux moitiés du
        contrat ne l'inventent pas chacune de son côté.
     2. `docs/PLAN2.md`, Groupe CAL — pour les actions dont l'agrégat n'a pas
        (encore) d'échantillon : le chemin y est écrit dans le texte de la tâche
        qui l'expose (CAL18 `layout`, CAL19 `roof-image`, CAL20 `versions` +
        `restaurer`, CAL21 `variantes` + `retenir`, CAL23 `moteur/resultat`,
        CAL24 `generer-devis`, CAL25 `sync-devis`, CAL231 `design-context`,
        CAL240 `importer-contour-ao`, CAL45 `parametres`).

   UNE SEULE FORME D'URL (décision de structure n°3 du Groupe CAL, et règle n°1
   du README des échantillons) : `/api/django/calepinage/calepinages/<pk>/…`,
   routeur DRF + sous-ressources en `@action` ; les réglages société vivent sous
   `/api/django/calepinage/parametres/`. Aucun autre préfixe n'est servi.

   ÉTAT DU SERVEUR AU MOMENT DE CETTE LANE (à dire, jamais à cacher) :
   `apps/calepinage/` ne porte encore QUE `contract_samples/` — ni `urls.py`, ni
   `views/`. Les routes ci-dessous sont construites en parallèle par les lanes
   backend (CAL4 monte le préfixe, CAL16/CAL17 le CRUD, CAL18-CAL25 les
   actions). C'est exactement la situation que PACT10 organise : le contrat est
   déjà là, les deux moitiés branchent dessus. Tant que `apps/calepinage/urls.py`
   n'existe pas, `scripts/check_api_contract.py` signale ces chemins comme sans
   route serveur — c'est un état TRANSITOIRE attendu, et le test jumeau le dit
   explicitement plutôt que de le masquer.

   AUCUN APPEL RÉSEAU À L'IMPORT : ce module ne fait que DÉCLARER des fonctions.
   ========================================================================== */

// Fabrique CRUD standard sur `/calepinage/<ressource>/`.
const crud = makeResourceFactory(api, '/calepinage')

// Racine du pivot. Écrite UNE fois : toute action ci-dessous s'y accroche, ce
// qui rend une seconde forme d'URL mécaniquement impossible.
const pivot = (id) => `/calepinage/calepinages/${id}/`

const calepinageApi = {
  /* ── Le calepinage lui-même (CAL16 liste + création, CAL17 détail agrégé) ──
     Les filtres de liste sont ceux RÉELLEMENT servis par CAL16 : `lead`,
     `client`, `statut`, `depuis`, `q`. La leçon PV22 est qu'un filtre ignoré
     par le serveur fait ouvrir le mauvais objet — on n'en invente donc aucun
     autre ici. */
  calepinages: {
    ...crud('calepinages'),

    // CAL18 — le document `roof_layout` (contrat v2 : CAL232,
    // `contract_samples/roof_layout_v2.schema.json`). GET relit, POST
    // enregistre ; le serveur ne touche que `roof_layout`/`layout_hash` et ne
    // change AUCUN statut.
    layout: (id) => api.get(`${pivot(id)}layout/`),
    enregistrerLayout: (id, corps) => api.post(`${pivot(id)}layout/`, corps),

    // CAL19 — l'image d'aperçu de toiture, stockée par le MÊME chemin que les
    // ventes (MinIO + URL présignée) ; aucun second chemin de stockage.
    // `corps` est un FormData : on laisse axios poser sa frontière multipart.
    envoyerImage: (id, corps) => api.post(`${pivot(id)}roof-image/`, corps),

    // CAL20 — historique. La restauration REJOUE une version en en créant une
    // NOUVELLE : jamais une réécriture, jamais une suppression d'historique.
    versions: (id) => api.get(`${pivot(id)}versions/`),
    restaurerVersion: (id, versionId) =>
      api.post(`${pivot(id)}versions/${versionId}/restaurer/`),

    // CAL21 — variantes. `retenir` est une ACTION (elle dé-retient la
    // précédente), jamais un PATCH de ressource — même patron qu'AO.
    variantes: (id) => api.get(`${pivot(id)}variantes/`),
    retenirVariante: (id, varianteId) =>
      api.post(`${pivot(id)}variantes/${varianteId}/retenir/`),

    // CAL21 — comparatif des variantes, conforme à
    // `contract_samples/variantes_comparer.json`. Les ÉCARTS viennent du
    // serveur : un écran ne les recalcule jamais.
    comparer: (id) => api.get(`${pivot(id)}comparer/`),

    // CAL243 — les équipements RETENUS et leur complétude de fiche
    // (`contract_samples/calepinage_equipements.json`). Lecture PURE : aucune
    // clé de prix d'achat ni de marge n'y transite (gardé par CAL122).
    equipements: (id) => api.get(`${pivot(id)}equipements/`),

    // CAL244 — le résultat retenu du calepinage
    // (`contract_samples/calepinage_resultat.json`).
    resultat: (id) => api.get(`${pivot(id)}resultat/`),

    // CAL247 — les dossiers réglementaires
    // (`contract_samples/dossiers_reglementaires.json`).
    dossiersReglementaires: (id) => api.get(`${pivot(id)}dossiers-reglementaires/`),

    // CAL231 — le contexte de conception (pin/contour/ville résolus par le
    // serveur, CAL15) : toutes les clés toujours présentes, nulles si la source
    // manque. Aucune coordonnée devinée côté écran.
    designContext: (id) => api.get(`${pivot(id)}design-context/`),

    // CAL240 — reprendre le contour d'une affaire AO. N'écrit QUE le contour du
    // document ; aucune géométrie opposable AO n'est touchée.
    importerContourAo: (id, corps) =>
      api.post(`${pivot(id)}importer-contour-ao/`, corps),

    // CAL24/CAL25 — le devis. Le chemin canonique de création vit dans
    // `apps/ventes/services` et n'est pas doublé : ces deux actions l'appellent.
    // RÈGLE #4 : aucune ligne de devis n'est fabriquée ici, aucun PDF n'est
    // produit, aucun statut n'est écrit par l'écran.
    genererDevis: (id, corps) => api.post(`${pivot(id)}generer-devis/`, corps),
    syncDevis: (id, corps) => api.post(`${pivot(id)}sync-devis/`, corps),
  },

  /* ── Le moteur, porte HTTP NEUTRE (CAL22/CAL23) ──────────────────────────
     `calculer` rend soit le résultat, soit 202 `{job_id}` au-delà du seuil de
     coût (CAL23) ; `resultat(jobId)` suit alors le travail de fond. Une seule
     file, un seul `kind` — jamais une seconde. */
  moteur: {
    calculer: (corps) => api.post('/calepinage/moteur/calculer/', corps),
    // `pose` (contrat `pose.json`) : route servie par CAL78 — appel ajouté avec elle.
    resultat: (jobId) => api.get(`/calepinage/moteur/resultat/${jobId}/`),
  },

  /* ── Réglages société (CAL45) ────────────────────────────────────────────
     UN enregistrement par société, sections JSON. Singleton : pas de `<pk>`,
     GET pour lire, PUT pour écrire. À vide, le serveur garde le comportement
     actuel — aucune valeur par défaut n'est inventée côté écran. */
  parametres: {
    get: () => api.get('/calepinage/parametres/'),
    update: (corps) => api.put('/calepinage/parametres/', corps),
  },
}

export default calepinageApi
