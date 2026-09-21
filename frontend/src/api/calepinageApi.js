import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   CAL33 — Client API du module Calepinage autonome (`apps/calepinage`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), JAMAIS un `axios.get`
   direct dans `features/calepinage/`.

   **LA VÉRITÉ EST LE SERVEUR, PAS CE FICHIER.**
   Un autre client d'API du dépôt a longtemps prétendu « publier le contrat que
   le backend enregistre ensuite » : construites en parallèle, les deux lanes
   ont divergé et neuf chemins appelés n'existaient sous AUCUNE route (404
   constatée en production le 03/08/2026). Ce fichier-ci ne rejoue
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
        CAL45 `parametres`).

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

    // CAL199/CAL246 — les calepinages marqués MODÈLE de la société (drapeau
    // `records.Tag`, jamais un champ propre). Lecture pure.
    modeles: () => api.get('/calepinage/calepinages/modeles/'),

    // CAL18 — le document `roof_layout` (contrat v2 : CAL232,
    // `contract_samples/roof_layout_v2.schema.json`). GET relit, POST
    // enregistre ; le serveur ne touche que `roof_layout`/`layout_hash` et ne
    // change AUCUN statut.
    layout: (id) => api.get(`${pivot(id)}layout/`),
    enregistrerLayoutCalepinage: (id, corps) => api.post(`${pivot(id)}layout/`, corps),

    // CAL19 — l'image d'aperçu de toiture, stockée par le MÊME chemin que les
    // ventes (MinIO + URL présignée) ; aucun second chemin de stockage.
    // `corps` est un FormData : on laisse axios poser sa frontière multipart.
    envoyerImage: (id, corps) => api.post(`${pivot(id)}roof-image/`, corps),

    // CAL52 — les photos de site (drone/oblique/sol), MÊME magasin que
    // `roof-image`. `corps` est un FormData (photo, genre, prise_le, legende).
    photos: (id) => api.get(`${pivot(id)}photos/`),
    ajouterPhoto: (id, corps) => api.post(`${pivot(id)}photos/`, corps),
    // CAL53 — le calage (4 coins [latitude, longitude]) d'UNE photo de site,
    // rechargé tel quel à la réouverture. `null` efface le calage.
    calerPhoto: (id, photoId, coins) =>
      api.patch(`${pivot(id)}photos/${photoId}/calage/`,
        { calage: coins ? { coins } : null }),

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

    // CAL92/93 — le profil d'horizon PVGIS du site (`printhorizon`),
    // contrat `contract_samples/calepinage_horizon.json`. Lecture PURE :
    // n'enregistre rien — `HorizonPanel.jsx` persiste ensuite le profil
    // choisi via `layout`/`enregistrerLayoutCalepinage` (CAL18).
    horizon: (id) => api.get(`${pivot(id)}horizon/`),

    // CAL159 — le dimensionnement du pompage (puits, besoin, réservoir,
    // courbe + point de fonctionnement, 12 volumes mensuels, pompe/variateur),
    // contrat `contract_samples/calepinage_pompage.json`. POST parce que
    // l'entrée est une SAISIE ; le serveur n'écrit RIEN.
    pompage: (id, corps) => api.post(`${pivot(id)}pompage/`, corps),

    // CAL244 — le résultat retenu du calepinage
    // (`contract_samples/calepinage_resultat.json`).
    resultat: (id) => api.get(`${pivot(id)}resultat/`),

    /* CAL125 — l'ENTRÉE du calcul électrique. Le matériel est DÉSIGNÉ et les
       longueurs/températures sont SAISIES ; la réponse est le `resultat`
       recalculé. CAL234 y fait voyager `affectation_manuelle` : c'est LÀ, et
       là seulement, qu'une affectation faite à la main est ENREGISTRÉE. */
    enregistrerEntreeElectrique: (id, corps) =>
      api.post(`${pivot(id)}entree-electrique/`, corps),

    /* CAL128 — le VERDICT à chaud, sans rien persister (garde en lecture).
       CAL234 : l'atelier y envoie l'affectation PROPOSÉE sous la MÊME clé
       `affectation_manuelle`, et lit les bloquants NOMMÉS (contrainte, pan,
       chaîne) avant de décider d'enregistrer. */
    evaluerElectrique: (id, corps) =>
      api.post(`${pivot(id)}evaluer-electrique/`, corps),

    // CAL195 — le schéma unifilaire du calepinage, en SVG inline. Le SVG est
    // composé PAR LE SERVEUR (même moteur que le devis, `core.electrique`) :
    // l'écran l'affiche, il ne dessine rien. `svg: null` + `bloquants` quand
    // la conception ne permet pas de dessiner — jamais un schéma approximatif.
    schemaUnifilaire: (id) => api.get(`${pivot(id)}schema-unifilaire/`),

    // CAL247 — les dossiers réglementaires
    // (`contract_samples/dossiers_reglementaires.json`).
    dossiersReglementaires: (id) => api.get(`${pivot(id)}dossiers-reglementaires/`),

    // CAL231 — le contexte de conception (pin/contour/ville résolus par le
    // serveur, CAL15) : toutes les clés toujours présentes, nulles si la source
    // manque. Aucune coordonnée devinée côté écran.
    designContext: (id) => api.get(`${pivot(id)}design-context/`),

    // SOLMVP15 — `importer-contour-ao` (CAL240) vivait ici. L'endpoint est
    // parti avec l'app d'appels d'offres, qui sort du produit : il n'y a plus
    // d'affaire dont reprendre le contour. Le contour de l'atelier reste
    // `roof_layout.outline` (v2), posé par le tracé sur carte.

    // CAL24/CAL25 — le devis. Le chemin canonique de création vit dans
    // `apps/ventes/services` et n'est pas doublé : ces deux actions l'appellent.
    // RÈGLE #4 : aucune ligne de devis n'est fabriquée ici, aucun PDF n'est
    // produit, aucun statut n'est écrit par l'écran.
    genererDevis: (id, corps) => api.post(`${pivot(id)}generer-devis/`, corps),
    syncDevis: (id, corps) => api.post(`${pivot(id)}sync-devis/`, corps),

    /* CALX27 — la levée du VERROU (CAL207, `views/verrou.py`). L'action
       existait, testée, et n'avait aucun consommateur : l'atelier affichait un
       bandeau « lecture seule » sans aucune sortie. Elle ne touche AUCUN
       statut de devis (règle #4) ; le serveur la trace au journal et rend
       `{calepinage, verrouille, deverrouille}`. Gardée par `calepinage_gerer`
       côté serveur — l'écran cache l'affordance avec le MÊME code. */
    deverrouiller: (id) => api.post(`${pivot(id)}deverrouiller/`, {}),

    // CALX19 — l'INVENTAIRE des sorties d'un calepinage (planche, plans, note
    // de calcul, DXF, tableurs, pack technique), contrat
    // `contract_samples/calepinage_sorties.json`. Lecture PURE : ne produit
    // aucun document, dit seulement ce qui existe et pourquoi une sortie
    // manque quand elle manque.
    sorties: (id) => api.get(`${pivot(id)}sorties/`),
    // CALX19 — le téléchargement GÉNÉRIQUE d'UNE sortie de cet inventaire :
    // `endpoint` vient TOUJOURS de l'entrée servie par `sorties()` ci-dessus
    // (déjà préfixée `/api/django/…`, l'intercepteur d'`api/axios.js` ne la
    // préfixe pas deux fois) — jamais un chemin reconstruit à la main ici.
    // `params` porte `?feuille=` pour le tableur CSV (CALX23), vide ailleurs.
    telechargerSortie: (endpoint, params) =>
      api.get(endpoint, { responseType: 'blob', params }),

    // CALX24 — compose le dossier technique (planche + note de calcul
    // fusionnées) et le DÉPOSE dans la GED : en ÉCRITURE (POST), gardée par
    // `calepinage_gerer` côté serveur. Réponse JSON normale (jamais un blob) :
    // `{document, nom, pieces, pages_attendues, signalements}`. Aucun import
    // `apps.ged` ici — l'écran ne parle qu'à CETTE action.
    composerPackTechnique: (id) => api.post(`${pivot(id)}pack-technique/`),

    // CALX28 — export/import du DOCUMENT de conception (`roof_layout`,
    // schéma v2 — `views/io_layout.py`, CAL216). `exporterConception` rend
    // `{roof_layout, layout_hash, schema_version}` TEL QUEL ; `importerConception`
    // VALIDE STRICTEMENT côté serveur avant écriture, et refuse en NOMMANT le
    // CHEMIN JSON du premier champ fautif (`champ`) — jamais une validation
    // recalculée ici. Distinct de `layout()`/`enregistrerLayoutCalepinage`
    // (CAL18, l'ATELIER) : ce sont les portes ÉCHANGE / round-trip fichier.
    exporterConception: (id) => api.get(`${pivot(id)}export-layout/`),
    importerConception: (id, document) => api.post(`${pivot(id)}import-layout/`, document),

    // CALX18 — les postes de pertes (catalogue CAL139, `views/simulation.py`) :
    // lecture pure du catalogue + des postes persistés, et leur enregistrement.
    pertes: (id) => api.get(`${pivot(id)}pertes/`),
    enregistrerPertes: (id, corps) => api.post(`${pivot(id)}enregistrer-pertes/`, corps),

    // CALX25 — le relevé terrain (chaînes de cotes, CAL64, `views/releve.py`).
    // GET rend l'historique (`releves`) ; POST enregistre une chaîne ET rend
    // le relevé créé PLUS l'historique à jour (contrat `calepinage_releve.json`).
    releve: (id) => api.get(`${pivot(id)}releve/`),
    enregistrerReleve: (id, corps) => api.post(`${pivot(id)}releve/`, corps),
  },

  /* ── Le moteur, porte HTTP NEUTRE (CAL22/CAL23) ──────────────────────────
     `calculer` rend soit le résultat, soit 202 `{job_id}` au-delà du seuil de
     coût (CAL23) ; `resultat(jobId)` suit alors le travail de fond. Une seule
     file, un seul `kind` — jamais une seconde. */
  moteur: {
    calculer: (corps) => api.post('/calepinage/moteur/calculer/', corps),
    // `pose` (contrat `pose.json`) : le relevé voyage sous `demande`, la
    // réponse porte la pose ET son régime de preuve.
    pose: (corps) => api.post('/calepinage/moteur/pose/', corps),
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
