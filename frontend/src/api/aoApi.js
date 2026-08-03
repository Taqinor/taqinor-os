import api from './axios'
import { makeResourceFactory } from './resource'

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

  // ── Calepinage / variantes (moteur `core/calepinage/`, partagé villas) ──
  calepinages: {
    ...crud('calepinages'),
    // AOF11 — actions non-CRUD nommées de l'atelier de calepinage. `patch_entree`
    // est TOUJOURS REJOUÉ côté serveur (jamais estimé côté front, en-tête du
    // groupe « CHOIX MAXIMUM + RECOMMANDATIONS »).
    calculer: (id, params) => api.post(`/ao/calepinages/${id}/calculer/`, params),
    suggestions: (id) => api.get(`/ao/calepinages/${id}/suggestions/`),
    sensibilites: (id, params) => api.get(`/ao/calepinages/${id}/sensibilites/`, { params }),
    alleeGratuite: (id, params) => api.get(`/ao/calepinages/${id}/allee-gratuite/`, { params }),
    statutJob: (id, jobId) => api.get(`/ao/calepinages/${id}/statut-de-job/${jobId}/`),
  },
  variantes: {
    ...crud('variantes'),
    decomposition: (id) => api.get(`/ao/variantes/${id}/decomposition/`),
  },

  // ── Bordereau / équipements / exigences CPS ──
  // RÉPARATION 03/08/2026 — le routeur publie `series-questions` ; le front
  // appelait `series-qr` (404), et filtrait sur `affaire` alors que le
  // ViewSet ne connaît que `appel_offre`.
  seriesQR: crud('series-questions'),
  equipements: {
    ...crud('equipements'),
    // Bascule ATOMIQUE d'équipement (référence + prix + grandeurs dérivées
    // recalculées + fiche annexée AJOUTÉE + ancienne RETIRÉE — en-tête du
    // groupe « QUALITÉ DOCUMENTAIRE NIVEAU FRDISI »).
    bascule: (id, data) => api.post(`/ao/equipements/${id}/bascule/`, data),
  },
  exigencesCps: crud('exigences-cps'),

  // ── Dossier de soumission (pièces — ViewSet legacy ODX11 `pieces-soumission`) ──
  dossiers: {
    ...crud('dossiers-soumission'),
    genererPiece: (id, typePiece) =>
      api.post(`/ao/dossiers-soumission/${id}/generer-piece/`, { type: typePiece }),
    controlesAvantDepot: (id) =>
      api.get(`/ao/dossiers-soumission/${id}/controles-avant-depot/`),
    // Génération asynchrone (job Celery) du pack + ZIP de dépôt.
    zip: (id) => api.post(`/ao/dossiers-soumission/${id}/zip/`),
    statutJob: (id, jobId) => api.get(`/ao/dossiers-soumission/${id}/statut-de-job/${jobId}/`),
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
   endpoint. Miroir du chemin déclaré par AOF161 (`/ao/:id/rentabilite`,
   lane `frontend/ao-directeur`).
   ========================================================================== */
export const aoRentabiliteApi = {
  get: (affaireId) => api.get(`/ao/${affaireId}/rentabilite/`),
  update: (affaireId, data) => api.patch(`/ao/${affaireId}/rentabilite/`, data),
  // Téléchargement du document interne (URL signée — jamais un lien MinIO direct).
  download: (affaireId) => api.get(`/ao/${affaireId}/rentabilite/telecharger/`),
}

export default aoApi
