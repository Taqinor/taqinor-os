import api from './axios'
import { makeResourceFactory } from './resource'
import { pivot } from './calepinage/_base'
import { projet } from './calepinage/projet'
import { simulation } from './calepinage/simulation'
import { sorties } from './calepinage/sorties'

// ACAL316 — l'en-tête If-Match d'une écriture COMPLÈTE du document (obligatoire côté serveur,
// 428 sans lui) : l'empreinte « document » lue, ou l'ETag vide `""` quand le document est vide.
const jetonIfMatch = (empreinte) => ({ headers: { 'If-Match': empreinte || '""' } })

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

// CALX37 — corps du POST de duplication d'une variante : `nom` saisi prime ;
// sans lui, un nom dérivé de la source évite un POST refusé pour nom vide.
// Fonction PURE (aucun appel réseau) : la garde CAL33 exige que chaque
// `api.<verbe>(` soit le corps direct d'une fonction fléchée.
// ACAL109 — la copie n'emporte JAMAIS le `resultat` : une simulation décrit la
// conception qui l'a produite, pas sa copie (elle se relance).
export function corpsDeCopieVariante(source, nom) {
  const src = source ?? {}
  const nomFinal = nom || (src.nom ? `${src.nom} (copie)` : 'Copie de variante')
  return { nom: nomFinal, roof_layout: src.roof_layout }
}

