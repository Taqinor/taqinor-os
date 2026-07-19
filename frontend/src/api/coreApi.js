import api from './axios'

/* ============================================================================
   XPLT8 — client API de la couche fondation `core` (jobs planifiés + modèles
   de workflow installables), et pont vers la boîte d'approbations
   transverse de `reporting` pour la liste des instances de workflow en cours.
   ----------------------------------------------------------------------------
   Miroir fin de `core/urls.py` (FG368 jobs/, FG369 workflow-templates/) et de
   `apps/reporting/approbations.py` (XKB1, source `'workflow'` =
   `core.WorkflowStepInstance`). Toutes les URLs sont relatives : l'intercepteur
   axios préfixe `/api/django`.

   WIR51 : le CRUD serveur des définitions de workflow existe désormais
   (`workflow-definitions/`, `workflow-step-definitions/`, company forcée côté
   serveur) — `workflowDefinitions` ci-dessous le consomme, comblant le GAP
   BACKEND que documentait l'écran Workflows.
   ========================================================================== */

const coreApi = {
  // SCA24 — thème white-label de la société courante (FG392, singleton). GET
  // est ouvert à tout utilisateur authentifié ; le shell l'utilise en lecture
  // seule (aucun écran d'édition ici). Renvoie des défauts vides (jamais 404)
  // quand aucun thème n'a été configuré — repli neutre côté frontend.
  theme: {
    getCourant: () => api.get('/core/theme/courant/'),
  },

  // ODX5 — catalogue de modules (ODX3 : manifests fusionnés à l'état
  // ModuleToggle de la société) + activer/désactiver avec fermeture de
  // dépendances. Lecture ouverte à tout utilisateur authentifié (le shell en
  // a besoin, ODX6) ; écriture réservée admin/responsable côté serveur.
  modules: {
    catalogue: () => api.get('/core/modules/'),
    activer: (key) => api.post(`/core/modules/${key}/activer/`),
    // `cascade` en query string (le backend lit `request.query_params`, pas
    // le corps) : désactive aussi les dépendants actifs au lieu de refuser
    // en 400.
    desactiver: (key, { cascade = false } = {}) =>
      api.post(`/core/modules/${key}/desactiver/${cascade ? '?cascade=1' : ''}`),
    // FG391 — lignes ModuleToggle brutes (dont `raison`, non exposée par le
    // catalogue) : sert uniquement à afficher le motif d'une désactivation
    // existante, jamais à activer/désactiver (le catalogue fait déjà la
    // fermeture de dépendances, cette route ne l'appliquerait pas).
    toggles: {
      list: () => api.get('/core/module-toggles/'),
    },
  },

  // FG368 — jobs planifiés (Celery Beat), lecture + exécution manuelle admin.
  jobs: {
    list: () => api.get('/core/jobs/'),
    run: (task) => api.post('/core/jobs/run/', { task }),
  },

  // FG369 — bibliothèque de modèles de workflow installables.
  workflowTemplates: {
    list: () => api.get('/core/workflow-templates/'),
    installer: (code) =>
      api.post('/core/workflow-templates/installer/', { code }),
  },

  // WIR51 — CRUD serveur des définitions de workflow (FG366) : composer une
  // chaîne d'étapes la persiste réellement (company forcée côté serveur, jamais
  // dans le corps ; `code` dérivé du nom côté serveur).
  workflowDefinitions: {
    list: () => api.get('/core/workflow-definitions/'),
    create: (payload) => api.post('/core/workflow-definitions/', payload),
    update: (id, payload) =>
      api.put(`/core/workflow-definitions/${id}/`, payload),
    remove: (id) => api.delete(`/core/workflow-definitions/${id}/`),
  },

  // XKB1 — boîte d'approbations centralisée (reporting), filtrée côté client
  // sur `source: 'workflow'` pour n'afficher que les instances BPM (FG366).
  workflowInstances: {
    listPending: () =>
      api.get('/reporting/approbations-en-attente/', {
        params: { source: 'workflow' },
      }),
    decider: (id, decision, motif) =>
      api.post('/reporting/approbations-en-attente/decider/', {
        source: 'workflow',
        id,
        decision, // 'approuver' | 'refuser'
        motif,
      }),
  },

  // XPLT9 — FG381 dashboards sans-code (CRUD, `layout` JSON opaque). Le
  // filtre global en cascade (XPLT9) vit dans `layout.globalFilters` (clé
  // additive, aucune migration) : `getDashboard`/`updateDashboardLayout`
  // sont les seuls appels nécessaires à ce mécanisme — le CRUD complet
  // (create/delete/list) n'est volontairement PAS dupliqué ici tant
  // qu'aucun écran constructeur ne le consomme (cf. DashboardFilterBar).
  dashboards: {
    get: (id) => api.get(`/core/dashboards/${id}/`),
    list: () => api.get('/core/dashboards/'),
    updateLayout: (id, layout) =>
      api.patch(`/core/dashboards/${id}/`, { layout }),
  },

  // XPLT10 — partage de dashboard : lien public tokenisé (créer/révoquer) +
  // mode TV (rotation plein écran des dashboards société/partagés).
  dashboardsPartages: {
    list: () => api.get('/core/dashboards-partages/'),
    create: (dashboardId, expiresAt) =>
      api.post('/core/dashboards-partages/', {
        dashboard: dashboardId, expires_at: expiresAt || null,
      }),
    // Révoquer = kill-switch (`actif=False`), jamais une suppression physique.
    revoke: (id) => api.patch(`/core/dashboards-partages/${id}/`, { actif: false }),
    remove: (id) => api.delete(`/core/dashboards-partages/${id}/`),
    // Accès public (sans session) via le seul jeton — utilisé par une page
    // publique dédiée si besoin ; le kiosque TV authentifié utilise `tv()`.
    getPublic: (token) => api.get(`/core/dashboards-partages/public/${token}/`),
  },
  dashboardsTv: {
    list: () => api.get('/core/dashboards-tv/'),
  },
  // XPLT23 — onglet « Confidentialité » (loi 09-08 / CNDP), réservé
  // admin/responsable (le backend re-vérifie : IsAdminOrResponsableTier).
  // `company` n'est jamais envoyée : toujours imposée côté serveur.
  confidentialite: {
    // Registre des traitements CNDP — CRUD complet + export CSV.
    registreTraitements: {
      list: () => api.get('/core/registre-traitements/'),
      create: (data) => api.post('/core/registre-traitements/', data),
      update: (id, data) => api.patch(`/core/registre-traitements/${id}/`, data),
      remove: (id) => api.delete(`/core/registre-traitements/${id}/`),
      exportCsv: () =>
        api.get('/core/registre-traitements/export-csv/', { responseType: 'blob' }),
    },
    // Demandes de personnes concernées (accès/effacement/rectification) —
    // soumission + suivi + exécution (`traiter`, gérée par core.dsr).
    dsrRequests: {
      list: () => api.get('/core/dsr-requests/'),
      create: (data) => api.post('/core/dsr-requests/', data),
      traiter: (id) => api.post(`/core/dsr-requests/${id}/traiter/`),
    },
  },
}

export default coreApi
