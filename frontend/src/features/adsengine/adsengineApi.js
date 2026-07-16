import api from '../../api/axios'
import { makeResourceFactory } from '../../api/resource'

/* ============================================================================
   ENG21 — Client API du module « Publicité » (moteur Meta-ads autonome).
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /adsengine/... ».
   Point d'import unique pour tous les écrans du module (ENG22–ENG28). Colocalisé
   dans la feature (lane frontend/adsengine totalement disjointe — aucun fichier
   partagé avec les autres lanes).

   DOCTRINE (docs/engine/research/scope-features.md) :
   - Les identifiants Meta sont WRITE-ONLY : `connection.save` les écrit, RIEN
     ne les relit (`connection.get` ne renvoie qu'un statut, jamais un secret).
   - Aucun toggle d'activation n'est exposé (le client naît PAUSED, par design).
   - Chaque chiffre du dashboard est traçable jusqu'aux leads réels
     (`metrics.leads` — jamais de chiffre boîte-noire).
   - Approuver/rejeter sont des actions STRUCTURÉES (jamais du chat).
   Le backend (apps/adsengine) est construit dans une lane parallèle ; les tests
   RTL de ce module MOCKENT entièrement cette couche.
   ========================================================================== */

const resource = makeResourceFactory(api, '/adsengine')

const adsengineApi = {
  // ── ENG22 — Connexion Meta (identifiants WRITE-ONLY) ──
  connection: {
    // Statut de connexion uniquement — JAMAIS les secrets (write-only).
    get: () => api.get('/adsengine/connection/'),
    // Enregistre les identifiants ; ils ne sont jamais relus.
    save: (payload) => api.post('/adsengine/connection/', payload),
    // ENG12 — santé du câblage (jeton, compte pub, pixel/CAPI, PAUSED).
    health: () => api.get('/adsengine/connection/health/'),
  },

  // ── ENG9 — Garde-fous (plafond quotidien/mensuel, band d'auto-approbation) ──
  guardrail: {
    get: () => api.get('/adsengine/guardrail/'),
    update: (payload) => api.patch('/adsengine/guardrail/', payload),
  },

  // ── ENG10/ENG23 — Métriques du dashboard « un chiffre » ──
  metrics: {
    dashboard: (params) => api.get('/adsengine/metrics/dashboard/', { params }),
    // Drill-down : la liste des leads réels derrière un chiffre (traçabilité).
    leads: (metric, params) =>
      api.get('/adsengine/metrics/leads/', { params: { metric, ...params } }),
  },

  // ── ENG13 — Alertes (bandeau dashboard, WhatsApp-first) ──
  alerts: {
    list: (params) => api.get('/adsengine/alerts/', { params }),
  },

  // ── ENG5/ENG24 — Campagnes (miroirs) + classement par créatif ──
  campaigns: {
    ...resource('campaigns'),
    syncNow: () => api.post('/adsengine/campaigns/sync-now/'),
    creativeRanking: (params) =>
      api.get('/adsengine/campaigns/creative-ranking/', { params }),
  },

  // ── ENG7/ENG25/ENG28 — EngineAction (boîte d'approbation + journal) ──
  actions: {
    ...resource('actions'),
    pending: (params) =>
      api.get('/adsengine/actions/', { params: { statut: 'en_attente', ...params } }),
    log: (params) => api.get('/adsengine/actions/', { params }),
    approve: (id) => api.post(`/adsengine/actions/${id}/approuver/`),
    reject: (id, payload) => api.post(`/adsengine/actions/${id}/rejeter/`, payload),
  },

  // ── ENG11/ENG26 — Brief hebdomadaire ──
  brief: {
    latest: (params) => api.get('/adsengine/brief/', { params }),
  },

  // ── ENG15/ENG27 — Bibliothèque créative + policy-check + variantes ──
  creatives: {
    ...resource('creatives'),
    upload: (formData) => api.post('/adsengine/creatives/upload/', formData),
    policyCheck: (id, payload) =>
      api.post(`/adsengine/creatives/${id}/policy-check/`, payload),
    generateVariants: (id) => api.post(`/adsengine/creatives/${id}/variantes/`),
  },
}

export default adsengineApi