const calepinageApi = {
  /* ── Le calepinage lui-même (CAL16 liste + création, CAL17 détail agrégé) ──
     Les filtres de liste sont ceux RÉELLEMENT servis par CAL16 : `lead`,
     `client`, `statut`, `depuis`, `q`. La leçon PV22 est qu'un filtre ignoré
     par le serveur fait ouvrir le mauvais objet — on n'en invente donc aucun
     autre ici. */
  calepinages: {
    // ACAL120 — les SEULES méthodes CRUD servies : un calepinage ne se
    // supprime pas (DELETE/PUT ⇒ 405) — archiver est l'unique geste.
    ...(({ list, get, create, update }) => ({ list, get, create, update }))(crud('calepinages')),

    // CAL199/CAL246 — les calepinages marqués MODÈLE de la société (drapeau
    // `records.Tag`, jamais un champ propre). Lecture pure.
    modeles: () => api.get('/calepinage/calepinages/modeles/'),

    // CAL18 — le document `roof_layout` (contrat v2 : CAL232,
    // `contract_samples/roof_layout_v2.schema.json`). GET relit, POST
    // enregistre ; le serveur ne touche que `roof_layout`/`layout_hash` et ne
    // change AUCUN statut.
    layout: (id) => api.get(`${pivot(id)}layout/`),
    // ACAL316 — If-Match OBLIGATOIRE (428 sans jeton) : `empreinte` est l'empreinte « document »
    // lue avec le document (`GET layout/`, design-context) ou rendue par la dernière écriture ;
    // un document encore vide n'en a pas, son jeton est l'ETag vide `""`.
    enregistrerLayoutCalepinage: (id, corps, empreinte) => api.post(`${pivot(id)}layout/`, corps, jetonIfMatch(empreinte)),

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
    // ACAL109 — la clé `variantes` (GET liste brute, sans appelant) est
    // retirée : la liste se lit par `comparer()`.
    retenirVariante: (id, varianteId) =>
      api.post(`${pivot(id)}variantes/${varianteId}/retenir/`),

    // CALX37 — créer une variante (`services.creer_variante`, déjà servi par
    // `POST variantes/`) : `corps` porte `nom`/`roof_layout`/`resultat`, un nom
    // vide est refusé CÔTÉ ÉCRAN avant tout appel (la garde serveur existe
    // aussi, elle n'est jamais la seule).
    creerVariante: (id, corps) => api.post(`${pivot(id)}variantes/`, corps),

    // CALX37 — dupliquer : AUCUNE action serveur dédiée n'existe, c'est un
    // geste d'écran qui relit le détail complet de la source (`roof_layout`/
    // `resultat`, que le comparatif ne publie pas) puis crée une variante
    // neuve avec ce contenu. `nom` (saisi par l'utilisateur) prime ; sans lui,
    // un nom dérivé de la source évite un POST refusé pour nom vide.
    dupliquerVariante: (id, varianteId, nom) =>
      api.get(`${pivot(id)}variantes/${varianteId}/`)
        .then((res) => api.post(`${pivot(id)}variantes/`, corpsDeCopieVariante(res?.data, nom))),

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

    ...sorties,

    ...simulation,

    // CALX109 — les modules que la société peut RÉELLEMENT poser, avec les
    // cotes de leur fiche technique (`views/modules_disponibles.py`, contrat
    // `calepinage_modules_disponibles.json`). L'atelier 3D ne connaissait
    // qu'un module écrit en dur : cette lecture lui sert le catalogue, dans
    // la forme EXACTE du catalogue `modules[]` du document v2 (CALX82), donc
    // sans traduction de clés. Une fiche incomplète est LISTÉE avec son motif
    // et n'est pas sélectionnable ; une liste vide porte son propre motif —
    // l'écran affiche CEUX-LÀ, il n'en invente aucun.
    modulesDisponibles: (id) => api.get(`${pivot(id)}modules-disponibles/`),

    // CALX107 — le FICHIER du plan de fond : son URL servie (pré-signée, même
    // magasin que les photos de site) et sa taille en PIXELS NATURELS
    // (`views/plan_importe.py`, contrat `calepinage_plan_importe.json`).
    // L'atelier sait peindre le calque de fond mais ne parle jamais à Django :
    // c'est l'écran qui va chercher la pièce jointe que le document désigne
    // (`underlay.attachmentId`) et la lui redonne. Une taille illisible vaut
    // `null` avec son motif — l'écran affiche CELUI-LÀ, il n'invente aucune
    // étendue.
    planImporte: (id) => api.get(`${pivot(id)}plan-importe/`),

    // CALX302 — dépose une image PRODUITE PAR LE NAVIGATEUR (carte de
    // chaleur d'ombrage, diagramme de pertes, rendu 3D). `genre` : un des
    // trois admis (`ombrage`, `sankey`, `plan3d`), `fichier` : une data-URL
    // base64 (`documents/deposerImage.js` la produit depuis un Blob) — le
    // serveur refuse tout le reste en NOMMANT le champ fautif (jamais une
    // confiance au type déclaré par le navigateur).
    deposerImageDocument: (id, { genre, fichier }) =>
      api.post(`${pivot(id)}image-document/`, { genre, fichier }),

    // CALX320 — l'inventaire des NEUF documents du lot 6 (CALX291/321/322),
    // contrat `contract_samples/calepinage_documents.json`, DISTINCT de
    // `sorties()` ci-dessus : chaque pièce porte `manque[]` (le champ NOMMÉ
    // qui manque, jamais une phrase générique) et `versions[]` (l'historique
    // retrouvable, la plus récente d'abord). C'est CET inventaire que
    // `documents/PanneauDocuments.jsx` consomme désormais — lecture PURE,
    // même discipline que `sorties()`.
    documents: (id) => api.get(`${pivot(id)}documents/`),

    // CALX320 — le téléchargement GÉNÉRIQUE d'UN document de l'inventaire
    // `documents()` ci-dessus : MÊME geste que `telechargerSortie`
    // (`endpoint` vient TOUJOURS de l'entrée servie, jamais reconstruit),
    // nommé à part — un document du lot 6 n'est pas une sortie technique.
    telechargerDocument: (endpoint, params) =>
      api.get(endpoint, { responseType: 'blob', params }),

    ...projet,

    // ACAL82 — persiste le système de fixation CHOISI (ACAL81, contrat
    // `calepinage_fixation_bom.json` › `fixation_post`) : `{systeme_id|null}`
    // → `{systeme, systeme_source}` ; `null` retire le choix.
    appliquerFixation: (id, corps) => api.post(`${pivot(id)}fixation/`, corps), // ACAL

    // ACAL238 — joindre (multipart `{dossier, piece, fichier}`) ou retirer
    // (`{dossier, piece, retirer: true}`) une pièce d'un dossier réglementaire
    // (contrat `dossiers_reglementaires.json` › `joindre_piece`).
    joindrePiece: (id, corps) => api.post(`${pivot(id)}joindre-piece/`, corps), // ACAL

    // ACAL149 — la RELECTURE de l'entrée électrique enregistrée + le matériel
    // résolu et les candidats (contrat `calepinage_entree_electrique.json`).
    // Le POST reste `enregistrerEntreeElectrique` (au-dessus).
    entreeElectrique: (id) => api.get(`${pivot(id)}entree-electrique/`),

    // ACAL161 — l'ÉDITION du schéma unifilaire (libellés et repères par clef de bloc ;
    // `null` efface une rubrique). Le serveur fusionne clé par clé (ACAL160) et renvoie le
    // MÊME document que le GET `schemaUnifilaire`, édition appliquée.
    enregistrerEditionSld: (id, edition) => api.post(`${pivot(id)}schema-unifilaire/`, edition),

    // ACAL222 — la REMISE explicite d'un document (`{code, langue}`) : 201
    // nouvelle version, 200 `deja_remise` (même empreinte des entrées), 400
    // sous le champ nommé (contrat `calepinage_documents.json` › `remise`).
    remettreDocument: (id, corps) => api.post(`${pivot(id)}remettre-document/`, corps), // ACAL
    // ACAL223 — une pièce de méthode POST (dossier de fin de chantier) : l'`endpoint` vient
    // TOUJOURS de l'entrée servie ; `params` (ex. `{langue}`) voyagent en query.
    declencherDocument: (endpoint, params) => api.post(endpoint, null, { params }), // ACAL
    // ACAL223 — l'aperçu HTML EXACT d'une pièce (`apercu-document?code=&langue=`), texte brut.
    apercuDocument: (id, code, params) => api.get(`${pivot(id)}apercu-document/`, // ACAL
      { responseType: 'text', params: { code, ...params } }),
    // ACAL23 — contrat calepinage_layout_section.json (ACAL1/ACAL22). L'écriture COMPLÈTE
    // porte l'empreinte « document » lue au boot (ou rendue par la dernière écriture) dans
    // l'en-tête If-Match : un document modifié ailleurs répond 409 `document_modifie`, rien
    // n'est écrasé. Sans empreinte connue : l'ETag vide (ACAL316 — l'en-tête est obligatoire).
    enregistrerLayoutCalepinageConditionnel: (id, corps, empreinte) => api.post( // ACAL
      `${pivot(id)}layout/`, corps, jetonIfMatch(empreinte)),
    // ACAL23 — l'écriture d'UNE section (`{cle, valeur | zone_id + champs, base_empreinte}`).
    enregistrerSectionLayout: (id, corps) => api.post(`${pivot(id)}layout/section/`, corps), // ACAL
    // ACAL192 (D-ACAL-13, contrat calepinage_design_context.json › geometrie.derive) — le GPS
    // du lead a été corrigé après le tracé : le SERVEUR translate toute la géométrie (nouvelle
    // version) ou acquitte la dérive (`repereAcquitte`). Aucune translation côté navigateur.
    recentrerSurLead: (id) => api.post(`${pivot(id)}recentrer-sur-lead/`, {}), // ACAL
    garderRepere: (id) => api.post(`${pivot(id)}garder-repere/`, {}), // ACAL
    // ACAL207 (D-ACAL-28, contrat calepinage_releve.json › appliquer_cote) — `{zone_id,
    // cote_index, longueur_m}` → `{roof_layout, version}` : le SERVEUR recale le côté choisi
    // par homothétie (400 nommé : cote à confirmer, pan croisé ; 409 : verrou).
    appliquerCoteReleve: (id, releveId, corps) => api.post( // ACAL
      `${pivot(id)}releve/${releveId}/appliquer-cote/`, corps),
    // ACAL66 — la DÉCISION sur une suggestion de pente IGN, par le serveur (ACAL65) :
    // `{operation: 'proposer' | 'accepter' | 'refuser', zone_id?, base_empreinte}`. La
    // suggestion est persistée dans le pan (« pente du terrain »), jamais recopiée dans
    // la pente du pan (D-ACAL-19). 409 `document_modifie` si le jeton est périmé.
    decisionSuggestionPente: (id, corps) => api.post(`${pivot(id)}suggestions-pente/`, corps), // ACAL
    // ACAL73 — le téléversement d'une IMAGE de plan (PNG/JPEG) comme fond du document
    // (ACAL72) : `corps` est un FormData (`fichier`, `base_empreinte`) — axios pose sa
    // frontière multipart. Le serveur écrit `underlay` par section et rend `{underlay,
    // empreinte_document}` ; 409 `document_modifie` si le jeton est périmé.
    envoyerFondPlan: (id, corps) => api.post(`${pivot(id)}fond-plan/`, corps), // ACAL
    // ACAL109 — renommer (PATCH `{nom}`) et supprimer une variante ; le refus
    // serveur (variante RETENUE) est affiché tel quel par l'écran.
    modifierVariante: (id, varianteId, corps) => api.patch(`${pivot(id)}variantes/${varianteId}/`, corps), // ACAL
    supprimerVariante: (id, varianteId) => api.delete(`${pivot(id)}variantes/${varianteId}/`), // ACAL
    // ACAL113 (D-ACAL-17, contrat calepinage_simulation.json › corps_variante) — simuler UNE
    // variante : le résultat est écrit SUR LA VARIANTE (202 + job, suivi par useSuiviJob).
    simulerVariante: (id, varianteId) => api.post(`${pivot(id)}simuler/`, { variante_id: varianteId, forcer: true }), // ACAL
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

    // ACAL133 — « Tout recalculer » après un changement de réglage société :
    // relance en tâche de fond chaque simulation périmée de la société
    // (`views/parametres.py::RecalculerSimulationsView`, ACAL134). Rend 202
    // `{soumis, jobs: [{calepinage, job_id}], reste}` — au plus un plafond de
    // travaux par appel, `reste` compte ceux à relancer par un nouvel appel.
    recalculerSimulations: () => api.post('/calepinage/parametres/recalculer-simulations/'),

    // CALX29 — suggestion de pente par LiDAR IGN (France seule,
    // `services/lidar_ign.py`). GET est une LECTURE LOCALE : elle dit si le
    // service est offert à la société de l'appelant SANS émettre de requête
    // sortante, même quand il l'est — c'est elle qui commande l'affichage du
    // bouton. POST envoie le document de conception et reçoit une suggestion
    // par pan, jamais persistée côté serveur : c'est l'écran qui accepte ou
    // jette, puis enregistre via `enregistrerLayoutCalepinage` (CAL18).
    suggestionPenteDisponible: () => api.get('/calepinage/parametres/suggestion-pente/'),
    suggererPentesIGN: (roofLayout) =>
      api.post('/calepinage/parametres/suggestion-pente/', { roof_layout: roofLayout }),

    // CALX30 — les PROFILS TYPES de consommation de la société (CAL149,
    // `views/consommation.py`, servi sous le préfixe `parametres` parce
    // qu'aucun identifiant de calepinage n'y entre). Le GET sert les profils
    // SAISIS puis les replis ÉTIQUETÉS « hypothèse interne » ; le PUT
    // REMPLACE les profils saisis — un repli n'en est pas un, il n'est donc
    // jamais renvoyé comme une saisie.
    profilsTypes: () => api.get('/calepinage/parametres/profils-types/'),
    enregistrerProfilsTypes: (profils) =>
      api.put('/calepinage/parametres/profils-types/', { profils }),
  },
}

export default calepinageApi
// ACAL3 — contrat calepinage_publication.json (M0)
// ACAL9 — contrat calepinage_entree_electrique.json (M0)
// ACAL9 — contrat calepinage_publication_electrique.json (M0)
// ACAL11 — contrat calepinage_liste.json (M0)
// ACAL12 — contrat calepinage_creation_conflit.json (M0)
// ACAL13 — contrat calepinage_photos.json (M0)
// ACAL15 — contrat gabarits_dossier_reglementaire.json (M0)
// ACAL21 — contrat calepinage_consommation_proposee.json (M0)
