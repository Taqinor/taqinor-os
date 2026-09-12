import api from './axios'

/* ============================================================================
   IA — copilotes de génération (apps.ai_governance, Groupe NTAI). Toutes ces
   vues LISENT, proposent un brouillon, et n'écrivent JAMAIS dans un modèle
   métier. Sans clé LLM/STT configurée, elles répondent 503 avec un message FR
   explicite (« rédaction manuelle requise ») — jamais un appel réseau perdu.
   ----------------------------------------------------------------------------
   PACT141 — `rediger` (NTAI11) aplatit le fil de discussion + les activités
   d'une fiche et renvoie un brouillon FR éditable, jamais envoyé — réutilisé
   par la relance commerciale (ce lot) et la réponse SAV (ailleurs). Zéro
   appelant avant ce lot.
   ========================================================================== */

const aiGovernanceApi = {
  // `data` : { content_type: 'crm.lead', object_id, canal: 'email'|'whatsapp'|'sms',
  // intention? }. Réponse : { brouillon, entrees_fil, envoye:false, source, ... }.
  rediger: (data) => api.post('/ai/rediger/', data),

  // PACT144 — `data` : { module: 'commercial'|'facturation', periode: 'AAAA-MM' }.
  // Réponse : { module, periode, metriques:[{cle,label,valeur,unite}], narratif,
  // envoye:false, source }. 400 si le narratif cite un chiffre absent des
  // métriques (refus serveur, jamais rendu) ; 503 sans clé LLM.
  rapportPeriode: (data) => api.post('/ai/rapport-periode/', data),

  // NTAI8 — `data` : { content_type, object_id }. Réponse : { resume, faits,
  // entrees_fil, source }. 400 si le type n'est pas pris en charge ; 503 sans
  // clé LLM (« lecture manuelle »).
  resumeFiche: (data) => api.post('/ai/resume-fiche/', data),

  // NTAI9 — `data` : { content_type, object_id }. Réponse : { actions: [{
  // action, label, priorite, raison, action_key }], execute: false }.
  // Disponible même sans clé LLM (heuristique déterministe).
  prochainesActions: (data) => api.post('/ai/prochaines-actions/', data),

  /* --------------------------------------------------------------------
     Gouvernance IA (/ai-governance/*) — surfaces d'ADMINISTRATION, palier
     Administrateur/Directeur. Distinctes des copilotes ci-dessus.
     -------------------------------------------------------------------- */

  // NTAI6 — état réel de chaque capacité (ocr/stt/vision_qa/llm) : fournisseur
  // actif, motif d'inactivité, appels, latence médiane, dernière erreur.
  // Aucune clé d'API n'est jamais renvoyée.
  capabilities: () => api.get('/ai-governance/capabilities/'),

  // NTAI1 — agrégats d'usage & coût (par jour / feature / fournisseur).
  // `params` : { since?: 'AAAA-MM-JJ', feature?: string }.
  usage: (params) => api.get('/ai-governance/usage/', { params }),

  // NTAI2 — budget IA mensuel. `budgetStatut` renvoie { configure, plafond_mad,
  // depense_mad, pourcentage, depasse, alerte, periode } ; `configure: false`
  // = aucun budget défini (aucun pourcentage affiché contre un plafond
  // imaginaire).
  budgets: () => api.get('/ai-governance/budgets/'),
  budgetStatut: () => api.get('/ai-governance/budgets/statut/'),
  creerBudget: (data) => api.post('/ai-governance/budgets/', data),
  modifierBudget: (id, data) => api.patch(`/ai-governance/budgets/${id}/`, data),

  // NTAI5 — bibliothèque de prompts éditables. `promptsEffectifs` liste, pour
  // chaque clé connue du code, le corps qui s'applique et son origine.
  promptTemplates: () => api.get('/ai-governance/prompt-templates/'),
  promptsEffectifs: () => api.get('/ai-governance/prompt-templates/effective/'),
}

export default aiGovernanceApi
