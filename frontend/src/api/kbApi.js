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
}

export default kbApi
