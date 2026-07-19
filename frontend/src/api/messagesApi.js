import api from './axios'

// S12 — Client API du module Discuter (chat interne d'équipe). Toutes les
// routes vivent sous /api/django/chat/ (le préfixe /api/django est injecté par
// l'intercepteur axios). La portée société est appliquée côté serveur : on ne
// passe JAMAIS de company depuis le client.
//
// Le backend chat est construit en parallèle (S17–S19) ; ce module est écrit
// contre le contrat REST convenu et reste la SEULE source des appels chat.
const messagesApi = {
  // ── Conversations ──
  // Liste mes conversations (DMs + canaux) avec aperçu du dernier message et
  // unread_count. Pagination DRF standard ({results, next, ...}).
  listConversations: (params) => api.get('/chat/conversations/', { params }),
  getConversation: (id) => api.get(`/chat/conversations/${id}/`),
  // data = { kind: 'dm'|'channel', name?, member_ids: [], ... }
  createConversation: (data) => api.post('/chat/conversations/', data),
  updateConversation: (id, data) =>
    api.patch(`/chat/conversations/${id}/`, data),
  archiveConversation: (id) =>
    api.post(`/chat/conversations/${id}/archive/`),
  // Mute / unmute (toggle côté UI via `muted` booléen).
  muteConversation: (id, muted) =>
    api.post(`/chat/conversations/${id}/mute/`, { muted }),

  // ── Membres (canaux) ──
  addMembers: (id, member_ids) =>
    api.post(`/chat/conversations/${id}/members/`, { member_ids }),
  removeMember: (id, userId) =>
    api.delete(`/chat/conversations/${id}/members/${userId}/`),
  leaveConversation: (id) =>
    api.post(`/chat/conversations/${id}/leave/`),

  // ── Messages ──
  // Page la plus récente d'abord (newest-first) ; `before` = id/curseur pour le
  // scroll infini inversé (charger les plus anciens). Le backend liste les
  // messages via /chat/messages/?conversation=<id> (filtrage par query param).
  listMessages: (conversationId, params) =>
    api.get('/chat/messages/', {
      params: { conversation: conversationId, ...params },
    }),
  // data = { conversation, body, mentions?, reply_to?, record_type?, record_id? }
  sendMessage: (data) => api.post('/chat/messages/', data),
  editMessage: (id, data) => api.patch(`/chat/messages/${id}/`, data),
  deleteMessage: (id) => api.delete(`/chat/messages/${id}/`),

  // ── Lu / non-lu ──
  // Marque la conversation lue jusqu'au dernier message (ou jusqu'à messageId).
  markRead: (conversationId, messageId) =>
    api.post(`/chat/conversations/${conversationId}/read/`,
      messageId ? { message: messageId } : {}),
  // Total des non-lus toutes conversations confondues → badge d'en-tête.
  // Le backend répond { per_conversation: {id: n}, total } via l'action `unread`.
  unreadCount: () => api.get('/chat/conversations/unread/'),

  // ── Recherche ──
  search: (q, params) =>
    api.get('/chat/conversations/search/', { params: { q, ...params } }),

  // ── Réactions (toggle : ajout/retrait du même emoji par le même user) ──
  toggleReaction: (messageId, emoji) =>
    api.post(`/chat/messages/${messageId}/react/`, { emoji }),

  // ── Épingles ──
  pinMessage: (messageId) => api.post(`/chat/messages/${messageId}/pin/`),
  unpinMessage: (messageId) => api.post(`/chat/messages/${messageId}/unpin/`),
  listPinned: (conversationId) =>
    api.get('/chat/messages/', {
      params: { conversation: conversationId, pinned: 1 },
    }),

  // ── Pièces jointes ──
  // Upload binaire (multipart) → crée un message portant la pièce jointe.
  // `onUploadProgress` permet à FileUpload d'afficher une barre de progression.
  // Le backend attend `conversation` + `file` (et `kind=voice` pour un mémo).
  uploadAttachment: (conversationId, file, onUploadProgress) => {
    const fd = new FormData()
    fd.append('conversation', conversationId)
    fd.append('file', file)
    return api.post('/chat/messages/upload/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
    })
  },
  // Téléchargement (proxy même-origine) d'une pièce jointe d'un message.
  getAttachment: (messageId, attachmentId) =>
    api.get(`/chat/messages/${messageId}/attachments/${attachmentId}/download/`),

  // ── Partage d'enregistrement (lead, devis, chantier…) dans une conversation ──
  // Le backend n'a pas de route dédiée : un partage est un message normal portant
  // record_type/record_id. data = { conversation, record_type, record_id, body? }
  shareRecord: (data) => api.post('/chat/messages/', data),

  // ── Membres de la société (pour @mentions + ajout de membres) ──
  // Réutilise l'endpoint /users/ existant (portée société côté serveur).
  listCompanyMembers: () => api.get('/users/'),

  // ── WIR156 / XKB26 — Statut personnalisé + Ne pas déranger + présence ──
  // Le statut est TOUJOURS celui de l'appelant (jamais un autre user_id) ;
  // `colleagues` liste les statuts des collègues de la société (lecture seule).
  status: {
    me: () => api.get('/chat/status/me/'),
    setStatus: (data) => api.post('/chat/status/me/', data),
    clear: () => api.post('/chat/status/clear/'),
    // Body: { start: iso|null, end: iso|null } ; null/null lève le NPD.
    setDnd: (data) => api.post('/chat/status/dnd/', data),
    colleagues: () => api.get('/chat/status/colleagues/'),
  },
}

export default messagesApi
