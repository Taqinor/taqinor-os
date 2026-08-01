import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   AOF11 — Client API du module Appels d'offres (`apps/ao`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), jamais un `axios.get`
   direct dans `features/ao/`. Miroir FIN des ressources REST du domaine
   (calepinage prouvé multi-kits/arc, dossier de dépôt niveau FRDISI) — ce
   fichier PUBLIE le contrat d'API que le backend (lane `backend/ao`, AOF31)
   enregistre ensuite (viewsets/filtres/pagination) : les noms de ressources
   ci-dessous sont la référence, pas un miroir a posteriori.

   `affaires`/`pieces`/`dossiers` pointent sur les 3 ViewSets LEGACY déjà
   enregistrés (ODX11, `apps/ao/urls.py` : `appels-offres`/`pieces-soumission`/
   `dossiers-soumission`) — le terme métier « affaire » est une lecture FRONT,
   la route serveur ne change pas. Les autres ressources (bâtiments, toitures,
   plans sources, relevés, obstacles, zones, chaînes, calepinages, variantes,
   séries Q/R, équipements, exigences CPS, bibliothèque) sont NOUVELLES —
   livrées par la lane `backend/ao` au fil du Groupe AOF.

   **RÈGLE #4 / en-tête du groupe : L'ÉCONOMIE EST RÉSERVÉE AU DIRECTEUR.**
   `aoRentabiliteApi` est un export **SÉPARÉ**, jamais mélangé aux ressources
   ci-dessus — un import de `aoApi` seul n'expose AUCUN appel réseau vers
   l'endpoint de rentabilité (gardé par `aoApi.test.mjs`).
   ========================================================================== */

// ARC44 — Fabrique CRUD standard sur `/ao/<ressource>/`.
const crud = makeResourceFactory(api, '/ao')

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
  plansSources: crud('plans-sources'),
  releves: crud('releves'),
  obstacles: crud('obstacles'),
  zones: crud('zones'),
  chaines: crud('chaines'),

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
  seriesQR: crud('series-qr'),
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
  bibliotheque: crud('bibliotheque'),

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
