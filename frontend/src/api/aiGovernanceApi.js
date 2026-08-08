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
}

export default aiGovernanceApi
