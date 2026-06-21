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
  // scroll infini inversé (charger les plus anciens).
  listMessages: (conversationId, params) =>
    api.get(`/chat/conversations/${conversationId}/messages/`, { params }),
  // data = { conversation, body, mentions?, attachment_ids?, reply_to? }
  sendMessage: (data) => api.post('/chat/messages/', data),
  editMessage: (id, data) => api.patch(`/chat/messages/${id}/`, data),
  deleteMessage: (id) => api.delete(`/chat/messages/${id}/`),

  // ── Lu / non-lu ──
  // Marque la conversation lue jusqu'au dernier message (ou jusqu'à messageId).
  markRead: (conversationId, messageId) =>
    api.post(`/chat/conversations/${conversationId}/read/`,
      messageId ? { message: messageId } : {}),
  // Total des non-lus toutes conversations confondues → badge d'en-tête.
  unreadCount: () => api.get('/chat/unread-count/'),

  // ── Recherche ──
  search: (q, params) => api.get('/chat/search/', { params: { q, ...params } }),

  // ── Réactions (toggle : ajout/retrait du même emoji par le même user) ──
  toggleReaction: (messageId, emoji) =>
    api.post(`/chat/messages/${messageId}/reactions/`, { emoji }),

  // ── Épingles ──
  pinMessage: (messageId) => api.post(`/chat/messages/${messageId}/pin/`),
  unpinMessage: (messageId) => api.delete(`/chat/messages/${messageId}/pin/`),
  listPinned: (conversationId) =>
    api.get(`/chat/conversations/${conversationId}/pinned/`),

  // ── Pièces jointes ──
  // Upload binaire (multipart) → renvoie un id + URL signée. `onUploadProgress`
  // permet à FileUpload d'afficher une barre de progression.
  uploadAttachment: (file, onUploadProgress) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/chat/attachments/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
    })
  },
  // URL de récupération signée d'une pièce jointe (téléchargement).
  getAttachment: (id) => api.get(`/chat/attachments/${id}/`),

  // ── Partage d'enregistrement (lead, devis, facture…) dans une conversation ──
  // data = { conversation, record_type, record_id, note? }
  shareRecord: (data) => api.post('/chat/share-record/', data),

  // ── Membres de la société (pour @mentions + ajout de membres) ──
  // Réutilise l'endpoint /users/ existant (portée société côté serveur).
  listCompanyMembers: () => api.get('/users/'),
}

export default messagesApi
