import api from './axios'
import { makeResourceFactory } from './resource'
import { endpointNonConstruit } from './endpointNonConstruit'

/* ============================================================================
   AOF11 — Client API du module Appels d'offres (`apps/ao`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), jamais un `axios.get`
   direct dans `features/ao/`.

   **LA VÉRITÉ EST `backend/django_core/apps/ao/urls.py`, PAS CE FICHIER.**
   Ce fichier a longtemps prétendu « publier le contrat que le backend
   enregistre ensuite » : construites en parallèle, les deux lanes ont divergé
   et neuf chemins appelés ici n'existaient sous AUCUNE route (404 constatée
   en production le 03/08/2026 sur la Bibliothèque). Chaque chemin ci-dessous
   est désormais RELU dans le routeur serveur ; quand un endpoint manque
   vraiment, il est NOMMÉ en commentaire plutôt que deviné.

   `affaires`/`pieces`/`dossiers` pointent sur les 3 ViewSets LEGACY (ODX11 :
   `appels-offres`/`pieces-soumission`/`dossiers-soumission`) — le terme
   métier « affaire » est une lecture FRONT, la route serveur ne change pas.

   **RÈGLE #4 / en-tête du groupe : L'ÉCONOMIE EST RÉSERVÉE AU DIRECTEUR.**
   `aoRentabiliteApi` est un export **SÉPARÉ**, jamais mélangé aux ressources
   ci-dessus — un import de `aoApi` seul n'expose AUCUN appel réseau vers
   l'endpoint de rentabilité (gardé par `aoApi.test.mjs`).
   ========================================================================== */

// ARC44 — Fabrique CRUD standard sur `/ao/<ressource>/`.
const crud = makeResourceFactory(api, '/ao')

/* ── AOF173 — La bibliothèque est une FAÇADE, pas une ressource serveur ────
   Les quatre catégories de l'écran Bibliothèque correspondent à quatre
   ressources RÉELLES du routeur AO. `list({ type })` choisit la bonne ; le
   `type` n'est donc jamais envoyé au serveur (aucune de ces ressources ne
   connaît ce filtre — l'envoyer produirait un filtre ignoré, c.-à-d. une
   liste fausse qui a l'air juste). */
export const BIBLIOTHEQUE_RESSOURCES = {
  kit: 'kits-calepinage',
  preset: 'presets-calepinage',
  gabarit_pack: 'modeles-pack',
  texte_normalise: 'sections-memoire',
}

const bibliothequeParType = Object.fromEntries(
  Object.entries(BIBLIOTHEQUE_RESSOURCES).map(([type, chemin]) => [type, crud(chemin)]),
)

const ressourceBibliotheque = (type) => {
  const ressource = bibliothequeParType[type]
  if (!ressource) throw new Error(`Catégorie de bibliothèque inconnue : ${type}`)
  return ressource
}

const bibliothequeFacade = {
  list: ({ type, ...params } = {}) => ressourceBibliotheque(type).list(params),
  get: (type, id) => ressourceBibliotheque(type).get(id),
  update: (type, id, data) => ressourceBibliotheque(type).update(id, data),
}

/* ── Endpoints que le backend N'A PAS construits ───────────────────────────
   Ne JAMAIS remplacer ces appels par un chemin deviné : une URL inventée
   produit un 404 anonyme (voir `api/endpointNonConstruit.js`). */
const nonConstruit = endpointNonConstruit

