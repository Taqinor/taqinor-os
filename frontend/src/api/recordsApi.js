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
  // (Re)tag une pièce jointe par phase de chantier (avant/pendant/apres/null).
  setAttachmentPhase: (attId, phase) =>
    api.post(`/records/attachments/${attId}/set-phase/`, { phase: phase ?? null }),
  deleteAttachment: (id) => api.delete(`/records/attachments/${id}/`),
}

export default recordsApi
