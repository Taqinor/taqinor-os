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

   IMPORTANT (gap backend confirmé) : il n'existe AUCUN ViewSet CRUD pour
   `WorkflowDefinition`/`WorkflowStepDefinition` — seule l'installation depuis
   un modèle (`workflow-templates/installer/`) matérialise ces lignes. Ce
   client ne fabrique donc PAS d'appels vers des endpoints qui n'existent pas ;
   `createDefinition`/`updateDefinition` ci-dessous sont volontairement absents.
   ========================================================================== */

const coreApi = {
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
}

export default coreApi