const aoApi = {
  // ── Affaire (AppelOffre — ViewSet legacy ODX11 `appels-offres`) ──
  affaires: {
    ...crud('appels-offres'),
    // AOF170 — action de ligne « dupliquer » (AOF130 : gabarit d'affaire
    // réutilisable, aucune variante/économie copiée). L'archivage LOGIQUE
    // (jamais une suppression dure) réutilise le `update()` générique
    // ci-dessus (`update(id, { archive: true })`) — pas d'action dédiée.
    dupliquer: (id) => api.post(`/ao/appels-offres/${id}/dupliquer/`),
  },

  // ── Toiture / relevé (portes 1-2-3 : plan fourni, from-scratch, carte) ──
  batiments: crud('batiments'),
  toitures: crud('toitures'),
  // RÉPARATION 03/08/2026 — le routeur enregistre `plans-source` et
  // `chaines-cotes` (AU SINGULIER pour le premier) ; le front appelait
  // `plans-sources` et `chaines`, deux 404 silencieuses.
  // PACT76 — `upload` publie l'action MULTIPART réelle
  // (`PlanSourceViewSet.upload`) : le fichier part en `records.Attachment`,
  // JAMAIS un `FileField` local ; le serveur recalcule l'échelle à CHAQUE
  // écriture de calibration (`create`/`update` appellent `_recalibrer`).
  plansSources: {
    ...crud('plans-source'),
    upload: (id, fichier) => {
      const fd = new FormData()
      fd.append('fichier', fichier)
      return api.post(`/ao/plans-source/${id}/upload/`, fd)
    },
  },
  releves: crud('releves'),
  obstacles: crud('obstacles'),
  chaines: crud('chaines-cotes'),
  //
  // `zones:` A ÉTÉ RETIRÉ — ENDPOINT À CONSTRUIRE, pas un renommage.
  // L'outil de saisie des zones (AOF89 : interdite / réservée / préférée)
  // existe côté écran, mais AUCUN modèle ni route ne les persiste, et
  // `calepinage_io.document_entree()` envoie `'zones': []` en dur au moteur.
  // Publier ici un `crud('zones')` ferait croire à un stockage qui n'existe
  // pas ; le jour où le modèle est créé, la ressource revient ici.

  /* ── Calepinage (moteur `core/calepinage/`) ─────────────────────────────
     LES VRAIES ROUTES, telles que `apps/ao/calepinage_urls.py` les publie.
     Le calepinage n'est PAS une ressource : il n'existe aucun modèle
     `Calepinage`, donc aucun `/ao/calepinages/<id>/`. Le calcul est SANS
     ÉTAT (on lui donne une toiture + des paramètres, ou un document
     d'entrée), et ce qui est PERSISTÉ est une `VarianteCalepinage`. */
  calepinage: {
    // Calcul synchrone borné. Corps : `{toiture, params}` ou `{entree}`.
    // 202 = le travail dépasse le budget synchrone → passer par `lancer`.
    calculer: (corps) => api.post('/ao/calepinage/calculer/', corps),
    // Calcul en tâche de fond (`core.jobs`) → renvoie l'id du job.
    lancer: (corps) => api.post('/ao/calepinage/lancer/', corps),
    // Suivi + résultat du job de fond.
    resultat: (jobId) => api.get(`/ao/calepinage/resultat/${jobId}/`),
    // Actions AOF62, portées par la VARIANTE (jamais par un « calepinage »).
    variantes: {
      retenir: (id) => api.post(`/ao/calepinage/variantes/${id}/retenir/`),
      sensibilites: (id) => api.post(`/ao/calepinage/variantes/${id}/sensibilites/`),
      marches: (id) => api.get(`/ao/calepinage/variantes/${id}/marches/`),
      comparer: (ids) => api.get('/ao/calepinage/variantes/comparer/',
        { params: { ids: [].concat(ids).join(',') } }),
    },
  },

  /* `calepinages` (au pluriel) — LA FICTION, ce qu'il en RESTE. 03/08/2026.
     ------------------------------------------------------------------------
     L'ATELIER EST RECÂBLÉ (même jour) : `useCalepinage` + `CalepinageStudio`
     n'appellent plus une seule de ces entrées — ils passent par
     `aoApi.calepinage` ci-dessus, c'est-à-dire par les routes que
     `apps/ao/calepinage_urls.py` publie réellement. Le studio est piloté par
     un `toitureId`, jamais par un `calepinageId` : le calcul est SANS ÉTAT,
     il n'y a rien à charger par identifiant.

     Ce bloc n'est donc plus une impasse à l'usage — il ne subsiste que pour
     l'écran encore écrit contre le document persisté imaginaire :
     `variantes/HistoriqueVersions.jsx` (`list`, `update`). RÉPARATION
     07/08/2026 (PACT172) — `variantes/SensibilitesPanel.jsx` appelle
     désormais le VRAI endpoint ci-dessous (`aoApi.calepinage.variantes.
     sensibilites`) ; `sensibilites` n'a donc plus aucun appelant. Chaque
     entrée reste un 501 MOTIVÉ, sans requête réseau : un 404 anonyme est
     précisément ce qu'on répare, et une URL devinée le recréerait. */
  calepinages: {
    // Plus AUCUN appelant depuis le 03/08/2026 (l'atelier est recâblé).
    get: nonConstruit('/ao/calepinages/<id>/',
      "aucun modèle Calepinage n'existe ; un calepinage se CALCULE "
      + '(aoApi.calepinage.calculer({toiture, params})) et ce qui est '
      + 'persisté est une VarianteCalepinage (/ao/variantes-calepinage/)'),
    // Appelé par variantes/HistoriqueVersions.jsx — À CONSTRUIRE.
    list: nonConstruit('/ao/calepinages/?versions_de=<id>',
      "l'historique de versions d'un calepinage n'est pas modélisé"),
    // Appelé par variantes/HistoriqueVersions.jsx — À CONSTRUIRE.
    update: nonConstruit('/ao/calepinages/<id>/',
      "la restauration d'une version n'existe pas côté serveur"),
    // Plus AUCUN appelant depuis le 03/08/2026.
    calculer: nonConstruit('/ao/calepinages/<id>/calculer/',
      'le calcul est SANS ÉTAT : utiliser aoApi.calepinage.calculer('
      + '{toiture, params}), puis aoApi.calepinage.lancer/resultat au-delà '
      + 'du budget synchrone (202)'),
    // À CONSTRUIRE : `core/calepinage/recommandations.py` existe, mais AUCUNE
    // route ne le publie — l'atelier n'affiche donc aucune suggestion.
    suggestions: nonConstruit('/ao/calepinages/<id>/suggestions/',
      'aucune route ne publie les recommandations du moteur'),
    // Plus AUCUN appelant depuis le 07/08/2026 (PACT172) — SensibilitesPanel.jsx
    // appelle désormais aoApi.calepinage.variantes.sensibilites(varianteId).
    sensibilites: nonConstruit('/ao/calepinages/<id>/sensibilites/',
      'les sensibilités se calculent sur une VARIANTE : utiliser '
      + 'aoApi.calepinage.variantes.sensibilites(varianteId) — la réponse '
      + 'porte reference_modules/plancher_modules/engagement_modules/'
      + 'verdict/sensibilites, pas lignes/plancher'),
    alleeGratuite: nonConstruit('/ao/calepinages/<id>/allee-gratuite/',
      "l'allée gratuite n'est publiée par aucune route"),
    // Plus AUCUN appelant : le suivi de job de l'atelier passe par
    // aoApi.calepinage.resultat(jobId) (route RÉELLE).
    statutJob: nonConstruit('/ao/calepinages/<id>/statut-de-job/<jobId>/',
      'le suivi de job est aoApi.calepinage.resultat(jobId)'),
  },
  // RÉPARATION 03/08/2026 — le CRUD des variantes est routé sous
  // `variantes-calepinage` (AOF28) ; `variantes` n'a jamais existé. Et
  // l'échelle de décomposition n'est pas une action de ce ViewSet : c'est
  // `marches` sur le viewset d'actions d'AOF62
  // (`/ao/calepinage/variantes/<id>/marches/`), qui rejoue les deltas SIGNÉS
  // à partir des comptes persistés.
  variantes: {
    ...crud('variantes-calepinage'),
    decomposition: (id) => api.get(`/ao/calepinage/variantes/${id}/marches/`),
    // Actions RÉELLES du CRUD (AOF28) : `publier` refuse tant que la preuve
    // ne tient pas, `retenir` désigne l'unique variante retenue.
    publier: (id) => api.post(`/ao/variantes-calepinage/${id}/publier/`),
    retenir: (id) => api.post(`/ao/variantes-calepinage/${id}/retenir/`),
  },

  /* ── PACT74 — Pièces du dossier de CONSULTATION reçu de l'acheteur (AOF21) ─
     `pieces-consultation`, enregistrée depuis toujours : CPS, règlement,
     plans d'architecte, cadre de bordereau vierge, ADDITIFS — jamais exposée.
     `additif` enregistre un erratum ET marque « à revérifier » les exigences
     CPS qui en dérivent, en une seule action serveur. */
  piecesConsultation: {
    ...crud('pieces-consultation'),
    additif: (id, corps) => api.post(`/ao/pieces-consultation/${id}/additif/`, corps),
  },

  // ── Bordereau / équipements / exigences CPS ──
  // RÉPARATION 03/08/2026 — le routeur publie `series-questions` ; le front
  // appelait `series-qr` (404), et filtrait sur `affaire` alors que le
  // ViewSet ne connaît que `appel_offre`.
  seriesQR: crud('series-questions'),
  /* PACT170 — les QUESTIONS elles-mêmes. Le routeur les publie depuis
     toujours (`router.register(r'questions', QuestionAOViewSet)`,
     `apps/ao/urls.py`) ; seul le client manquait, si bien que l'écran
     « Questions terrain » ne pouvait qu'AFFICHER les questions imbriquées
     dans leur série, jamais en créer ni en corriger une. Création : `serie`,
     `texte`, et AU MOINS un impact chiffré (`impact_min_modules` et/ou
     `impact_max_modules`) — le sérialiseur refuse le reste, et c'est la règle
     produit : on ne pose une question que si sa réponse change le compte. */
  questions: crud('questions'),
  /* ── `equipements` — CONSTRUIT le 03/08/2026 (AOF118 + AOF141) ───────────
     Le trou est comblé : `EquipementAO` a désormais son sérialiseur, son
     ViewSet `equipements` et l'action atomique `bascule`
     (`services.basculer_equipement`, posée par la lane backend jumelle du
     même commit). Le client repasse donc par la factory CRUD partagée.

     **Le filtre de liste est `?appel_offre=<id>`** — le nom du CHAMP DU
     MODÈLE (`EquipementAO.appel_offre`) et la convention de toutes les
     ressources filles du routeur AO (`ToitureAOViewSet`, `ReleveAOViewSet`…
     lisent `query_params['appel_offre']`). L'écran envoyait `?projet=` :
     personne ne l'aurait vu échouer, un filtre inconnu est simplement IGNORÉ
     par le ViewSet — c'est-à-dire la liste de TOUTE la société avec l'air
     d'être filtrée sur un dossier. Un 404 se voit ; un filtre ignoré, non.

     `bascule` est une ACTION, jamais un PATCH : elle doit être ATOMIQUE
     (référence + grandeurs dérivées + lignes de bordereau + fiche annexée
     ajoutée ET ancienne retirée, en une transaction). Sa réponse porte le
     rapport de `fabrique/bascule_rapport.py`. */
  equipements: {
    ...crud('equipements'),
    bascule: (id, corps) => api.post(`/ao/equipements/${id}/bascule/`, corps),
  },
  exigencesCps: crud('exigences-cps'),

  /* ── PACT72 — Pièces du dossier de dépôt, GÉNÉRÉES et FOURNIES ────────────
     `pieces-dossier-ao` (AOF115), enregistrée depuis toujours. `DossierPage`
     lit déjà les pièces GÉNÉRÉES via `dossiers.get(id).pieces` (imbriquées) ;
     aucun écran n'offrait de marquer une pièce FOURNIE « présente » ni d'y
     attacher son fichier — pas même un wrapper client. */
  piecesDossierAo: crud('pieces-dossier-ao'),

  // ── Dossier de DÉPÔT (AOF115 — `dossiers-ao`, kit `core/documents.py`) ──
  //
  // RÉPARATION 03/08/2026 — `dossiers` visait `dossiers-soumission`, qui est
  // une AUTRE ressource : `DossierSoumission` (FG225) est la checklist
  // administrative HISTORIQUE, sans statut, sans empreinte, et ses
  // `PieceSoumission` n'ont PAS de `visibilite`. Or les écrans du dossier
  // lisent `piece.visibilite` (DossierPage.utils `piecesVisibles`), l'état de
  // contrôle et les pièces hors contrôle : tout cela n'existe que sur
  // `DossierAO`/`PieceDossierAO`. Les deux tables ont des identifiants
  // DISTINCTS — `get(7)` sur l'une et une action sur l'autre auraient désigné
  // deux dossiers différents, ce qui est pire qu'un 404 : silencieux.
  dossiers: {
    ...crud('dossiers-ao'),
    controlesAvantDepot: (id) =>
      api.get(`/ao/dossiers-ao/${id}/controles-avant-depot/`),
    // PACT71 — complétude DÉRIVÉE (`DossierAO.raisons_de_non_depot`, en
    // français) : pièces obligatoires manquantes, checklist partenaire encore
    // ouverte, pièces administratives expirées à la date de remise des plis.
    completude: (id) => api.get(`/ao/dossiers-ao/${id}/completude/`),
    // AOF136 — sème les points de checklist partenaire manquants (idempotent :
    // un second appel ne recrée rien).
    initialiserChecklist: (id) =>
      api.post(`/ao/dossiers-ao/${id}/initialiser-checklist/`),
    // PACT25 — LES TROIS CHEMINS SONT OUVERTS. Ils étaient délibérément
    // fermés tant que `services.producteurs_de_pack` n'existait pas : la
    // fabrique savait écrire le ZIP (`fabrique/pack_zip.ecrire_pack_zip`) et
    // `tasks.produire_pack` savait l'orchestrer, mais RIEN ne leur fournissait
    // les pièces — un job se serait terminé « terminé » avec zéro pièce et
    // `useGenerationJob` aurait appelé `onSucces` : « pack prêt » sur une
    // archive vide. Le monteur existe désormais, et un pack VIDE ou INCOMPLET
    // met le job en ÉCHEC au lieu de finir vert (le faux succès est mort).
    genererPiece: (id) => api.post(`/ao/dossiers-ao/${id}/generer-piece/`),
    // Le ZIP est un FICHIER : `responseType: 'blob'`. Refus 400 motivé quand
    // un contrôle de cohérence est rouge ou qu'aucune pièce n'est déposable.
    zip: (id) => api.get(`/ao/dossiers-ao/${id}/zip/`, { responseType: 'blob' }),
    // Suivi scopé société : un job d'une autre société est INTROUVABLE (404),
    // jamais « interdit » — un 403 confirmerait son existence.
    statutJob: (id, jobId) =>
      api.get(`/ao/dossiers-ao/${id}/statut-de-job/`, { params: { job: jobId } }),
  },
  pieces: crud('pieces-soumission'),

  /* ── PACT71 — Checklist partenaire du dossier de dépôt (AOF136) ───────────
     `checklist-partenaire`, enregistrée depuis toujours côté serveur : un
     point obligatoire encore ouvert BLOQUE la transition « prêt à déposer »
     (`DossierAO.raisons_de_non_depot`), mais aucun écran ne l'affichait — la
     porte de blocage était invisible, contournée par l'API en croyant bien
     faire. `pointer` trace TOUJOURS le responsable côté serveur. */
  checklistPartenaire: {
    ...crud('checklist-partenaire'),
    pointer: (id, corps) => api.post(`/ao/checklist-partenaire/${id}/pointer/`, corps),
  },

  /* ── PACT73 — Bibliothèque des pièces administratives (AOF137) ────────────
     `pieces-administratives`, SCOPÉE SOCIÉTÉ (jamais une affaire) : une pièce
     datée (attestation fiscale, CNSS, RC…) s'enregistre UNE fois et se
     RATTACHE à plusieurs AO sans dupliquer un octet. `rattacher` ajoute la
     pièce à un dossier ; `aRenouveler` liste celles qui entrent dans leur
     fenêtre de rappel. */
  piecesAdministratives: {
    ...crud('pieces-administratives'),
    rattacher: (id, dossierId) =>
      api.post(`/ao/pieces-administratives/${id}/rattacher/`, { dossier: dossierId }),
    aRenouveler: () => api.get('/ao/pieces-administratives/a-renouveler/'),
  },

  // ── Bibliothèque : kits, presets, gabarits, textes normalisés ──
  //
  // RÉPARATION 03/08/2026 — `crud('bibliotheque')` appelait
  // `/ao/bibliotheque/`, une route que le backend n'a JAMAIS enregistrée :
  // 404 constatée en production. Les quatre catégories de l'écran sont
  // QUATRE ressources réelles (`apps/ao/urls.py`), et la bibliothèque n'est
  // qu'une façade de lecture par-dessus. Aucune n'est agrégée côté serveur :
  // un agrégat aurait imposé un identifiant composite inventé, alors que
  // « modifier un texte normalisé » est très exactement un PATCH sur
  // `sections-memoire/<id>/`.
  bibliotheque: {
    ...bibliothequeFacade,
    // AOF173 — les dossiers qui reprennent ce texte, à afficher AVANT toute
    // validation. La liste est calculée côté serveur avec la MÊME règle
    // d'inclusion que le rendu du mémoire (jamais une estimation d'écran).
    dossiersImpactes: (id) => api.get(`/ao/sections-memoire/${id}/dossiers-impactes/`),
  },

  // AOF172/AOF166 — appel agrégé UNIQUE du tableau de bord (nom d'endpoint +
  // selector repris nominativement de NTMAR27 par AOF166, pour éviter deux
  // tableaux de bord AO concurrents) : AO en cours, taux de réussite, cautions
  // immobilisées, marchés en exécution, capacité vs engagement, échéances dues.
  tableauMarches: () => api.get('/ao/tableau-marches/'),

  /* ── PACT69 — Bordereau des prix (AOF120, `bordereaux-prix`) ──────────────
     Le routeur les enregistre depuis toujours ; `BordereauPage.jsx` (AOF179)
     avait été construit AVANT que ce client ne les publie et montait un motif
     d'indisponibilité permanent (voir `AffaireDetail.jsx`). `totaux`/
     `controles` sont les DEUX `@action` réelles du ViewSet — jamais un total
     recalculé côté front (AOF94). */
  bordereaux: {
    ...crud('bordereaux-prix'),
    totaux: (id) => api.get(`/ao/bordereaux-prix/${id}/totaux/`),
    controles: (id) => api.get(`/ao/bordereaux-prix/${id}/controles/`),
  },
  sectionsBordereau: crud('sections-bordereau'),
  lignesBordereau: crud('lignes-bordereau'),

  /* ── PACT70 — Suivi administratif de l'AO : cautions, échéances, résultat ─
     Trois ressources FG224/FG226/FG227, enregistrées depuis toujours côté
     serveur (`apps/ao/urls.py`), jamais publiées ici : le tableau de bord
     (`tableauMarches` ci-dessus) les AGRÈGE (taux de réussite, cautions
     immobilisées, échéances dues) sans qu'aucun écran ne permette d'en créer
     une seule — ses indicateurs restent donc à zéro. */
  cautionsSoumission: {
    ...crud('cautions-soumission'),
    // AOF16 — chemin d'ÉCRITURE unique du montant DÉFINITIF (dérivé du taux
    // de la clause CPS, jamais saisi à la main). Idempotent côté serveur.
    deriverDefinitive: (corps) =>
      api.post('/ao/cautions-soumission/deriver-definitive/', corps),
  },
  echeancesAo: {
    ...crud('echeances-ao'),
    dues: () => api.get('/ao/echeances-ao/dues/'),
  },
  resultatsAo: {
    ...crud('resultats-ao'),
    stats: () => api.get('/ao/resultats-ao/stats/'),
    // AOF32 — chemin d'ÉCRITURE unique du résultat d'ouverture des plis
    // (upsert idempotent côté serveur, cf. `ResultatAOViewSet.enregistrer`).
    enregistrer: (corps) => api.post('/ao/resultats-ao/enregistrer/', corps),
  },
}

