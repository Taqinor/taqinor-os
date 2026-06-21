import api from './axios'

// Activités planifiées + pièces jointes génériques (apps.records).
const recordsApi = {
  // ── Activités ──
  getActivities: (model, id) =>
    api.get('/records/activities/', { params: { model, id } }),
  getMyActivities: () => api.get('/records/activities/mine/'),
  getActivityTypes: () => api.get('/records/activity-types/'),
  createActivity: (data) => api.post('/records/activities/', data),
  updateActivity: (id, data) => api.patch(`/records/activities/${id}/`, data),
  deleteActivity: (id) => api.delete(`/records/activities/${id}/`),
  markActivityDone: (id, next) =>
    api.post(`/records/activities/${id}/done/`, next ? { next } : {}),

  // ── Tags (FG9) ──
  getTags: (q) => api.get('/records/tags/', { params: q ? { q } : {} }),
  createTag: (nom, couleur) => api.post('/records/tags/', { nom, couleur: couleur || '' }),
  deleteTag: (id) => api.delete(`/records/tags/${id}/`),
  getTaggedItems: (model, id) =>
    api.get('/records/tagged-items/', { params: { model, id } }),
  addTag: (model, id, tagId) =>
    api.post('/records/tagged-items/', { model, id, tag: tagId }),
  removeTag: (taggedItemId) => api.delete(`/records/tagged-items/${taggedItemId}/`),

  // ── Commentaires (FG7) ──
  getComments: (model, id) =>
    api.get('/records/comments/', { params: { model, id } }),
  createComment: (model, id, body) =>
    api.post('/records/comments/', { model, id, body }),
  updateComment: (id, body) => api.patch(`/records/comments/${id}/`, { body }),
  deleteComment: (id) => api.delete(`/records/comments/${id}/`),

  // ── Pièces jointes ──
  getAttachments: (model, id) =>
    api.get('/records/attachments/', { params: { model, id } }),
  uploadAttachment: (model, id, file, phase) => {
    const fd = new FormData()
    fd.append('model', model)
    fd.append('id', id)
    fd.append('file', file)
    if (phase) fd.append('phase', phase)
    return api.post('/records/attachments/', fd)
  },
  deleteAttachment: (id) => api.delete(`/records/attachments/${id}/`),
  // N5/L5 — re-tague la phase (avant/pendant/après) sans ré-uploader.
  setAttachmentPhase: (id, phase) =>
    api.patch(`/records/attachments/${id}/phase/`, { phase }),
}

export default recordsApi
