import api from './axios'

/* ============================================================================
   Base de connaissances (apps/kb) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /kb/... ».
   Un seul point d'import pour tous les écrans du module (UX43).
   Basenames DRF confirmés côté backend : articles / versions / article-liens /
   article-acls. @actions articles : publier / nouvelle-version / marquer-lu /
   resume-lecture. @action article-liens : articles (recherche inverse).
   ========================================================================== */

const kbApi = {
  // ── Articles (CRUD + recherche/filtres) ──
  // ?search= (titre/corps/catégorie/tags), ?categorie=, ?tag=, ?statut=,
  // ?ordering= (id/titre/date_modification).
  listArticles: (params) => api.get('/kb/articles/', { params }),
  getArticle: (id) => api.get(`/kb/articles/${id}/`),
  createArticle: (data) => api.post('/kb/articles/', data),
  updateArticle: (id, data) => api.patch(`/kb/articles/${id}/`, data),
  removeArticle: (id) => api.delete(`/kb/articles/${id}/`),

  // ── Cycle de vie / versionnement (POST, aucun corps requis) ──
  publier: (id) => api.post(`/kb/articles/${id}/publier/`),
  nouvelleVersion: (id) => api.post(`/kb/articles/${id}/nouvelle-version/`),
  marquerLu: (id) => api.post(`/kb/articles/${id}/marquer-lu/`),
  resumeLecture: (id) => api.get(`/kb/articles/${id}/resume-lecture/`),

  // ── Versions (lecture seule, ?article=<id>, ?ordering=version) ──
  listVersions: (params) => api.get('/kb/versions/', { params }),

  // ── Liens article → cible métier (?article=, ?type_cible=, ?cible_id=) ──
  listLiens: (params) => api.get('/kb/article-liens/', { params }),
  createLien: (data) => api.post('/kb/article-liens/', data),
  removeLien: (id) => api.delete(`/kb/article-liens/${id}/`),
  // Recherche inverse : articles liés à une cible.
  articlesForCible: (params) =>
    api.get('/kb/article-liens/articles/', { params }),

  // ── Droits d'accès par rôle (ACL) (?article=, ?niveau=) ──
  listAcls: (params) => api.get('/kb/article-acls/', { params }),
  createAcl: (data) => api.post('/kb/article-acls/', data),
  removeAcl: (id) => api.delete(`/kb/article-acls/${id}/`),

  // ── XKB8/21 — arbre + réordonnancement/déplacement/duplication ──
  arbre: () => api.get('/kb/articles/arbre/'),
  // VX241(a) — compte RÉEL du sous-arbre qu'un DELETE cascaderait (parent
  // est on_delete=CASCADE) : affiché AVANT confirmation de suppression.
  descendantsCount: (id) => api.get(`/kb/articles/${id}/descendants-count/`),
  deplacer: (id, data) => api.post(`/kb/articles/${id}/deplacer/`, data),
  dupliquer: (id, data) => api.post(`/kb/articles/${id}/dupliquer/`, data),
  items: (id, params) => api.get(`/kb/articles/${id}/items/`, { params }),

  // ── XKB14 — vérification/verrouillage + péremption ──
  verifier: (id, horizon_jours) =>
    api.post(`/kb/articles/${id}/verifier/`, { horizon_jours }),
  verrouiller: (id) => api.post(`/kb/articles/${id}/verrouiller/`),
  deverrouiller: (id) => api.post(`/kb/articles/${id}/deverrouiller/`),
  rapportPeremption: () => api.get('/kb/articles/rapport-peremption/'),

  // ── XKB10 — sommaire (TOC) ──
  sommaire: (id) => api.get(`/kb/articles/${id}/sommaire/`),

  // ── XKB18 — traduction ──
  traduire: (id, langue) => api.post(`/kb/articles/${id}/traduire/`, { langue }),

  // ── XKB11 — rétroliens ──
  retroliens: (id) => api.get(`/kb/articles/${id}/retroliens/`),

  // ── XKB12 — gabarits ──
  gabarits: () => api.get('/kb/articles/gabarits/'),
  enregistrerCommeGabarit: (id) =>
    api.post(`/kb/articles/${id}/enregistrer-comme-gabarit/`),
  depuisGabarit: (id) => api.post(`/kb/articles/${id}/depuis-gabarit/`),

  // ── XKB17 — export/import ──
  exportPdfUrl: (id) => `/api/django/kb/articles/${id}/export-pdf/`,
  exportMarkdownUrl: (id) => `/api/django/kb/articles/${id}/export-markdown/`,
  exportZipUrl: () => '/api/django/kb/articles/export-zip/',
  importerMarkdown: (data) => {
    const form = new FormData()
    if (data.fichier) form.append('fichier', data.fichier)
    if (data.contenu) form.append('contenu', data.contenu)
    return api.post('/kb/articles/importer-markdown/', form)
  },

  // ── XKB15 — favoris/récents ──
  togglerFavori: (id) => api.post(`/kb/articles/${id}/toggler-favori/`),
  recents: () => api.get('/kb/articles/recents/'),
  listFavoris: (params) => api.get('/kb/favoris/', { params }),

  // ── XKB16 — rapports/stats ──
  rapportTopConsultes: () => api.get('/kb/articles/rapport-top-consultes/'),
  rapportMoinsConsultes: () => api.get('/kb/articles/rapport-moins-consultes/'),
  rapportLacunesConnaissance: () =>
    api.get('/kb/articles/rapport-lacunes-connaissance/'),

  // ── ZGED10 — emoji + couverture ──
  uploadCouverture: (id, fichier) => {
    const form = new FormData()
    form.append('fichier', fichier)
    return api.post(`/kb/articles/${id}/couverture/`, form)
  },
  removeCouverture: (id) => api.delete(`/kb/articles/${id}/couverture/`),
  couvertureImageUrl: (id) => `/api/django/kb/articles/${id}/couverture-image/`,

  // ── ZGED12 — blocs réutilisables ──
  listBlocs: (params) => api.get('/kb/blocs/', { params }),
  createBloc: (data) => api.post('/kb/blocs/', data),
  removeBloc: (id) => api.delete(`/kb/blocs/${id}/`),

  // ── XKB19 — partages publics ──
  listPartages: (params) => api.get('/kb/partages/', { params }),
  createPartage: (data) => api.post('/kb/partages/', data),
  depublierPartage: (id) => api.post(`/kb/partages/${id}/depublier/`),
  // Endpoint PUBLIC (sans login) — jamais via l'instance ``api`` authentifiée
  // pour éviter d'envoyer un cookie de session inutile ; axios brut suffit,
  // le proxy /api/django est le même hôte.
  getPublicArticle: (token) => api.get(`/kb/public/${token}/`),

  // ── XKB22 — parcours d'intégration ──
  listParcours: (params) => api.get('/kb/parcours/', { params }),
  createParcours: (data) => api.post('/kb/parcours/', data),
  parcoursArticles: (id) => api.get(`/kb/parcours/${id}/articles/`),
  listParcoursArticles: (params) => api.get('/kb/parcours-articles/', { params }),
  createParcoursArticle: (data) => api.post('/kb/parcours-articles/', data),
  removeParcoursArticle: (id) => api.delete(`/kb/parcours-articles/${id}/`),
  listAssignations: (params) => api.get('/kb/parcours-assignations/', { params }),
  createAssignation: (data) => api.post('/kb/parcours-assignations/', data),
  assignationProgression: (id) =>
    api.get(`/kb/parcours-assignations/${id}/progression/`),
}

export default kbApi