/* ============================================================================
   Export ISOLÉ de la rentabilité — JAMAIS mélangé à `aoApi` ci-dessus.
   ----------------------------------------------------------------------------
   `ao_rentabilite_voir` est une ELEVATED_PERMISSION (en-tête du Groupe AOF) :
   importer `aoApi` seul ne doit exposer AUCUN chemin réseau vers cet
   endpoint.

   LA CIBLE A ÉTÉ TRANCHÉE (le test de garde d'hier disait qu'il faudrait la
   trancher, pas la découvrir en production). AOF161 avait déclaré côté front
   `/ao/:id/rentabilite/` — un chemin que le routeur n'a JAMAIS servi : il n'y
   a aucune ressource montée à la racine `/ao/<id>/`, et l'économie n'est pas
   indexée par l'id d'affaire. La route RÉELLE, enregistrée par
   `apps/ao/urls.py` (AOF157, `router.register(r'economie', EconomieAOViewSet)`),
   est `/ao/economie/<id>/`, indexée par l'économie elle-même et filtrable par
   `?appel_offre=` — c'est ce que ce client appelle désormais.
   ========================================================================== */
export const aoRentabiliteApi = {
  // Depuis un écran d'affaire on ne connaît QUE l'id de l'AO : le serveur
  // expose exactement ce filtre (`EconomieAOViewSet.get_queryset`), donc on
  // le lit au lieu de deviner un id d'économie. Renvoie une LISTE paginée.
  parAffaire: (affaireId) => api.get('/ao/economie/', { params: { appel_offre: affaireId } }),
  get: (economieId) => api.get(`/ao/economie/${economieId}/`),
  update: (economieId, data) => api.patch(`/ao/economie/${economieId}/`, data),
  // PACT75 — l'économie d'une affaire n'existe pas d'office : `EconomieAOViewSet`
  // est un ModelViewSet ordinaire, `create` fonctionne tel quel (les taux de
  // TVA ont un défaut serveur — seul `appel_offre` est requis).
  creer: (affaireId) => api.post('/ao/economie/', { appel_offre: affaireId }),

  /* Le classeur interne se PRODUIT (job de fond) avant de se retirer : il
     n'est jamais rendu dans le temps d'une requête. `produireClasseur` renvoie
     202 + l'id du job, `statutClasseur` suit l'avancement, `download` retire
     les octets — relayés par l'endpoint directeur lui-même, donc jamais un
     lien MinIO direct. */
  produireClasseur: (economieId) => api.post(`/ao/economie/${economieId}/telecharger/`),
  statutClasseur: (economieId, jobId) => api.get(`/ao/economie/${economieId}/telecharger/`,
    { params: { job: jobId } }),
  download: (economieId, jobId) => api.get(`/ao/economie/${economieId}/telecharger/`,
    { params: { job: jobId, fichier: 1 }, responseType: 'blob' }),

  // PACT75 — verrou de l'économie : une cascade de prix déjà propagée ne se
  // modifie plus (`_refuser_si_verrouillee`, appliqué aux lignes ET aux
  // cibles).
  verrouiller: (economieId) => api.post(`/ao/economie/${economieId}/verrouiller/`),
  deverrouiller: (economieId) => api.post(`/ao/economie/${economieId}/deverrouiller/`),

  // PACT75 — postes du coût de revient, scopés à UNE économie (`?economie=`).
  lignesCoutRevient: crud('lignes-cout-revient'),
  // PACT75 — cibles de bénéfice VERSIONNÉES : `create` route vers
  // `services_directeur.nouvelle_cible` côté serveur (incrémente la version,
  // désactive la précédente, trace l'auteur) — jamais un POST qui écraserait
  // une version existante.
  ciblesFinancieres: crud('cibles-financieres'),
}

export default aoApi
