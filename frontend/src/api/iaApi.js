import axios from 'axios'

// Même origine que la page par défaut (chemins relatifs via nginx) —
// fonctionne depuis localhost ET depuis l'adresse privée Tailscale.
import { originFrom } from './origin'
// Ré-authentification gracieuse partagée avec le client principal (axios.js) :
// on émet l'événement « session expirée » plutôt que de recharger durement la
// page, ce qui préserve l'état des formulaires OCR/agent en cours.
import { emitSessionExpired } from '../providers/session-bridge'
// VX161 — refresh 401 partagé avec axios.js (une seule promesse en vol,
// jamais un POST /token/refresh/ par requête en échec).
import { refreshSession } from './refreshCoordinator'

const ORIGIN = originFrom(import.meta.env.VITE_IA_API_URL)

const iaApi_instance = axios.create({
  baseURL: ORIGIN,
  withCredentials: true, // envoie les cookies httpOnly automatiquement
})

// ── Requete : prefixe /api/fastapi uniquement ─────────────────
// Plus d'injection manuelle du token — le cookie est envoye automatiquement
iaApi_instance.interceptors.request.use((config) => {
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/fastapi' + config.url
  }
  return config
})

// ── Reponse : refresh silencieux sur 401 ──────────────────────
iaApi_instance.interceptors.response.use(
  (response) => response,
  async (error) => {
    // `error.config` est absent sur les erreurs de configuration/setup : on le
    // garde optionnel pour ne jamais lever depuis l'intercepteur lui-même.
    const originalRequest = error.config || {}
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        // VX161 — promesse de refresh PARTAGÉE (avec axios.js) : N 401
        // simultanés (mix des deux instances) n'émettent qu'UN SEUL POST refresh.
        await refreshSession(ORIGIN)
        return iaApi_instance(originalRequest)
      } catch {
        // Refresh echoue : la session est reellement expiree.
      }
      // Ré-authentification gracieuse EN PLACE (pas de rechargement dur) —
      // identique au client principal : le SessionProvider affiche un modal de
      // reconnexion et les formulaires OCR/agent ouverts sont préservés.
      emitSessionExpired()
    }
    return Promise.reject(error)
  }
)

const iaApi = {
  queryAgent: (question) =>
    iaApi_instance.post('/sql-agent/query', { question }),

  // AG3 — exécute une action SENSIBLE précédemment PROPOSÉE par l'agent, via le
  // jeton opaque (`confirm_token`) renvoyé dans la proposition. Miroir frontend
  // de POST /sql-agent/confirm (AG2). Le bouton « Confirmer » de la carte de
  // proposition l'appelle ; « Annuler » se contente d'écarter la carte.
  confirmAction: (token) =>
    iaApi_instance.post('/sql-agent/confirm', { token }),

  // AG10/AG11 — transcrit un court clip vocal de l'assistant en texte via Groq
  // Whisper (POST /sql-agent/transcribe, multipart). Réponse : { text, language }
  // ou { available:false, detail } quand GROQ_API_KEY manque (dégradation
  // gracieuse, pas une erreur). Le micro de l'assistant (useVoiceChat) l'appelle.
  transcribeVoice: (blob) => {
    const formData = new FormData()
    const filename = (blob && blob.name) || 'audio.webm'
    formData.append('file', blob, filename)
    return iaApi_instance.post('/sql-agent/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // AG1 — catalogue des actions agentiques exécutables par l'utilisateur
  // courant (filtré par permission côté serveur). C'est un endpoint DJANGO
  // (apps/agent) : on passe le chemin absolu `/api/django/...` pour que
  // l'intercepteur NE préfixe PAS `/api/fastapi`. Métadonnées seules — aucune
  // exécution ici. Réponse : { count, actions: [{ key, label, description,
  // inputs, endpoint, method, required_permission, risk, confirm_summary }] }.
  getAgentActions: () =>
    iaApi_instance.get('/api/django/agent/actions/'),

  // YHARD2 — journal des actions IA confirmées (admin/Directeur) + annulation
  // d'une action réversible. Mêmes endpoints DJANGO absolus (apps/agent).
  getAgentActionLogs: () =>
    iaApi_instance.get('/api/django/agent/logs/'),
  undoAgentAction: (id) =>
    iaApi_instance.post(`/api/django/agent/logs/${id}/annuler/`),

  getSchema: () =>
    iaApi_instance.get('/sql-agent/schema'),

  // XKB23 — Assistant IA d'écriture & résumé (éditeur KB). Réutilise la même
  // clé LLM key-gated (GROQ/Anthropic) que le reste du service IA — aucun
  // nouveau fournisseur payant. `action` ∈ {generer, reformuler, corriger,
  // traduire_fr_ar, traduire_ar_fr, resumer}. `texte` est soit la sélection
  // (reformuler/corriger/traduire), soit le corps entier (générer/résumer).
  // BLOQUÉ : aucun endpoint FastAPI de rédaction/résumé n'existe encore
  // (grep de `backend/fastapi_ia/app/api/endpoints/` : seuls ocr/sql-agent/
  // chat/projets/transcription/voice sont montés) — câblé à l'URL
  // conventionnelle `/kb/redaction` (même préfixage que /ocr, /projets) en
  // attendant. Tant que le backend ne répond pas, l'appel échoue proprement
  // (401/404/503 selon dégradation) et l'UI affiche un message clair au lieu
  // de planter — jamais un no-op silencieux qui ferait croire à une écriture.
  kbRedaction: ({ action, texte, contexte } = {}) =>
    iaApi_instance.post('/kb/redaction', { action, texte, contexte }),

  getChatHistory: () =>
    iaApi_instance.get('/sql-agent/history'),

  clearChatHistory: () =>
    iaApi_instance.delete('/sql-agent/history'),

  processDocument: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return iaApi_instance.post('/ocr/process_document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  processStockDocument: ({ file, docType = '' }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    return iaApi_instance.post('/ocr/process_stock_document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  saveOcrDocument: (data) =>
    iaApi_instance.post('/ocr/save_document', data),

  getOcrDocuments: (limit = 50, offset = 0) =>
    iaApi_instance.get(`/ocr/documents?limit=${limit}&offset=${offset}`),

  deleteOcrDocument: (id) =>
    iaApi_instance.delete(`/ocr/documents/${id}`),
}

export default iaApi
