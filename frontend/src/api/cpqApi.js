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

  // ── Paramètres CPQ (WIR105) : seuils de marge par famille (NTCPQ6) et
  // paliers d'approbation par profondeur de remise (NTCPQ7/8). Les deux
  // ViewSets existent précisément pour retirer la dépendance au Django admin.
  // `marge_min_pct` est une donnée INTERNE : elle ne sort jamais vers un PDF
  // ou un écran client — ce paramétrage est réservé au palier responsable.
  getSeuilsMarge: (params) => api.get(`${P}/seuils-marge/`, { params }),
  createSeuilMarge: (data) => api.post(`${P}/seuils-marge/`, data),
  updateSeuilMarge: (id, data) => api.patch(`${P}/seuils-marge/${id}/`, data),
  deleteSeuilMarge: (id) => api.delete(`${P}/seuils-marge/${id}/`),

  getReglesApprobationRemise: (params) =>
    api.get(`${P}/regles-approbation-remise/`, { params }),
  createRegleApprobationRemise: (data) =>
    api.post(`${P}/regles-approbation-remise/`, data),
  updateRegleApprobationRemise: (id, data) =>
    api.patch(`${P}/regles-approbation-remise/${id}/`, data),
  deleteRegleApprobationRemise: (id) =>
    api.delete(`${P}/regles-approbation-remise/${id}/`),

  // ── Offres groupées / bundles (NTCPQ3). `lignes` est IMBRIQUÉE dans le
  // corps (le sérialiseur crée/remplace les lignes) ; `prix_total` optionnel
  // est réparti au prorata quand les lignes sont en mode FIXE.
  getOffresGroupees: (params) => api.get(`${P}/offres-groupees/`, { params }),
  createOffreGroupee: (data) => api.post(`${P}/offres-groupees/`, data),
  updateOffreGroupee: (id, data) => api.put(`${P}/offres-groupees/${id}/`, data),
  deleteOffreGroupee: (id) => api.delete(`${P}/offres-groupees/${id}/`),
  // `devis_id` dans le CORPS : la vue lit `query_params` OU `data` — le corps
  // évite de faire transiter un identifiant en query string.
  appliquerOffreGroupee: (id, devisId) =>
    api.post(`${P}/offres-groupees/${id}/appliquer/`, { devis_id: devisId }),

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
