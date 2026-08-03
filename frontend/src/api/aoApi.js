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
  plansSources: crud('plans-source'),
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

  /* `calepinages` (au pluriel) — ATELIER NON RECÂBLÉ, 03/08/2026.
     L'atelier (`useCalepinage`, `HistoriqueVersions`, `SensibilitesPanel`)
     est écrit contre un document `calepinage` PERSISTÉ, avec un identifiant,
     un historique de versions et un `patch_entree` rejoué : rien de tout cela
     n'existe côté serveur. Ce n'est donc PAS un renommage — c'est soit un
     modèle à construire, soit un recâblage de l'atelier sur le calcul sans
     état ci-dessus (`toitureId` au lieu de `calepinageId`). Les deux
     dépassent une correction de chemin, et deviner l'un des deux ferait
     exactement le mal qu'on répare.
     En attendant, chaque appel échoue AVEC SON MOTIF, sans requête réseau. */
  calepinages: {
    get: nonConstruit('/ao/calepinages/<id>/',
      "aucun modèle Calepinage n'existe ; ce qui est persisté est une "
      + 'VarianteCalepinage (/ao/variantes-calepinage/)'),
    list: nonConstruit('/ao/calepinages/?versions_de=<id>',
      "l'historique de versions d'un calepinage n'est pas modélisé"),
    update: nonConstruit('/ao/calepinages/<id>/',
      "la restauration d'une version n'existe pas côté serveur"),
    calculer: nonConstruit('/ao/calepinages/<id>/calculer/',
      'le calcul est SANS ÉTAT : utiliser aoApi.calepinage.calculer('
      + '{toiture, params})'),
    suggestions: nonConstruit('/ao/calepinages/<id>/suggestions/',
      'aucune route ne publie les recommandations du moteur'),
    sensibilites: nonConstruit('/ao/calepinages/<id>/sensibilites/',
      'les sensibilités se calculent sur une VARIANTE : utiliser '
      + 'aoApi.calepinage.variantes.sensibilites(varianteId) — la réponse '
      + 'porte reference_modules/plancher_modules/engagement_modules/'
      + 'verdict/sensibilites, pas lignes/plancher'),
    alleeGratuite: nonConstruit('/ao/calepinages/<id>/allee-gratuite/',
      "l'allée gratuite n'est publiée par aucune route"),
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

  // ── Bordereau / équipements / exigences CPS ──
  // RÉPARATION 03/08/2026 — le routeur publie `series-questions` ; le front
  // appelait `series-qr` (404), et filtrait sur `affaire` alors que le
  // ViewSet ne connaît que `appel_offre`.
  seriesQR: crud('series-questions'),
  /* `equipements` — ENDPOINT À CONSTRUIRE (03/08/2026), pas un renommage.
     Le modèle `EquipementAO` existe (AOF118 : snapshot figé, string-FK vers
     `stock.Produit`) et la mécanique de bascule est écrite dans
     `apps/ao/fabrique/bascule_rapport.py` + `fabrique/annexes.py`. Mais il
     n'y a NI sérialiseur, NI ViewSet, NI route, NI le `services.
     basculer_equipement` que le module de rapport cite lui-même comme
     manquant. Aucune ressource du routeur ne sert les équipements sous un
     autre nom — l'écran ne peut donc pas être « recâblé », il attend un
     endpoint. Le construire à la va-vite serait pire : la bascule doit être
     ATOMIQUE (référence + grandeurs dérivées + fiche annexée ajoutée +
     ancienne retirée, en une transaction), c'est une tâche entière. */
  equipements: {
    list: nonConstruit('/ao/equipements/',
      "le modèle EquipementAO existe mais n'a ni sérialiseur ni ViewSet ni "
      + 'route'),
    get: nonConstruit('/ao/equipements/<id>/', "aucune route n'expose "
      + 'EquipementAO'),
    create: nonConstruit('/ao/equipements/', "aucune route n'expose "
      + 'EquipementAO'),
    update: nonConstruit('/ao/equipements/<id>/', "aucune route n'expose "
      + 'EquipementAO'),
    remove: nonConstruit('/ao/equipements/<id>/', "aucune route n'expose "
      + 'EquipementAO'),
    bascule: nonConstruit('/ao/equipements/<id>/bascule/',
      'services.basculer_equipement (AOF141) n’est pas écrit — seul le '
      + 'RAPPORT de bascule (fabrique/bascule_rapport.py) existe'),
  },
  exigencesCps: crud('exigences-cps'),

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
    // ENDPOINT À CONSTRUIRE — pas un renommage. Vérifié le 03/08/2026 : AUCUN
    // producteur de pièce n'existe côté serveur. Les rendus
    // (`fabrique/rendus/*`) prennent tous un CONTEXTE déjà assemblé, et le
    // monteur qui assemblerait ce contexte depuis un `DossierAO`
    // (`services.producteurs_de_pack`) n'est pas écrit — `apps/ao/tasks.py` le
    // dit lui-même dans sa docstring. Deviner une URL ici ne ferait
    // qu'échanger un 404 anonyme contre un autre.
    genererPiece: nonConstruit('/ao/dossiers-ao/<id>/generer-piece/',
      'aucun producteur de pièce : les rendus attendent un contexte que '
      + 'personne n’assemble (services.producteurs_de_pack manque)'),
    // ENDPOINT À CONSTRUIRE — et c'est le cas où ouvrir la porte serait PIRE
    // que la laisser fermée. La fabrique sait ÉCRIRE le ZIP
    // (`fabrique/pack_zip.ecrire_pack_zip`, testé, refus motivé si un contrôle
    // est rouge) et `tasks.produire_pack` sait l'orchestrer de façon
    // idempotente — mais RIEN ne leur fournit les pièces. Une @action `zip`
    // rendrait donc un job qui se termine « terminé » avec zéro pièce, et
    // `useGenerationJob` appellerait `onSucces` : « pack prêt » sur un pack
    // vide. Un faux succès est pire qu'un 404 — il se dépose.
    zip: nonConstruit('/ao/dossiers-ao/<id>/zip/',
      'le ZIP et son job existent mais aucun monteur ne leur passe les '
      + 'pièces (services.producteurs_de_pack manque)'),
    // ENDPOINT À CONSTRUIRE, par conséquence directe de `zip` ci-dessus :
    // aucun job de pack ne peut être lancé, donc il n'y en a aucun à suivre.
    // Le patron de suivi est déjà écrit et servira tel quel le jour où le
    // monteur existe : `ResultatCalepinageView` (job scopé société, introuvable
    // — 404, jamais « interdit » — pour une autre société).
    statutJob: nonConstruit('/ao/dossiers-ao/<id>/statut-de-job/<jobId>/',
      'aucun job de pack ne peut être lancé tant que `zip` ne construit rien'),
  },
  pieces: crud('pieces-soumission'),

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
}

export default aoApi
