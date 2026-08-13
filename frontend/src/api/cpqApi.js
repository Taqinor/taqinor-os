import api from './axios'

/* ============================================================================
   CPQ (apps.cpq) — client API.
   ----------------------------------------------------------------------------
   PACT129 — le configurateur CPQ n'avait AUCUN fichier client (module entier
   jamais exposé, Groupe PACT §E4). Première passe : les prix contractuels
   (NTCPQ5, montés en onglet « Tarifs négociés » sur la fiche client).

   PACT125 — le module frontend `features/cpq` existe désormais : ce client
   est étendu (AJOUT SEUL) au configurateur guidé (NTCPQ9/10, session
   questions-réponses → résultat résolu → devis brouillon) et à
   l'administration de ses questions. Miroir strict de `apps/cpq/urls.py` :
   aucune route inventée. `company` n'est JAMAIS envoyée (imposée serveur).
   ========================================================================== */

const P = '/cpq'

const cpqApi = {
  // Aucun filtre serveur par client (`PrixContractuelViewSet` ne déclare pas
  // de `filterset_fields` — le filtrage par client se fait CÔTÉ CLIENT sur
  // la réponse, jamais un `?client=` inventé que le serveur ignorerait).
  getPrixContractuels: (params) => api.get('/cpq/prix-contractuels/', { params }),
  // `data` : { client, produit, prix_ht, date_debut?, date_fin?, motif? } —
  // réservé Directeur/Commercial responsable (403 serveur sinon).
  createPrixContractuel: (data) => api.post('/cpq/prix-contractuels/', data),
  updatePrixContractuel: (id, data) => api.patch(`/cpq/prix-contractuels/${id}/`, data),
  deletePrixContractuel: (id) => api.delete(`/cpq/prix-contractuels/${id}/`),

  // ── Questions du configurateur (NTCPQ9) — lecture tout rôle, écriture
  // réservée Directeur/Commercial responsable côté serveur.
  getQuestionsConfigurateur: (params) =>
    api.get(`${P}/configurateur-questions/`, { params }),
  createQuestionConfigurateur: (data) =>
    api.post(`${P}/configurateur-questions/`, data),
  updateQuestionConfigurateur: (id, data) =>
    api.patch(`${P}/configurateur-questions/${id}/`, data),
  deleteQuestionConfigurateur: (id) =>
    api.delete(`${P}/configurateur-questions/${id}/`),

  // ── Contraintes de compatibilité entre deux produits (NTCPQ1).
  // `type` ∈ INCOMPATIBLE | REQUIERT | RECOMMANDE ; `bloquante` est calculée
  // côté serveur (lecture seule) — jamais envoyée.
  getContraintesCompatibilite: (params) =>
    api.get(`${P}/contraintes-compatibilite/`, { params }),
  createContrainteCompatibilite: (data) =>
    api.post(`${P}/contraintes-compatibilite/`, data),
  updateContrainteCompatibilite: (id, data) =>
    api.patch(`${P}/contraintes-compatibilite/${id}/`, data),
  deleteContrainteCompatibilite: (id) =>
    api.delete(`${P}/contraintes-compatibilite/${id}/`),
  // Corps : { produit_ids: [...] } → { valide, violations, bloquantes,
  // avertissements } — la séparation bloquantes/avertissements vient du
  // SERVEUR, jamais recalculée côté écran.
  validerCompatibilite: (produitIds) =>
    api.post(`${P}/valider-compatibilite/`, { produit_ids: produitIds }),

  // ── Session du configurateur guidé (NTCPQ9/10). `demarrer` renvoie
  // { session (token), questions[] } ; les trois suivantes sont indexées par
  // ce token, jamais par un id de session.
  demarrerConfigurateur: () => api.post(`${P}/configurateur/demarrer/`),
  repondreConfigurateur: (token, reponses) =>
    api.post(`${P}/configurateur/${token}/repondre/`, { reponses }),
  resultatConfigurateur: (token) =>
    api.get(`${P}/configurateur/${token}/resultat/`),
  genererDevisConfigurateur: (token, data) =>
    api.post(`${P}/configurateur/${token}/generer-devis/`, data || {}),
}

export default cpqApi
